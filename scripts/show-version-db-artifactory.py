#!/usr/bin/env python3
"""
View the contents of the Artifactory version database.

Usage:
    python3 show-version-db-artifactory.py
"""

import os
import sys
import json
import requests
from datetime import datetime


def main():
    """View the current version database from Artifactory."""

    # Required environment variables
    artifactory_url = os.environ.get('ARTIFACTORY_URL')
    if not artifactory_url:
        print("ERROR: ARTIFACTORY_URL environment variable not set")
        sys.exit(1)

    repository = os.environ.get('ARTIFACTORY_REPOSITORY')
    if not repository:
        print("ERROR: ARTIFACTORY_REPOSITORY environment variable not set")
        sys.exit(1)

    api_key = os.environ.get('ARTIFACTORY_API_KEY')
    if not api_key:
        print("ERROR: ARTIFACTORY_API_KEY environment variable not set")
        sys.exit(1)

    # SSL verification
    verify_ssl = os.environ.get('ARTIFACTORY_SKIP_SSL_VERIFICATION', 'false').lower() != 'true'
    if not verify_ssl:
        print("WARNING: Skipping SSL verification for Artifactory endpoint")
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    print(f"Connecting to Artifactory at {artifactory_url}...")

    # Download version database
    url = f"{artifactory_url.rstrip('/')}/{repository}/release-monitor/version_db.json"
    headers = {'Authorization': f'Bearer {api_key}'}

    try:
        print(f"Fetching version database from: {url}")
        response = requests.get(url, headers=headers, verify=verify_ssl)

        if response.status_code == 404:
            print("No version database found in Artifactory")
            print(f"Expected location: {url}")
            return

        response.raise_for_status()
        version_data = response.json()

        print(f"\nVersion database from Artifactory")
        print("=" * 70)

        # Show metadata
        metadata = version_data.get('metadata', {})
        print(f"Version: {metadata.get('version', 'unknown')}")
        print(f"Storage: {metadata.get('storage', 'unknown')}")
        print(f"Created: {metadata.get('created_at', 'unknown')}")
        print(f"Last updated: {metadata.get('last_updated', 'unknown')}")

        # Show repositories
        print("\nTracked repositories:")
        print("-" * 70)

        repos = version_data.get('repositories', {})
        if not repos:
            print("  No repositories tracked yet")
        else:
            for repo_key, repo_data in sorted(repos.items()):
                version = repo_data.get('current_version', 'unknown')
                last_updated = repo_data.get('last_updated', 'unknown')
                created_at = repo_data.get('created_at', 'unknown')

                print(f"\n  {repo_key}:")
                print(f"    Current version: {version}")
                print(f"    Created: {created_at}")
                print(f"    Last updated: {last_updated}")

                # Show recent downloads if any
                download_history = repo_data.get('download_history', [])
                if download_history:
                    print(f"    Download history ({len(download_history)} entries):")
                    for dl in download_history[-3:]:  # Show last 3
                        dl_version = dl.get('version', 'unknown')
                        dl_time = dl.get('downloaded_at', 'unknown')
                        print(f"      - {dl_version} at {dl_time}")

        print(f"\nTotal repositories: {len(repos)}")

    except requests.exceptions.RequestException as e:
        print(f'Error fetching version database: {e}')
        if hasattr(e, 'response') and e.response:
            print(f'Response status: {e.response.status_code}')
            print(f'Response text: {e.response.text}')
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f'Error parsing JSON response: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
