#!/usr/bin/env python3
"""
Upload downloaded release files to JFrog Artifactory.

This script uploads all .gz and .zip files from the downloads directory
to JFrog Artifactory repository, or uploads just the releases.json file
when --releases-json flag is used.
"""

import os
import sys
import hashlib
import requests
from requests.auth import HTTPBasicAuth
from pathlib import Path
import argparse


def calculate_checksums(file_path):
    """Calculate SHA1 and MD5 checksums for the file."""
    sha1_hash = hashlib.sha1()
    md5_hash = hashlib.md5()

    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha1_hash.update(chunk)
            md5_hash.update(chunk)

    return sha1_hash.hexdigest(), md5_hash.hexdigest()


def upload_releases_json(artifactory_url, repository, headers, auth, verify_ssl):
    """Upload just the releases.json file to Artifactory."""

    # Find releases.json file
    releases_file = Path('../release-output/releases.json')
    if not releases_file.exists():
        print("ERROR: Could not find releases.json file at ../release-output/releases.json")
        return False

    # Upload releases.json file
    artifactory_path = 'release-monitor/latest-releases.json'
    url = f"{artifactory_url.rstrip('/')}/{repository}/{artifactory_path}"

    print(f'Uploading releases.json to {url}')

    try:
        # Get file size
        file_size = releases_file.stat().st_size
        print(f'  File size: {file_size} bytes')

        # Use JSON content type for releases.json
        upload_headers = headers.copy()
        upload_headers['Content-Type'] = 'application/json'

        # Read and upload file
        with open(releases_file, 'rb') as f:
            response = requests.put(
                url,
                data=f,
                headers=upload_headers,
                auth=auth,
                verify=verify_ssl,
                timeout=60
            )

        response.raise_for_status()
        print(f'  Upload response: {response.status_code}')
        print(f'  Success: Uploaded {file_size} bytes')

        # Print response details for debugging
        if response.text:
            print(f'  Response: {response.text}')

        return True

    except requests.exceptions.RequestException as e:
        print(f'Error uploading releases.json: {e}')
        if hasattr(e, 'response') and e.response:
            print(f'  Response status: {e.response.status_code}')
            print(f'  Response text: {e.response.text}')
        return False
    except Exception as e:
        print(f'Error uploading releases.json: {e}')
        return False


def main():
    """Upload release files or releases.json to Artifactory."""

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Upload files to JFrog Artifactory')
    parser.add_argument('--releases-json', action='store_true',
                       help='Upload only the releases.json file instead of downloaded files')
    args = parser.parse_args()

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

    headers = {'Content-Type': 'application/octet-stream'}
    auth = None

    if api_key:
        headers['X-JFrog-Art-Api'] = api_key
        print("Using API key authentication")
    elif username and password:
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

    # Check for proxy settings
    http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
    https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
    no_proxy = os.environ.get('NO_PROXY') or os.environ.get('no_proxy')

    if http_proxy or https_proxy:
        print(f'Proxy detected:')
        print(f'  HTTP_PROXY: {http_proxy}')
        print(f'  HTTPS_PROXY: {https_proxy}')
        print(f'  NO_PROXY: {no_proxy}')

        # Check if Artifactory endpoint should bypass proxy
        if artifactory_url and 'example.com' in artifactory_url:
            if not no_proxy or 'example.com' not in no_proxy:
                print(f'WARNING: Artifactory endpoint {artifactory_url} may be going through proxy')
                print(f'Consider adding your Artifactory domain to NO_PROXY environment variable')

    print(f'Using Artifactory: {artifactory_url}')
    print(f'Repository: {repository}')

    # Handle releases.json upload mode
    if args.releases_json:
        print('Mode: Uploading releases.json file only')
        success = upload_releases_json(artifactory_url, repository, headers, auth, verify_ssl)
        if success:
            print('\nSUCCESS: Uploaded releases.json to Artifactory.')
            sys.exit(0)
        else:
            print('\nERROR: Failed to upload releases.json to Artifactory.')
            sys.exit(1)

    # Find downloads directory
    possible_paths = [
        Path('../downloads'),             # Concourse input directory (relative from release-monitor-repo)
        Path('downloads'),                # Current directory
        Path('/tmp/downloads'),           # Absolute path used by pipeline
        Path(os.environ.get('DOWNLOAD_DIR', '/tmp/downloads'))  # Environment variable
    ]

    downloads_dir = None
    for path in possible_paths:
        if path.exists():
            downloads_dir = path
            print(f'Found downloads directory at: {downloads_dir}')
            break

    if not downloads_dir:
        print(f'ERROR: Could not find downloads directory!')
        print(f'Searched in: {[str(p) for p in possible_paths]}')
        sys.exit(1)

    uploaded_count = 0

    # Upload files
    for file_path in downloads_dir.rglob('*'):
        if file_path.is_file() and (file_path.suffix in ['.gz', '.zip']):
            # Create Artifactory path maintaining directory structure
            relative_path = file_path.relative_to(downloads_dir)
            artifactory_path = f'release-downloads/{relative_path}'

            # Build full URL
            url = f"{artifactory_url.rstrip('/')}/{repository}/{artifactory_path}"

            print(f'Uploading {relative_path} to {url}')

            try:
                # Get file size and calculate checksums
                file_size = file_path.stat().st_size
                print(f'  File size: {file_size} bytes')

                sha1_checksum, md5_checksum = calculate_checksums(file_path)
                print(f'  SHA1: {sha1_checksum}')
                print(f'  MD5: {md5_checksum}')

                # Prepare headers with checksums
                upload_headers = headers.copy()
                upload_headers['X-Checksum-Sha1'] = sha1_checksum
                upload_headers['X-Checksum-Md5'] = md5_checksum
                upload_headers['Content-Length'] = str(file_size)

                # Read and upload file
                with open(file_path, 'rb') as f:
                    response = requests.put(
                        url,
                        data=f,
                        headers=upload_headers,
                        auth=auth,
                        verify=verify_ssl,
                        timeout=300  # 5 minute timeout for large files
                    )

                response.raise_for_status()
                print(f'  Upload response: {response.status_code}')
                uploaded_count += 1
                print(f'  Success: Uploaded {file_size} bytes')

                # Print response details for debugging
                if response.text:
                    print(f'  Response: {response.text}')

            except requests.exceptions.RequestException as e:
                print(f'Error uploading {file_path}: {e}')
                if hasattr(e, 'response') and e.response:
                    print(f'  Response status: {e.response.status_code}')
                    print(f'  Response text: {e.response.text}')
                raise
            except Exception as e:
                print(f'Error uploading {file_path}: {e}')
                raise

    if uploaded_count == 0:
        print('\nINFO: No release files found to upload.')
        print('This is normal when all monitored releases are already at their latest versions.')

        # Show what files were found for debugging
        file_count = sum(1 for p in downloads_dir.rglob('*') if p.is_file())
        if file_count > 0:
            print(f'\nFound {file_count} metadata files in downloads directory.')
    else:
        print(f'\nSUCCESS: Uploaded {uploaded_count} files to Artifactory.')


if __name__ == '__main__':
    main()
