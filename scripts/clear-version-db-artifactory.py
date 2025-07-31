#!/usr/bin/env python3
"""
Clear the entire Artifactory version database.

This script deletes the version database file from Artifactory,
forcing all releases to be re-downloaded on the next pipeline run.
"""

import os
import sys
import requests
from datetime import datetime, timezone


def main():
    """Clear the entire version database from Artifactory storage."""

    # Required environment variables
    artifactory_url = os.environ.get('ARTIFACTORY_URL')
    if not artifactory_url:
        print("ERROR: ARTIFACTORY_URL environment variable not set")
        sys.exit(1)

    repository = os.environ.get('ARTIFACTORY_REPOSITORY')
    if not repository:
        print("ERROR: ARTIFACTORY_REPOSITORY environment variable not set")
        sys.exit(1)

    # Authentication - prefer API key over username/password
    api_key = os.environ.get('ARTIFACTORY_API_KEY')
    username = os.environ.get('ARTIFACTORY_USERNAME')
    password = os.environ.get('ARTIFACTORY_PASSWORD')

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

    # SSL verification
    verify_ssl = os.environ.get('ARTIFACTORY_SKIP_SSL_VERIFICATION', 'false').lower() != 'true'
    if not verify_ssl:
        print("WARNING: Skipping SSL verification for Artifactory endpoint")
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    print(f'Using Artifactory: {artifactory_url}')
    print(f'Repository: {repository}')

    # Delete the version database
    url = f"{artifactory_url.rstrip('/')}/{repository}/release-monitor/version_db.json"

    try:
        print(f'Clearing version database at: {url}')
        response = requests.delete(url, headers=headers, auth=auth, verify=verify_ssl)

        if response.status_code == 404:
            print('Version database not found - nothing to clear')
        else:
            response.raise_for_status()
            print('Successfully cleared version database from Artifactory')

        print('Next pipeline run will download all releases as new')

    except requests.exceptions.RequestException as e:
        print(f'Error clearing version database: {e}')
        if hasattr(e, 'response') and e.response:
            print(f'Response status: {e.response.status_code}')
            print(f'Response text: {e.response.text}')
        sys.exit(1)


if __name__ == '__main__':
    main()
