#!/usr/bin/env python3
"""
Download releases from JFrog Artifactory

This script downloads release artifacts that have been uploaded to Artifactory
by the release-monitor pipeline. It uses the Storage API which is available
in both Artifactory OSS and Pro versions.

Usage:
    python3 download-from-artifactory.py [options]

Environment Variables:
    ARTIFACTORY_URL: Base URL of Artifactory (e.g., http://localhost:8081/artifactory)
    ARTIFACTORY_REPOSITORY: Repository name (e.g., generic-releases)
    ARTIFACTORY_USERNAME: Username for authentication (optional)
    ARTIFACTORY_PASSWORD: Password for authentication (optional)
    ARTIFACTORY_API_KEY: API key for authentication (optional)

Examples:
    # Download all releases
    python3 download-from-artifactory.py

    # Download specific repository
    python3 download-from-artifactory.py --repo kubernetes/kubernetes

    # Download with pattern matching
    python3 download-from-artifactory.py --pattern "*linux-amd64*"

    # List available repositories with versions
    python3 download-from-artifactory.py --list

    # List repositories with detailed version and file information
    python3 download-from-artifactory.py --list-detailed

    # List only repository names (fastest)
    python3 download-from-artifactory.py --list-repos-only
"""

import os
import sys
import argparse
import requests
from pathlib import Path
import logging
from typing import Dict, List, Optional, Any


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ArtifactoryDownloader:
    """Download artifacts from JFrog Artifactory using Storage API."""

    def __init__(self, base_url: str, repository: str, username: Optional[str] = None,
                 password: Optional[str] = None, api_key: Optional[str] = None,
                 verify_ssl: bool = True):
        """Initialize downloader."""
        self.base_url = base_url.rstrip('/')
        self.repository = repository
        self.verify_ssl = verify_ssl

        # Set up authentication
        self.session = requests.Session()
        if api_key:
            self.session.headers['Authorization'] = f'Bearer {api_key}'
            logger.info("Using API key authentication")
        elif username and password:
            self.session.auth = (username, password)
            logger.info("Using username/password authentication")
        else:
            logger.warning("No authentication configured")

        if not verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def list_folder(self, path: str = "") -> Dict[str, Any]:
        """List contents of a folder using Storage API."""
        if path:
            url = f"{self.base_url}/api/storage/{self.repository}/{path}"
        else:
            url = f"{self.base_url}/api/storage/{self.repository}"

        try:
            response = self.session.get(url, verify=self.verify_ssl)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list {path}: {e}")
            return {}

    def download_file(self, file_path: str, output_dir: str) -> bool:
        """Download a single file."""
        url = f"{self.base_url}/{self.repository}/{file_path}"

        # Create output path
        output_path = Path(output_dir) / file_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Skip if already exists
        if output_path.exists():
            logger.info(f"Skipping {file_path} - already downloaded")
            return True

        try:
            logger.info(f"Downloading {file_path}")
            response = self.session.get(url, stream=True, verify=self.verify_ssl)
            response.raise_for_status()

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            logger.info(f"  → Saved to: {output_path}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download {file_path}: {e}")
            return False

    def list_releases(self) -> List[str]:
        """List all available releases."""
        releases = []

        # List release-downloads folder
        folder_data = self.list_folder("release-downloads")
        if not folder_data.get('children'):
            logger.warning("No releases found in release-downloads folder")
            return releases

        for item in folder_data['children']:
            if item.get('folder'):
                repo_name = item['uri'].strip('/')
                # Convert underscore back to slash for display
                display_name = repo_name.replace('_', '/')
                releases.append(display_name)

        return sorted(releases)

    def list_repository_versions(self, repo_name: str) -> List[str]:
        """List all versions for a specific repository."""
        versions = []

        # Convert slash to underscore for folder name
        folder_name = repo_name.replace('/', '_')

        # List repository folder
        repo_data = self.list_folder(f"release-downloads/{folder_name}")
        if not repo_data.get('children'):
            return versions

        for version_item in repo_data['children']:
            if version_item.get('folder'):
                version = version_item['uri'].strip('/')
                versions.append(version)

        return sorted(versions, reverse=True)  # Show newest versions first

    def get_version_file_count(self, repo_name: str, version: str) -> int:
        """Get the number of files in a specific version."""
        folder_name = repo_name.replace('/', '_')
        version_path = f"release-downloads/{folder_name}/{version}"

        version_data = self.list_folder(version_path)
        if not version_data.get('children'):
            return 0

        # Count non-folder items (files)
        file_count = sum(1 for item in version_data['children'] if not item.get('folder'))
        return file_count

    def list_releases_with_versions(self) -> Dict[str, List[str]]:
        """List all releases with their available versions."""
        releases_with_versions = {}

        # Get all repositories
        releases = self.list_releases()

        for repo in releases:
            versions = self.list_repository_versions(repo)
            releases_with_versions[repo] = versions

        return releases_with_versions

    def download_repository(self, repo_name: str, output_dir: str, pattern: Optional[str] = None) -> int:
        """Download all artifacts for a repository."""
        # Convert slash to underscore for folder name
        folder_name = repo_name.replace('/', '_')
        downloaded = 0

        # List repository folder
        repo_data = self.list_folder(f"release-downloads/{folder_name}")
        if not repo_data.get('children'):
            logger.warning(f"No versions found for {repo_name}")
            return 0

        # Iterate through versions
        for version_item in repo_data['children']:
            if version_item.get('folder'):
                version = version_item['uri'].strip('/')
                version_path = f"release-downloads/{folder_name}/{version}"

                # List files in version folder
                version_data = self.list_folder(version_path)
                if version_data.get('children'):
                    for file_item in version_data['children']:
                        if not file_item.get('folder'):
                            file_name = file_item['uri'].strip('/')
                            file_path = f"{version_path}/{file_name}"

                            # Apply pattern filter if specified
                            if pattern:
                                import fnmatch
                                if not fnmatch.fnmatch(file_name, pattern):
                                    continue

                            if self.download_file(file_path, output_dir):
                                downloaded += 1

        return downloaded

    def download_all(self, output_dir: str, pattern: Optional[str] = None) -> int:
        """Download all available releases."""
        releases = self.list_releases()
        total_downloaded = 0

        for repo in releases:
            logger.info(f"\nDownloading {repo}...")
            downloaded = self.download_repository(repo, output_dir, pattern)
            total_downloaded += downloaded
            logger.info(f"Downloaded {downloaded} files from {repo}")

        return total_downloaded


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Download releases from JFrog Artifactory',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--url',
        default=os.environ.get('ARTIFACTORY_URL', 'http://localhost:8081/artifactory'),
        help='Artifactory base URL'
    )

    parser.add_argument(
        '--repository',
        default=os.environ.get('ARTIFACTORY_REPOSITORY', 'generic-releases'),
        help='Repository name'
    )

    parser.add_argument(
        '--username',
        default=os.environ.get('ARTIFACTORY_USERNAME'),
        help='Username for authentication'
    )

    parser.add_argument(
        '--password',
        default=os.environ.get('ARTIFACTORY_PASSWORD'),
        help='Password for authentication'
    )

    parser.add_argument(
        '--api-key',
        default=os.environ.get('ARTIFACTORY_API_KEY'),
        help='API key for authentication'
    )

    parser.add_argument(
        '--repo',
        help='Download specific repository (e.g., kubernetes/kubernetes)'
    )

    parser.add_argument(
        '--pattern',
        help='File pattern to match (e.g., "*.tar.gz")'
    )

    parser.add_argument(
        '--output-dir',
        default='./artifactory-downloads',
        help='Output directory'
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List available repositories with their versions'
    )

    parser.add_argument(
        '--list-repos-only',
        action='store_true',
        help='List only repository names (faster, no version details)'
    )

    parser.add_argument(
        '--list-detailed',
        action='store_true',
        help='List repositories with versions and file counts (slower but more detailed)'
    )

    parser.add_argument(
        '--no-verify-ssl',
        action='store_true',
        help='Skip SSL certificate verification'
    )

    args = parser.parse_args()

    # Create downloader
    downloader = ArtifactoryDownloader(
        base_url=args.url,
        repository=args.repository,
        username=args.username,
        password=args.password,
        api_key=args.api_key,
        verify_ssl=not args.no_verify_ssl
    )

    # List repositories
    if args.list or args.list_repos_only or args.list_detailed:
        if args.list_repos_only:
            logger.info("Listing available repositories...")
            releases = downloader.list_releases()

            if releases:
                print("\nAvailable repositories:")
                for repo in releases:
                    print(f"  - {repo}")
            else:
                print("\nNo repositories found")
        elif args.list_detailed:
            logger.info("Listing available repositories with versions and file counts...")
            releases_with_versions = downloader.list_releases_with_versions()

            if releases_with_versions:
                print("\nDetailed repository listing:")
                print("=" * 60)
                for repo, versions in releases_with_versions.items():
                    print(f"\n📦 {repo}")
                    if versions:
                        print(f"   Versions ({len(versions)}):")
                        for version in versions:
                            file_count = downloader.get_version_file_count(repo, version)
                            print(f"     • {version} ({file_count} files)")
                    else:
                        print("   No versions found")
                print("\n" + "=" * 60)
                total_repos = len(releases_with_versions)
                total_versions = sum(len(versions) for versions in releases_with_versions.values())
                total_files = sum(
                    downloader.get_version_file_count(repo, version)
                    for repo, versions in releases_with_versions.items()
                    for version in versions
                )
                print(f"Summary: {total_repos} repositories, {total_versions} total versions, {total_files} total files")
            else:
                print("\nNo repositories found")
        else:
            logger.info("Listing available repositories with versions...")
            releases_with_versions = downloader.list_releases_with_versions()

            if releases_with_versions:
                print("\nAvailable repositories and versions:")
                print("=" * 50)
                for repo, versions in releases_with_versions.items():
                    print(f"\n📦 {repo}")
                    if versions:
                        print(f"   Versions ({len(versions)}): ", end="")
                        # Show first 5 versions inline, rest on separate lines if many
                        if len(versions) <= 5:
                            print(", ".join(versions))
                        else:
                            print(f"{len(versions)} versions available")
                            print("   Latest 5:", ", ".join(versions[:5]))
                            if len(versions) > 5:
                                print(f"   ... and {len(versions) - 5} more")
                    else:
                        print("   No versions found")
                print("\n" + "=" * 50)
                total_repos = len(releases_with_versions)
                total_versions = sum(len(versions) for versions in releases_with_versions.values())
                print(f"Summary: {total_repos} repositories, {total_versions} total versions")
            else:
                print("\nNo repositories found")
        return 0

    # Download artifacts
    logger.info(f"Downloading to: {args.output_dir}")

    if args.repo:
        # Download specific repository
        downloaded = downloader.download_repository(args.repo, args.output_dir, args.pattern)
    else:
        # Download all
        downloaded = downloader.download_all(args.output_dir, args.pattern)

    logger.info(f"\nDownload complete! Downloaded {downloaded} artifacts")
    logger.info(f"Files saved to: {os.path.abspath(args.output_dir)}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
