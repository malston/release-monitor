#!/usr/bin/env python3
"""
Clear a specific repository from the Artifactory version database to force re-download.

Usage:
    python3 clear-version-entry-artifactory.py <owner/repo>

Example:
    python3 clear-version-entry-artifactory.py etcd-io/etcd
"""

import sys
import os
import json
import requests
from datetime import datetime, timezone


def clear_version_entry(repo_key):
    """Clear a specific repository from the version database."""
    
    # Required environment variables
    artifactory_url = os.environ.get('ARTIFACTORY_URL')
    if not artifactory_url:
        print("ERROR: ARTIFACTORY_URL environment variable not set")
        return False
    
    repository = os.environ.get('ARTIFACTORY_REPOSITORY')
    if not repository:
        print("ERROR: ARTIFACTORY_REPOSITORY environment variable not set")
        return False
    
    api_key = os.environ.get('ARTIFACTORY_API_KEY')
    if not api_key:
        print("ERROR: ARTIFACTORY_API_KEY environment variable not set")
        return False
    
    # SSL verification
    verify_ssl = os.environ.get('ARTIFACTORY_SKIP_SSL_VERIFICATION', 'false').lower() != 'true'
    if not verify_ssl:
        print("WARNING: Skipping SSL verification for Artifactory endpoint")
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    print(f"Connecting to Artifactory at {artifactory_url}...")
    
    # Download current version database
    url = f"{artifactory_url.rstrip('/')}/{repository}/release-monitor/version_db.json"
    headers = {'Authorization': f'Bearer {api_key}'}
    
    try:
        print(f"Downloading version database from: {url}")
        response = requests.get(url, headers=headers, verify=verify_ssl)
        
        if response.status_code == 404:
            print("No version database found in Artifactory")
            return False
        
        response.raise_for_status()
        version_data = response.json()
        print("Downloaded version database from Artifactory")
        
    except requests.exceptions.RequestException as e:
        print(f'Error downloading version database: {e}')
        if hasattr(e, 'response') and e.response:
            print(f'Response status: {e.response.status_code}')
            print(f'Response text: {e.response.text}')
        return False
    except json.JSONDecodeError as e:
        print(f'Error parsing JSON response: {e}')
        return False
    
    # Check if repository exists
    repos = version_data.get('repositories', {})
    if repo_key not in repos:
        print(f"Repository {repo_key} not found in version database")
        if repos:
            print("Available repositories:")
            for repo in sorted(repos.keys()):
                print(f"  - {repo}")
        else:
            print("No repositories tracked yet")
        return False
    
    # Remove the repository entry
    old_version = version_data['repositories'][repo_key].get('current_version', 'unknown')
    del version_data['repositories'][repo_key]
    
    # Update metadata
    if 'metadata' not in version_data:
        version_data['metadata'] = {}
    
    version_data['metadata']['last_updated'] = datetime.now(timezone.utc).isoformat()
    version_data['metadata']['version'] = '2.0'
    version_data['metadata']['storage'] = 'artifactory'
    
    # Upload updated version database
    try:
        json_content = json.dumps(version_data, indent=2, sort_keys=True)
        upload_headers = headers.copy()
        upload_headers['Content-Type'] = 'application/json'
        
        response = requests.put(
            url,
            data=json_content,
            headers=upload_headers,
            verify=verify_ssl
        )
        
        response.raise_for_status()
        print(f"Successfully removed {repo_key} (was at version {old_version})")
        print(f"Updated version database uploaded to Artifactory")
        print(f"\nNext pipeline run will re-download releases for {repo_key}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f'Error uploading updated version database: {e}')
        if hasattr(e, 'response') and e.response:
            print(f'Response status: {e.response.status_code}')
            print(f'Response text: {e.response.text}')
        return False


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    
    repo_key = sys.argv[1]
    if '/' not in repo_key:
        print("Error: Repository must be in format 'owner/repo'")
        sys.exit(1)
    
    success = clear_version_entry(repo_key)
    if not success:
        sys.exit(1)