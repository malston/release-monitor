#!/usr/bin/env python3
"""
Fetch monitor output (latest-releases.json) from Artifactory.

This script downloads the latest-releases.json file from Artifactory
for use in downstream pipeline tasks.
"""

import os
import requests
import sys
import argparse
from pathlib import Path


def fetch_monitor_output(output_dir='/monitor-output'):
    """Fetch the latest monitor output from Artifactory."""

    # Get configuration from environment
    artifactory_url = os.environ['ARTIFACTORY_URL']
    repository = os.environ['ARTIFACTORY_REPOSITORY']
    api_key = os.environ.get('ARTIFACTORY_API_KEY')
    username = os.environ.get('ARTIFACTORY_USERNAME')
    password = os.environ.get('ARTIFACTORY_PASSWORD')
    verify_ssl = os.environ.get('ARTIFACTORY_SKIP_SSL_VERIFICATION', 'false').lower() != 'true'

    if not verify_ssl:
        print("WARNING: Skipping SSL verification for Artifactory endpoint")
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Setup authentication - prefer API key over username/password
    headers = {}
    auth = None

    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
        print("Using API key authentication")
    elif username and password:
        from requests.auth import HTTPBasicAuth
        auth = HTTPBasicAuth(username, password)
        print(f"Using username/password authentication for user: {username}")
    else:
        print("ERROR: No authentication credentials found.")
        print("Set ARTIFACTORY_API_KEY or ARTIFACTORY_USERNAME/ARTIFACTORY_PASSWORD")
        sys.exit(1)

    # Build URL
    url = f'{artifactory_url.rstrip("/")}/{repository}/release-monitor/latest-releases.json'
    print(f'Fetching monitor output from: {url}')

    try:
        response = requests.get(url, headers=headers, auth=auth, verify=verify_ssl)
        response.raise_for_status()

        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Write to output directory
        output_file = output_path / 'latest-releases.json'
        with open(output_file, 'w') as f:
            f.write(response.text)

        print(f'Successfully downloaded latest-releases.json to {output_file}')

    except requests.exceptions.RequestException as e:
        print(f'Error fetching monitor output: {e}')
        if hasattr(e, 'response') and e.response:
            print(f'Response status: {e.response.status_code}')
            print(f'Response text: {e.response.text}')
        sys.exit(1)


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description='Fetch monitor output (latest-releases.json) from Artifactory'
    )
    parser.add_argument(
        '--output-dir', '-o',
        default=os.environ.get('OUTPUT_DIR', '/monitor-output'),
        help='Output directory for latest-releases.json (default: /monitor-output, or OUTPUT_DIR env var)'
    )
    parser.add_argument(
        '--output-file',
        help='Full path to output file (overrides --output-dir if specified)'
    )
    
    args = parser.parse_args()
    
    if args.output_file:
        # If full output file path is specified, use its parent directory
        output_path = Path(args.output_file)
        output_dir = str(output_path.parent)
        
        # Create directory and fetch
        fetch_monitor_output(output_dir)
        
        # Rename the file if needed (in case filename is different from latest-releases.json)
        if output_path.name != 'latest-releases.json':
            default_output = Path(output_dir) / 'latest-releases.json'
            default_output.rename(output_path)
            print(f'Renamed output file to {output_path}')
    else:
        # Use output directory
        fetch_monitor_output(args.output_dir)


if __name__ == '__main__':
    main()
