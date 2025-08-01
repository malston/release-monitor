#!/usr/bin/env python3
"""
GitHub Release Download Script

Main script that coordinates the download process:
1. Reads monitor output
2. Compares versions
3. Downloads new releases
4. Updates version database
"""

import os
import sys
import json
import yaml
import argparse
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from github_version_db import VersionDatabase
from version_compare import VersionComparator
from github_downloader import GitHubDownloader

# Configure logging
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ReleaseDownloadCoordinator:
    """
    Coordinates the release download process with version tracking.
    """

    def __init__(self, config: Dict[str, Any], github_token: str, force_local: bool = False):
        """
        Initialize download coordinator.

        Args:
            config: Download configuration
            github_token: GitHub API token
            force_local: Force local storage, bypassing S3/Artifactory auto-detection
        """
        self.config = config
        self.github_token = github_token

        # Initialize components
        download_config = config.get('download', {})

        # Check storage backend configuration
        s3_config = download_config.get('s3_storage', {})
        artifactory_config = download_config.get('artifactory_storage', {})
        use_s3 = s3_config.get('enabled', False)
        use_artifactory = artifactory_config.get('enabled', False)

        if force_local:
            logger.info("Forcing local storage for downloads (--force-download flag)")
            use_s3 = False
            use_artifactory = False
        else:
            # Auto-detect S3 usage if environment variables are present
            if not use_s3 and os.environ.get('VERSION_DB_S3_BUCKET'):
                use_s3 = True
                logger.info("Auto-detected S3 version database from VERSION_DB_S3_BUCKET environment variable")

            # Auto-detect Artifactory usage if environment variables are present
            if not use_artifactory and os.environ.get('ARTIFACTORY_URL') and os.environ.get('ARTIFACTORY_REPOSITORY'):
                use_artifactory = True
                logger.info("Auto-detected Artifactory version database from ARTIFACTORY_URL and ARTIFACTORY_REPOSITORY environment variables")

        # Priority: Artifactory > S3 > local
        if use_artifactory:
            # Use Artifactory version storage
            from github_version_artifactory import ArtifactoryVersionDatabase
            self.version_db = ArtifactoryVersionDatabase(
                base_url=os.environ.get('ARTIFACTORY_URL') or artifactory_config.get('base_url'),
                repository=os.environ.get('ARTIFACTORY_REPOSITORY') or artifactory_config.get('repository'),
                path_prefix=artifactory_config.get('path_prefix', 'release-monitor/'),
                username=os.environ.get('ARTIFACTORY_USERNAME') or artifactory_config.get('username'),
                password=os.environ.get('ARTIFACTORY_PASSWORD') or artifactory_config.get('password'),
                api_key=os.environ.get('ARTIFACTORY_API_KEY') or artifactory_config.get('api_key'),
                verify_ssl=artifactory_config.get('verify_ssl', True) and os.environ.get('ARTIFACTORY_SKIP_SSL_VERIFICATION', 'false').lower() != 'true'
            )
            logger.info(f"Using Artifactory version storage: {os.environ.get('ARTIFACTORY_URL') or artifactory_config.get('base_url')}")
        elif use_s3:
            # Check if we should use mc-based S3 implementation
            use_mc_s3 = os.environ.get('S3_USE_MC', 'true').lower() == 'true'

            if use_mc_s3:
                # Try to use mc-based S3 version storage for better compatibility
                try:
                    from github_version_s3_mc import S3VersionDatabase
                    self.version_db = S3VersionDatabase(
                        bucket=s3_config.get('bucket'),
                        key_prefix=s3_config.get('prefix', 'release-monitor/')
                    )
                    logger.info(f"Using mc-based S3 version storage: s3://{s3_config.get('bucket')}/{s3_config.get('prefix', 'release-monitor/')}version_db.json")
                except ImportError:
                    logger.warning("mc-based S3 implementation not available, falling back to boto3")
                    use_mc_s3 = False

            if not use_mc_s3:
                # Check if we should use S3-compatible storage (for MinIO, etc.)
                endpoint_url = s3_config.get('endpoint_url') or os.environ.get('AWS_ENDPOINT_URL')

                # Set endpoint URL for boto3 before importing S3 modules
                if endpoint_url:
                    os.environ['AWS_ENDPOINT_URL_S3'] = endpoint_url

                # Use boto3-based S3 version storage
                from github_version_s3 import VersionDatabase as S3VersionDatabase
                self.version_db = S3VersionDatabase(
                    use_s3=True,
                    s3_bucket=s3_config.get('bucket'),
                    s3_prefix=s3_config.get('prefix', 'release-monitor/'),
                    aws_region=s3_config.get('region'),
                    aws_profile=s3_config.get('profile')
                )

                endpoint_info = f" via {endpoint_url}" if endpoint_url else ""
                logger.info(f"Using boto3-based S3 version storage: s3://{s3_config.get('bucket')}/{s3_config.get('prefix', 'release-monitor/')}version_db.json{endpoint_info}")
        else:
            # Use local file storage
            self.version_db = VersionDatabase(
                download_config.get('version_db', 'version_db.json')
            )

        self.version_comparator = VersionComparator(
            include_prereleases=download_config.get('include_prereleases', False),
            strict_prerelease_filtering=download_config.get('strict_prerelease_filtering', False)
        )

        self.downloader = GitHubDownloader(
            token=github_token,
            download_dir=download_config.get('directory', 'downloads'),
            timeout=download_config.get('timeout', 300)
        )

        # Download settings
        self.asset_patterns = download_config.get('asset_patterns', [])
        self.verify_downloads = download_config.get('verify_downloads', True)
        self.cleanup_enabled = download_config.get('cleanup_old_versions', False)
        self.keep_versions = download_config.get('keep_versions', 5)

        # Source archive settings
        self.source_config = download_config.get('source_archives', {
            'enabled': True,
            'prefer': 'tarball',
            'fallback_only': True
        })

        # Repository overrides
        self.repository_overrides = download_config.get('repository_overrides', {})

        logger.info("Release download coordinator initialized")

    def process_monitor_output(self, monitor_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process monitor output and download new releases.

        Args:
            monitor_output: Output from GitHub monitor

        Returns:
            Download processing results
        """
        start_time = time.time()

        results = {
            'timestamp': time.time(),
            'total_releases_checked': 0,
            'new_downloads': 0,
            'skipped_releases': 0,
            'failed_downloads': 0,
            'download_results': [],
            'errors': []
        }

        if not monitor_output.get('releases'):
            logger.info("No releases found in monitor output")
            return results

        logger.info(f"Processing {len(monitor_output['releases'])} releases from monitor")

        for release in monitor_output['releases']:
            try:
                result = self._process_single_release(release)
                results['download_results'].append(result)
                results['total_releases_checked'] += 1

                if result['action'] == 'downloaded':
                    results['new_downloads'] += 1
                elif result['action'] == 'skipped':
                    results['skipped_releases'] += 1
                elif result['action'] == 'failed':
                    results['failed_downloads'] += 1

            except Exception as e:
                error_msg = f"Error processing release {release.get('repository', 'unknown')}: {e}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
                results['failed_downloads'] += 1

        # Cleanup old versions if enabled
        if self.cleanup_enabled:
            try:
                cleanup_stats = self.downloader.cleanup_old_downloads(self.keep_versions)
                results['cleanup_stats'] = cleanup_stats
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")

        results['processing_time'] = time.time() - start_time

        logger.info(f"Processing complete: {results['new_downloads']} downloaded, "
                   f"{results['skipped_releases']} skipped, {results['failed_downloads']} failed "
                   f"in {results['processing_time']:.1f}s")

        return results

    def _process_single_release(self, release: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single release for potential download.

        Args:
            release: Release data from monitor

        Returns:
            Processing result for this release
        """
        repository = release.get('repository', 'unknown')
        tag_name = release.get('tag_name', 'unknown')

        # Parse repository owner/name
        if '/' in repository:
            owner, repo = repository.split('/', 1)
        else:
            logger.warning(f"Invalid repository format: {repository}")
            return {
                'repository': repository,
                'tag_name': tag_name,
                'action': 'failed',
                'reason': 'Invalid repository format'
            }

        logger.debug(f"Processing {repository}:{tag_name}")

        # Get current stored version
        current_version = self.version_db.get_current_version(owner, repo)

        # Get repository-specific configuration to check for target version
        repo_override = self.repository_overrides.get(repository, {})
        target_version = repo_override.get('target_version')

        if target_version:
            # Target version specified - always download regardless of stored version
            logger.info(f"Target version {target_version} specified for {repository}, bypassing version comparison")
        else:
            # No target version - check if this version is newer
            github_prerelease = release.get('prerelease')  # Get GitHub's official prerelease flag
            if not self.version_comparator.is_newer(tag_name, current_version, github_prerelease):
                reason = f"Version {tag_name} is not newer than {current_version}"
                logger.debug(f"Skipping {repository}: {reason}")
                return {
                    'repository': repository,
                    'tag_name': tag_name,
                    'current_version': current_version,
                    'action': 'skipped',
                    'reason': reason
                }

        # Check if release has downloadable content (assets or source code)
        has_assets = bool(release.get('assets'))
        has_source = bool(release.get('tarball_url') or release.get('zipball_url'))

        if not has_assets and not has_source:
            logger.debug(f"No downloadable content found for {repository}:{tag_name}")
            return {
                'repository': repository,
                'tag_name': tag_name,
                'current_version': current_version,
                'action': 'skipped',
                'reason': 'No downloadable content (no assets or source archives)'
            }

        # Get repository-specific configuration
        repo_config = self._get_repository_config(repository)

        # Download the release assets and/or source code
        try:
            download_results = self.downloader.download_release_content(
                release, repo_config.get('asset_patterns', self.asset_patterns),
                repo_config.get('source_archives', self.source_config)
            )

            successful_downloads = [r for r in download_results if r['success']]

            if successful_downloads:
                # Update version database
                download_metadata = {
                    'download_count': len(successful_downloads),
                    'total_assets': len(download_results),
                    'downloaded_files': [r['file_path'] for r in successful_downloads],
                    'download_time': sum(r.get('download_time', 0) for r in successful_downloads),
                    'total_size': sum(r.get('file_size', 0) for r in successful_downloads)
                }

                self.version_db.update_version(owner, repo, tag_name, download_metadata)

                logger.info(f"Successfully downloaded {len(successful_downloads)} assets "
                           f"for {repository}:{tag_name}")

                return {
                    'repository': repository,
                    'tag_name': tag_name,
                    'previous_version': current_version,
                    'action': 'downloaded',
                    'download_results': download_results,
                    'metadata': download_metadata
                }
            else:
                # All downloads failed
                return {
                    'repository': repository,
                    'tag_name': tag_name,
                    'current_version': current_version,
                    'action': 'failed',
                    'reason': 'All asset downloads failed',
                    'download_results': download_results
                }

        except Exception as e:
            logger.error(f"Error downloading {repository}:{tag_name}: {e}")
            return {
                'repository': repository,
                'tag_name': tag_name,
                'current_version': current_version,
                'action': 'failed',
                'reason': f"Download error: {str(e)}"
            }

    def _get_repository_config(self, repository: str) -> Dict[str, Any]:
        """
        Get repository-specific configuration with fallbacks.

        Args:
            repository: Repository name in owner/repo format

        Returns:
            Repository configuration with merged overrides
        """
        repo_override = self.repository_overrides.get(repository, {})

        # Merge with defaults
        config = {
            'asset_patterns': repo_override.get('asset_patterns', self.asset_patterns),
            'source_archives': {**self.source_config, **repo_override.get('source_archives', {})}
        }

        return config

    def get_status_report(self) -> Dict[str, Any]:
        """
        Get status report of the download system.

        Returns:
            Status report with statistics
        """
        db_stats = self.version_db.get_database_stats()
        download_stats = self.downloader.get_download_stats()

        return {
            'database_stats': db_stats,
            'download_stats': download_stats,
            'config': {
                'download_directory': self.downloader.download_dir,
                'asset_patterns': self.asset_patterns,
                'include_prereleases': self.version_comparator.include_prereleases,
                'cleanup_enabled': self.cleanup_enabled,
                'keep_versions': self.keep_versions
            }
        }


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def load_monitor_output(input_source: str) -> Dict[str, Any]:
    """Load monitor output from file or stdin."""
    if input_source == '-':
        # Read from stdin
        data = sys.stdin.read()
    else:
        # Read from file
        with open(input_source, 'r') as f:
            data = f.read()

    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON input: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Download GitHub releases based on monitor output'
    )

    parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Configuration file path'
    )

    parser.add_argument(
        '--input', '-i',
        default='-',
        help='Monitor output file (- for stdin)'
    )

    parser.add_argument(
        '--output', '-o',
        help='Output file for download results (default: stdout)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be downloaded without actually downloading'
    )

    parser.add_argument(
        '--status',
        action='store_true',
        help='Show status report and exit'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        logger.error(f"Error loading config {args.config}: {e}")
        sys.exit(1)

    # Get GitHub token
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        logger.error("GITHUB_TOKEN environment variable is required")
        sys.exit(1)

    # Initialize coordinator
    coordinator = ReleaseDownloadCoordinator(config, github_token)

    # Handle status request
    if args.status:
        status = coordinator.get_status_report()
        output = json.dumps(status, indent=2)

        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            logger.info(f"Status report written to {args.output}")
        else:
            print(output)
        return

    # Load monitor output
    try:
        monitor_output = load_monitor_output(args.input)
    except Exception as e:
        logger.error(f"Error loading monitor output: {e}")
        sys.exit(1)

    # Process releases
    if args.dry_run:
        logger.info("DRY RUN MODE - No actual downloads will be performed")
        # TODO: Implement dry run logic
        results = {'dry_run': True, 'message': 'Dry run mode not yet implemented'}
    else:
        results = coordinator.process_monitor_output(monitor_output)

    # Output results
    output = json.dumps(results, indent=2, default=str)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        logger.info(f"Results written to {args.output}")
    else:
        print(output)


if __name__ == '__main__':
    main()
