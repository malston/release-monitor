#!/usr/bin/env python3
"""
GitHub Release Asset Downloader

Downloads release assets from GitHub with authentication, verification,
retry logic, and proper error handling.
"""

import os
import hashlib
import time
import logging
import requests
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import tempfile
import shutil
from urllib.parse import urlparse
import json

logger = logging.getLogger(__name__)


class GitHubDownloader:
    """
    Downloads GitHub release assets with authentication and verification.
    """

    def __init__(self, token: str, download_dir: str = 'downloads',
                 chunk_size: int = 8192, timeout: int = 300):
        """
        Initialize GitHub downloader.

        Args:
            token: GitHub API token
            download_dir: Directory to store downloaded files
            chunk_size: Chunk size for streaming downloads (bytes)
            timeout: Request timeout in seconds
        """
        self.token = token
        self.download_dir = Path(download_dir)
        self.chunk_size = chunk_size
        self.timeout = timeout

        # Create download directory
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # Setup session with authentication
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Release-Monitor-Downloader/1.0'
        })

        # Configure proxy settings from environment if present
        proxy_settings = {}
        if os.getenv('HTTP_PROXY') or os.getenv('http_proxy'):
            proxy_settings['http'] = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
        if os.getenv('HTTPS_PROXY') or os.getenv('https_proxy'):
            proxy_settings['https'] = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')

        if proxy_settings:
            self.session.proxies = proxy_settings
            logger.info(f"Configured proxy settings: {list(proxy_settings.keys())}")

        # Configure SSL verification
        skip_ssl_verification = os.environ.get('GITHUB_SKIP_SSL_VERIFICATION', 'false').lower() == 'true'
        if skip_ssl_verification:
            logger.warning("SSL verification disabled for GitHub downloads")
            self.session.verify = False
            # Suppress SSL warnings
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        logger.info(f"GitHub downloader initialized, download dir: {self.download_dir}")

    def download_release_content(self, release_data: Dict[str, Any],
                               asset_patterns: Optional[List[str]] = None,
                               source_config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Download all available content from a GitHub release (assets + source code).

        Args:
            release_data: Release data from GitHub API or monitor
            asset_patterns: Optional list of patterns to filter content (e.g., ['*.tar.gz', '*.zip', '*.yaml'])
            source_config: Optional source archive configuration

        Returns:
            List of download results with metadata
        """
        download_results = []

        # Default source configuration
        if source_config is None:
            source_config = {'enabled': True, 'prefer': 'tarball', 'fallback_only': True}

        # Download release assets (binaries, manifests, etc.)
        if release_data.get('assets'):
            asset_results = self.download_release_assets(release_data, asset_patterns)
            download_results.extend(asset_results)

        # Download source code archives based on configuration
        if source_config.get('enabled', True) and self._should_download_source(release_data, asset_patterns, download_results, source_config):
            source_results = self.download_source_archives(release_data, asset_patterns, source_config)
            download_results.extend(source_results)

        return download_results

    def download_release_assets(self, release_data: Dict[str, Any],
                              asset_patterns: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Download all or filtered assets from a GitHub release.

        Args:
            release_data: Release data from GitHub API or monitor
            asset_patterns: Optional list of patterns to filter assets (e.g., ['*.tar.gz', '*.zip'])

        Returns:
            List of download results with metadata
        """
        if not release_data.get('assets'):
            logger.warning(f"No assets found in release {release_data.get('tag_name', 'unknown')}")
            return []

        # Create release-specific directory
        repo_name = release_data.get('repository', 'unknown').replace('/', '_')
        tag_name = release_data.get('tag_name', 'unknown')
        release_dir = self.download_dir / repo_name / tag_name
        release_dir.mkdir(parents=True, exist_ok=True)

        download_results = []

        for asset in release_data.get('assets', []):
            try:
                # Check if asset matches patterns
                if asset_patterns and not self._matches_patterns(asset['name'], asset_patterns):
                    logger.debug(f"Skipping asset {asset['name']} (doesn't match patterns)")
                    continue

                # Download the asset
                result = self._download_single_asset(asset, release_dir, release_data)
                download_results.append(result)

            except Exception as e:
                logger.error(f"Failed to download asset {asset.get('name', 'unknown')}: {e}")
                download_results.append({
                    'asset_name': asset.get('name', 'unknown'),
                    'success': False,
                    'error': str(e),
                    'download_time': time.time()
                })

        logger.info(f"Downloaded {sum(1 for r in download_results if r['success'])} of "
                   f"{len(download_results)} assets for {repo_name}:{tag_name}")

        return download_results

    def _download_single_asset(self, asset: Dict[str, Any], release_dir: Path,
                              release_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Download a single asset with retry logic.

        Args:
            asset: Asset metadata from GitHub API
            release_dir: Directory to save the asset
            release_data: Full release data for context

        Returns:
            Download result metadata
        """
        asset_name = asset['name']
        download_url = asset['browser_download_url']
        file_path = release_dir / asset_name

        logger.info(f"Downloading {asset_name} from {download_url}")

        start_time = time.time()

        try:
            # Download with retry logic
            success, error_msg = self._download_with_retry(download_url, file_path, asset)

            if success:
                # Verify download
                verification_result = self.verify_download(file_path)

                # Prepare result metadata
                result = {
                    'asset_name': asset_name,
                    'success': True,
                    'file_path': str(file_path),
                    'file_size': file_path.stat().st_size,
                    'expected_size': asset.get('size'),
                    'download_time': time.time() - start_time,
                    'download_url': download_url,
                    'verification': verification_result,
                    'release_info': {
                        'repository': release_data.get('repository'),
                        'tag_name': release_data.get('tag_name'),
                        'published_at': release_data.get('published_at')
                    }
                }

                logger.info(f"Successfully downloaded {asset_name} "
                           f"({result['file_size']} bytes in {result['download_time']:.1f}s)")
                return result
            else:
                return {
                    'asset_name': asset_name,
                    'success': False,
                    'error': error_msg,
                    'download_time': time.time() - start_time,
                    'download_url': download_url
                }

        except Exception as e:
            logger.error(f"Unexpected error downloading {asset_name}: {e}")
            return {
                'asset_name': asset_name,
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'download_time': time.time() - start_time
            }

    def _download_with_retry(self, url: str, file_path: Path, asset: Dict[str, Any],
                           max_retries: int = 3) -> Tuple[bool, Optional[str]]:
        """
        Download file with retry logic and streaming.

        Args:
            url: Download URL
            file_path: Local file path to save to
            asset: Asset metadata for size checking
            max_retries: Maximum number of retry attempts

        Returns:
            Tuple of (success, error_message)
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # Use a temporary file for atomic downloads
                with tempfile.NamedTemporaryFile(delete=False, dir=file_path.parent) as temp_file:
                    temp_path = Path(temp_file.name)

                    # Start the download
                    response = self.session.get(url, stream=True, timeout=self.timeout)
                    response.raise_for_status()

                    # Check content length if available
                    expected_size = asset.get('size')
                    content_length = response.headers.get('content-length')
                    if content_length:
                        content_length = int(content_length)
                        if expected_size and content_length != expected_size:
                            logger.warning(f"Content-Length ({content_length}) doesn't match "
                                         f"expected size ({expected_size})")

                    # Download in chunks with progress reporting
                    downloaded_size = 0
                    hash_sha256 = hashlib.sha256()
                    last_progress_time = time.time()

                    for chunk in response.iter_content(chunk_size=self.chunk_size):
                        if chunk:  # Filter out keep-alive chunks
                            temp_file.write(chunk)
                            hash_sha256.update(chunk)
                            downloaded_size += len(chunk)

                            # Report progress every 5 seconds
                            current_time = time.time()
                            if current_time - last_progress_time >= 5:
                                mb_downloaded = downloaded_size / (1024 * 1024)
                                if content_length:
                                    percent = (downloaded_size / content_length) * 100
                                    mb_total = content_length / (1024 * 1024)
                                    logger.info(f"Download progress: {mb_downloaded:.1f}/{mb_total:.1f} MB ({percent:.1f}%)")
                                else:
                                    logger.info(f"Download progress: {mb_downloaded:.1f} MB downloaded")
                                last_progress_time = current_time

                    temp_file.flush()
                    os.fsync(temp_file.fileno())

                # Verify size if expected
                if expected_size and downloaded_size != expected_size:
                    temp_path.unlink()
                    raise ValueError(f"Downloaded size ({downloaded_size}) doesn't match "
                                   f"expected size ({expected_size})")

                # Atomically move to final location
                shutil.move(str(temp_path), str(file_path))

                # Store checksum for verification
                checksum_file = file_path.with_suffix(file_path.suffix + '.sha256')
                with open(checksum_file, 'w') as f:
                    f.write(f"{hash_sha256.hexdigest()}  {file_path.name}\n")

                return True, None

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Download attempt {attempt + 1} failed: {e}")

                # Check if this is an SSL error
                if 'CERTIFICATE_VERIFY_FAILED' in str(e) or 'SSLError' in str(e):
                    logger.error("SSL certificate verification failed. "
                               "Set GITHUB_SKIP_SSL_VERIFICATION=true to disable verification.")

                # Clean up temporary file if it exists
                try:
                    if 'temp_path' in locals() and temp_path.exists():
                        temp_path.unlink()
                except:
                    pass

                if attempt < max_retries:
                    # Exponential backoff
                    delay = 2 ** attempt
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)

        return False, f"Failed after {max_retries + 1} attempts. Last error: {last_error}"

    def verify_download(self, file_path: Path, expected_checksum: Optional[str] = None) -> Dict[str, Any]:
        """
        Verify downloaded file integrity.

        Args:
            file_path: Path to downloaded file
            expected_checksum: Optional expected SHA256 checksum

        Returns:
            Verification result metadata
        """
        if not file_path.exists():
            return {
                'verified': False,
                'error': 'File does not exist',
                'file_path': str(file_path)
            }

        try:
            # Calculate SHA256 checksum
            hash_sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(self.chunk_size), b""):
                    hash_sha256.update(chunk)

            calculated_checksum = hash_sha256.hexdigest()

            # Check if we have a stored checksum file
            checksum_file = file_path.with_suffix(file_path.suffix + '.sha256')
            stored_checksum = None
            if checksum_file.exists():
                with open(checksum_file, 'r') as f:
                    line = f.readline().strip()
                    if line:
                        stored_checksum = line.split()[0]

            # Verify against expected or stored checksum
            checksum_to_verify = expected_checksum or stored_checksum
            checksum_match = None
            if checksum_to_verify:
                checksum_match = calculated_checksum.lower() == checksum_to_verify.lower()

            result = {
                'verified': True,
                'file_path': str(file_path),
                'file_size': file_path.stat().st_size,
                'sha256': calculated_checksum,
                'checksum_match': checksum_match,
                'expected_checksum': checksum_to_verify
            }

            if checksum_match is False:
                result['error'] = 'Checksum mismatch'
                logger.error(f"Checksum mismatch for {file_path}: "
                           f"calculated={calculated_checksum}, expected={checksum_to_verify}")

            return result

        except Exception as e:
            return {
                'verified': False,
                'error': str(e),
                'file_path': str(file_path)
            }

    def _matches_patterns(self, filename: str, patterns: List[str]) -> bool:
        """
        Check if filename matches any of the given patterns.

        Args:
            filename: Name of the file to check
            patterns: List of patterns (supports * wildcards)

        Returns:
            True if filename matches any pattern
        """
        import fnmatch

        filename_lower = filename.lower()
        matched = False

        # First check inclusion patterns
        for pattern in patterns:
            if not pattern.startswith('!'):
                if fnmatch.fnmatch(filename_lower, pattern.lower()):
                    matched = True
                    break

        # If no inclusion pattern matched, return False
        if not matched:
            return False

        # Now check exclusion patterns
        for pattern in patterns:
            if pattern.startswith('!'):
                if fnmatch.fnmatch(filename_lower, pattern[1:].lower()):
                    return False

        return True

    def get_download_stats(self) -> Dict[str, Any]:
        """
        Get statistics about downloaded files.

        Returns:
            Statistics about the download directory
        """
        if not self.download_dir.exists():
            return {
                'total_files': 0,
                'total_size': 0,
                'repositories': 0
            }

        total_files = 0
        total_size = 0
        repositories = set()

        for repo_dir in self.download_dir.iterdir():
            if repo_dir.is_dir():
                repositories.add(repo_dir.name)
                for tag_dir in repo_dir.iterdir():
                    if tag_dir.is_dir():
                        for file_path in tag_dir.iterdir():
                            if file_path.is_file() and not file_path.name.endswith('.sha256'):
                                total_files += 1
                                total_size += file_path.stat().st_size

        return {
            'total_files': total_files,
            'total_size': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'repositories': len(repositories),
            'download_dir': str(self.download_dir)
        }

    def cleanup_old_downloads(self, keep_versions: int = 5) -> Dict[str, Any]:
        """
        Clean up old downloaded versions to save space.

        Args:
            keep_versions: Number of recent versions to keep per repository

        Returns:
            Cleanup statistics
        """
        if not self.download_dir.exists():
            return {'cleaned_files': 0, 'freed_space': 0}

        cleaned_files = 0
        freed_space = 0

        for repo_dir in self.download_dir.iterdir():
            if not repo_dir.is_dir():
                continue

            # Get all version directories sorted by modification time
            version_dirs = [d for d in repo_dir.iterdir() if d.is_dir()]
            version_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)

            # Remove old versions
            for old_dir in version_dirs[keep_versions:]:
                try:
                    for file_path in old_dir.iterdir():
                        if file_path.is_file():
                            freed_space += file_path.stat().st_size
                            cleaned_files += 1

                    shutil.rmtree(old_dir)
                    logger.info(f"Cleaned up old version: {old_dir}")

                except Exception as e:
                    logger.error(f"Error cleaning up {old_dir}: {e}")

        return {
            'cleaned_files': cleaned_files,
            'freed_space': freed_space,
            'freed_space_mb': round(freed_space / (1024 * 1024), 2)
        }

    def _should_download_source(self, release_data: Dict[str, Any],
                               asset_patterns: Optional[List[str]],
                               asset_results: List[Dict[str, Any]],
                               source_config: Dict[str, Any]) -> bool:
        """
        Determine if source code archives should be downloaded.

        Args:
            release_data: Release data from GitHub API
            asset_patterns: Asset filtering patterns
            asset_results: Results from asset downloads
            source_config: Source archive configuration

        Returns:
            True if source code should be downloaded
        """
        # Check if fallback_only is disabled (always download source)
        if not source_config.get('fallback_only', True):
            return True

        # If no asset patterns specified, download source when no assets were found
        if not asset_patterns:
            return len([r for r in asset_results if r['success']]) == 0

        # Check if patterns explicitly request source archives (only exact matches for source-specific terms)
        explicit_source_patterns = ['source', 'tarball', 'zipball']
        for pattern in asset_patterns:
            pattern_lower = pattern.lower()
            if any(sp == pattern_lower for sp in explicit_source_patterns):
                return True

        # Check if patterns include manifest/config file types that might not have traditional assets
        manifest_patterns = ['*.yaml', '*.yml', '*.json', '*.xml', '*.toml']
        for pattern in asset_patterns:
            pattern_lower = pattern.lower()
            if any(mp in pattern_lower for mp in manifest_patterns):
                # If looking for manifests but no assets matched, try source
                return len([r for r in asset_results if r['success']]) == 0

        # If assets were successfully downloaded, don't download source unless explicitly requested
        successful_assets = [r for r in asset_results if r['success']]
        if successful_assets:
            return False

        # No successful asset downloads, fall back to source
        return True

    def download_source_archives(self, release_data: Dict[str, Any],
                                asset_patterns: Optional[List[str]] = None,
                                source_config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Download source code archives (tarball and/or zipball) from GitHub release.

        Args:
            release_data: Release data from GitHub API or monitor
            asset_patterns: Optional list of patterns to filter archives
            source_config: Optional source archive configuration

        Returns:
            List of download results with metadata
        """
        download_results = []

        # Default source configuration
        if source_config is None:
            source_config = {'enabled': True, 'prefer': 'tarball', 'fallback_only': True}

        # Create release-specific directory
        repo_name = release_data.get('repository', 'unknown').replace('/', '_')
        tag_name = release_data.get('tag_name', 'unknown')
        release_dir = self.download_dir / repo_name / tag_name
        release_dir.mkdir(parents=True, exist_ok=True)

        # Prepare source archive info based on preference
        source_archives = []
        prefer = source_config.get('prefer', 'tarball').lower()

        if prefer == 'both':
            # Download both tarball and zipball
            if release_data.get('tarball_url'):
                source_archives.append({
                    'name': f'{repo_name}-{tag_name}.tar.gz',
                    'url': release_data['tarball_url'],
                    'type': 'tarball'
                })
            if release_data.get('zipball_url'):
                source_archives.append({
                    'name': f'{repo_name}-{tag_name}.zip',
                    'url': release_data['zipball_url'],
                    'type': 'zipball'
                })
        elif prefer == 'zipball':
            # Prefer zipball, fallback to tarball
            if release_data.get('zipball_url'):
                source_archives.append({
                    'name': f'{repo_name}-{tag_name}.zip',
                    'url': release_data['zipball_url'],
                    'type': 'zipball'
                })
            elif release_data.get('tarball_url'):
                source_archives.append({
                    'name': f'{repo_name}-{tag_name}.tar.gz',
                    'url': release_data['tarball_url'],
                    'type': 'tarball'
                })
        else:
            # Default: prefer tarball, fallback to zipball
            if release_data.get('tarball_url'):
                source_archives.append({
                    'name': f'{repo_name}-{tag_name}.tar.gz',
                    'url': release_data['tarball_url'],
                    'type': 'tarball'
                })
            elif release_data.get('zipball_url'):
                source_archives.append({
                    'name': f'{repo_name}-{tag_name}.zip',
                    'url': release_data['zipball_url'],
                    'type': 'zipball'
                })

        for archive in source_archives:
            try:
                # Source archives are controlled by source_config settings (prefer, fallback_only, etc.)
                # rather than asset_patterns. Asset patterns are for filtering release assets.
                # However, if someone explicitly includes source-specific keywords like 'tarball' or 'zipball'
                # in asset_patterns, we treat these as filters for source archive types.
                should_skip_archive = False
                if asset_patterns:
                    # Check for explicit source type filters
                    has_tarball_filter = 'tarball' in [p.lower() for p in asset_patterns]
                    has_zipball_filter = 'zipball' in [p.lower() for p in asset_patterns]

                    # If specific source type filters are present, only download matching types
                    if has_tarball_filter or has_zipball_filter:
                        if archive['type'] == 'tarball' and not has_tarball_filter:
                            should_skip_archive = True
                        elif archive['type'] == 'zipball' and not has_zipball_filter:
                            should_skip_archive = True

                if should_skip_archive:
                    logger.debug(f"Skipping source archive {archive['name']} (type {archive['type']} not in explicit filters)")
                    continue

                # Create a pseudo-asset for the source archive
                pseudo_asset = {
                    'name': archive['name'],
                    'browser_download_url': archive['url'],
                    'size': None  # GitHub doesn't provide size for source archives
                }

                # Download the source archive
                result = self._download_single_asset(pseudo_asset, release_dir, release_data)
                result['source_type'] = archive['type']  # Mark as source archive
                download_results.append(result)

            except Exception as e:
                logger.error(f"Failed to download source archive {archive['name']}: {e}")
                download_results.append({
                    'asset_name': archive['name'],
                    'source_type': archive['type'],
                    'success': False,
                    'error': str(e),
                    'download_time': time.time()
                })

        if download_results:
            successful = sum(1 for r in download_results if r['success'])
            logger.info(f"Downloaded {successful} of {len(download_results)} source archives for {repo_name}:{tag_name}")

        return download_results
