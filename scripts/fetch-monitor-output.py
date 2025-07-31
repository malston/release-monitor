#!/usr/bin/env python3
"""
Fetch monitor output (latest-releases.json) from Artifactory.

This script downloads the latest-releases.json file from Artifactory
for use in downstream pipeline tasks.
"""

import os
import requests
import sys


def fetch_monitor_output():
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

        # Write to output directory
        output_file = '/monitor-output/latest-releases.json'
        with open(output_file, 'w') as f:
            f.write(response.text)

        print(f'Successfully downloaded latest-releases.json to {output_file}')

    except requests.exceptions.RequestException as e:
        print(f'Error fetching monitor output: {e}')
        if hasattr(e, 'response') and e.response:
            print(f'Response status: {e.response.status_code}')
            print(f'Response text: {e.response.text}')
        sys.exit(1)


if __name__ == '__main__':
    fetch_monitor_output()
