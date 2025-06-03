#!/usr/bin/env python3
"""
GitHub Repository Release Monitoring Script

This script monitors GitHub repositories for new releases and outputs
structured information about available updates. Designed for use in
Concourse CI/CD pipelines.
"""

import os
import sys
import json
import yaml
import time
import argparse
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GitHubMonitor:
    """GitHub repository release monitoring client"""

    def __init__(self, token: str, rate_limit_delay: float = 1.0):
        """
        Initialize GitHub monitor

        Args:
            token: GitHub API token
            rate_limit_delay: Delay between API calls in seconds
        """
        self.token = token
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Release-Monitor/1.0'
        })

    def get_latest_release(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest release information for a repository

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Latest release information or None if no releases
        """
        url = f'https://api.github.com/repos/{owner}/{repo}/releases/latest'

        try:
            # Add rate limiting delay
            time.sleep(self.rate_limit_delay)

            response = self.session.get(url)

            # Handle rate limiting
            if response.status_code == 403 and 'rate limit' in response.text.lower():
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                wait_time = max(0, reset_time - int(time.time())) + 60
                logger.warning(f"Rate limit hit. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                response = self.session.get(url)

            if response.status_code == 404:
                logger.warning(f"No releases found for {owner}/{repo}")
                return None

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching release for {owner}/{repo}: {e}")
            raise

    def get_all_releases(self, owner: str, repo: str, per_page: int = 10) -> List[Dict[str, Any]]:
        """
        Get all releases for a repository

        Args:
            owner: Repository owner
            repo: Repository name
            per_page: Number of releases per page

        Returns:
            List of release information
        """
        url = f'https://api.github.com/repos/{owner}/{repo}/releases'
        params = {'per_page': per_page}

        try:
            time.sleep(self.rate_limit_delay)
            response = self.session.get(url, params=params)

            if response.status_code == 403 and 'rate limit' in response.text.lower():
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                wait_time = max(0, reset_time - int(time.time())) + 60
                logger.warning(f"Rate limit hit. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                response = self.session.get(url, params=params)

            if response.status_code == 404:
                logger.warning(f"No releases found for {owner}/{repo}")
                return []

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching releases for {owner}/{repo}: {e}")
            return []


class ReleaseTracker:
    """Tracks release timestamps and manages state"""

    def __init__(self, state_file: str = 'release_state.json'):
        """
        Initialize release tracker

        Args:
            state_file: Path to state file for tracking last checked timestamps
        """
        self.state_file = state_file
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Load state from file"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load state file: {e}")

        return {'repositories': {}, 'last_run': None}

    def _save_state(self):
        """Save state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except IOError as e:
            logger.error(f"Could not save state file: {e}")

    def get_last_checked(self, repo_key: str) -> Optional[datetime]:
        """Get last checked timestamp for repository"""
        timestamp = self.state['repositories'].get(repo_key, {}).get('last_checked')
        if timestamp:
            return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return None

    def update_last_checked(self, repo_key: str, timestamp: datetime):
        """Update last checked timestamp for repository"""
        if repo_key not in self.state['repositories']:
            self.state['repositories'][repo_key] = {}

        self.state['repositories'][repo_key]['last_checked'] = timestamp.isoformat()
        self.state['last_run'] = datetime.now(timezone.utc).isoformat()
        self._save_state()

    def has_new_release(self, repo_key: str, release_date: datetime) -> bool:
        """Check if release is newer than last checked timestamp"""
        last_checked = self.get_last_checked(repo_key)
        if not last_checked:
            return True
        return release_date > last_checked


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except (yaml.YAMLError, IOError) as e:
        logger.error(f"Could not load config file: {e}")
        sys.exit(1)


def parse_release_date(date_string: str) -> datetime:
    """Parse ISO date string to datetime object"""
    return datetime.fromisoformat(date_string.replace('Z', '+00:00'))


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Monitor GitHub repositories for new releases')
    parser.add_argument('--config', '-c', required=True, help='Path to configuration file')
    parser.add_argument('--output', '-o', help='Output file path (stdout if not specified)')
    parser.add_argument('--format', '-f', choices=['json', 'yaml'], default='json', help='Output format')
    parser.add_argument('--state-file', '-s', default='release_state.json', help='State file path')
    parser.add_argument('--force-check', action='store_true', help='Check all releases regardless of last checked time')
    parser.add_argument('--download', action='store_true', help='Download new releases after monitoring (requires download configuration)')

    args = parser.parse_args()

    # Get GitHub token from environment
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        logger.error("GITHUB_TOKEN environment variable is required")
        sys.exit(1)

    # Load configuration
    config = load_config(args.config)
    repositories = config.get('repositories', [])

    if not repositories:
        logger.error("No repositories configured")
        sys.exit(1)

    # Check download configuration if download is requested
    download_config = config.get('download', {})
    if args.download and not download_config.get('enabled', False):
        logger.error("Download requested but not enabled in configuration")
        sys.exit(1)

    # Initialize components
    monitor = GitHubMonitor(github_token)
    tracker = ReleaseTracker(args.state_file)

    new_releases = []

    logger.info(f"Checking {len(repositories)} repositories for new releases...")

    for repo_config in repositories:
        owner = repo_config['owner']
        repo = repo_config['repo']
        repo_key = f"{owner}/{repo}"

        logger.info(f"Checking {repo_key}...")

        try:
            latest_release = monitor.get_latest_release(owner, repo)
            if not latest_release:
                continue
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to check {repo_key}: {e}")
            # Check if we should exit on API errors or continue
            # You can customize this behavior - for now, we'll exit on API errors
            # to ensure pipeline failures are detected
            logger.error("Exiting due to API error. Set CONTINUE_ON_API_ERROR=true to skip failed repos.")
            if os.getenv('CONTINUE_ON_API_ERROR', '').lower() == 'true':
                logger.warning(f"Skipping {repo_key} due to API error (CONTINUE_ON_API_ERROR is set)")
                continue
            else:
                sys.exit(1)

        release_date = parse_release_date(latest_release['published_at'])

        # Check if this is a new release
        if args.force_check or tracker.has_new_release(repo_key, release_date):
            release_info = {
                'repository': repo_key,
                'owner': owner,
                'repo': repo,
                'tag_name': latest_release['tag_name'],
                'name': latest_release['name'],
                'published_at': latest_release['published_at'],
                'tarball_url': latest_release['tarball_url'],
                'zipball_url': latest_release['zipball_url'],
                'html_url': latest_release['html_url'],
                'prerelease': latest_release['prerelease'],
                'draft': latest_release['draft'],
                'assets': latest_release.get('assets', [])  # Include assets for download
            }

            new_releases.append(release_info)
            logger.info(f"New release found: {repo_key} {latest_release['tag_name']}")

        # Update last checked timestamp
        tracker.update_last_checked(repo_key, datetime.now(timezone.utc))

    # Prepare output
    output_data = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'total_repositories_checked': len(repositories),
        'new_releases_found': len(new_releases),
        'releases': new_releases
    }

    # Download new releases if requested
    if args.download and new_releases:
        try:
            # Import download functionality (lazy import to avoid dependency when not needed)
            from download_releases import ReleaseDownloadCoordinator

            logger.info(f"Starting downloads for {len(new_releases)} new releases...")

            # Initialize download coordinator
            coordinator = ReleaseDownloadCoordinator(config, github_token)

            # Process the releases for download
            download_results = coordinator.process_monitor_output(output_data)

            # Add download results to output
            output_data['download_results'] = download_results

            logger.info(f"Downloads complete: {download_results['new_downloads']} downloaded, "
                       f"{download_results['skipped_releases']} skipped, "
                       f"{download_results['failed_downloads']} failed")

        except ImportError as e:
            logger.error(f"Download functionality not available: {e}")
            output_data['download_error'] = "Download modules not found"
        except Exception as e:
            logger.error(f"Download error: {e}")
            output_data['download_error'] = str(e)

    # Output results
    if args.format == 'yaml':
        output_content = yaml.dump(output_data, default_flow_style=False)
    else:
        output_content = json.dumps(output_data, indent=2)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output_content)
        logger.info(f"Results written to {args.output}")
    else:
        print(output_content)

    logger.info(f"Monitoring complete. Found {len(new_releases)} new releases.")


if __name__ == '__main__':
    main()
