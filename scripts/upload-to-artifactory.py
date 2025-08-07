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
import json
import logging

# Import yaml conditionally - only needed for configuration loading
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


def calculate_checksums(file_path):
    """Calculate SHA1 and MD5 checksums for the file."""
    sha1_hash = hashlib.sha1()
    md5_hash = hashlib.md5()

    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha1_hash.update(chunk)
            md5_hash.update(chunk)

    return sha1_hash.hexdigest(), md5_hash.hexdigest()


def load_config(config_path: str):
    """Load YAML configuration file."""
    if not YAML_AVAILABLE:
        print("ERROR: PyYAML is required for configuration loading but not installed")
        print("Install it with: pip install PyYAML")
        return {}

    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config from {config_path}: {e}")
        return {}


def load_version_db(version_db_path: str):
    """Load version database JSON file."""
    try:
        with open(version_db_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Error loading version database from {version_db_path}: {e}")
        return {}


def should_upload_file(relative_path: Path, target_version: str = None, version_db: dict = None, asset_patterns: list = None):
    """Determine if a file should be uploaded based on target version configuration and asset patterns."""
    # Extract repository and version from file path
    # Path structure: owner_repo/version/file.ext (relative to downloads dir)
    path_parts = relative_path.parts
    if len(path_parts) < 3:
        return False

    repo_folder = path_parts[0]  # e.g., 'open-policy-agent_gatekeeper'
    file_version = path_parts[1]  # e.g., 'v3.18.0'
    filename = path_parts[2]  # e.g., 'file.yaml'

    # Convert folder name back to repository name
    repository = repo_folder.replace('_', '/')

    # Check asset patterns first
    if asset_patterns:
        import fnmatch
        filename_lower = filename.lower()
        pattern_matches = False

        # First check inclusion patterns
        for pattern in asset_patterns:
            if not pattern.startswith('!'):
                if fnmatch.fnmatch(filename_lower, pattern.lower()):
                    pattern_matches = True
                    break

        # If no inclusion pattern matched, return False
        if not pattern_matches:
            return False

        # Now check exclusion patterns
        for pattern in asset_patterns:
            if pattern.startswith('!'):
                if fnmatch.fnmatch(filename_lower, pattern[1:].lower()):
                    return False

    # Check version constraints
    if target_version:
        # If target version is specified, only upload files with that version
        return file_version == target_version
    else:
        # If no target version, upload the latest version from version database
        if version_db and repository in version_db:
            latest_version = version_db[repository].get('latest_version')
            return file_version == latest_version
        # If no version database info, upload all files (backward compatibility)
        return True


def upload_releases_json(artifactory_url, repository, headers, auth, verify_ssl):
    """Upload just the releases.json file to Artifactory."""

    # Get configurable path from environment variable
    # Default to Concourse structure if not specified
    releases_input_dir = os.getenv('RELEASES_INPUT_DIR', '/release-output')

    # Find releases.json file
    releases_file = Path(releases_input_dir) / 'releases.json'
    if not releases_file.exists():
        print(f"ERROR: Could not find releases.json file at {releases_file}")
        return False

    # Upload releases.json file
    artifactory_path = 'release-monitor/latest-releases.json'
    url = f"{artifactory_url.rstrip('/')}/{repository}/{artifactory_path}"

    print(f'Debug - artifactory_url: {artifactory_url}')
    print(f'Debug - repository: {repository}')
    print(f'Debug - artifactory_path: {artifactory_path}')
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
    parser.add_argument('--config', default='config.yaml',
                       help='Configuration file path (default: config.yaml)')
    parser.add_argument('--version-db',
                       help='Version database file path (auto-detected from config if not specified)')
    args = parser.parse_args()

    # Only load configuration if not in releases-json mode
    if not args.releases_json:
        # Load configuration
        config = load_config(args.config)
        download_config = config.get('download', {})
        repository_overrides = download_config.get('repository_overrides', {})

        # Handle REPOSITORY_OVERRIDES environment variable (same as download task)
        env_repo_overrides = os.environ.get('REPOSITORY_OVERRIDES', '{}')
        print(f"DEBUG: Raw REPOSITORY_OVERRIDES env var: {env_repo_overrides[:200]}...")
        if env_repo_overrides and env_repo_overrides.strip() != '{}':
            try:
                env_overrides = json.loads(env_repo_overrides)
                if env_overrides:
                    print(f"Applying repository overrides from environment variable ({len(env_overrides)} repositories)")
                    repository_overrides = env_overrides
                    for repo, config in env_overrides.items():
                        print(f"  {repo}: asset_patterns={config.get('asset_patterns', 'not specified')}")
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse REPOSITORY_OVERRIDES environment variable: {e}")

        # Load version database
        version_db_path = args.version_db or download_config.get('version_db', 'version_db.json')
        version_db = load_version_db(version_db_path)

        print(f"Loaded configuration from: {args.config}")
        print(f"Repository overrides: {len(repository_overrides)} configured")
        if repository_overrides:
            for repo, config in repository_overrides.items():
                print(f"  Final config for {repo}: asset_patterns={config.get('asset_patterns', 'not specified')}")
        print(f"Version database: {version_db_path} ({'found' if version_db else 'not found'})")
    else:
        # In releases-json mode, we don't need configuration
        repository_overrides = {}
        version_db = {}

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
        headers['Authorization'] = f'Bearer {api_key}'
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
    skipped_count = 0

    # Upload files with target version filtering and asset pattern matching
    for file_path in downloads_dir.rglob('*'):
        if file_path.is_file():
            # Create Artifactory path maintaining directory structure
            relative_path = file_path.relative_to(downloads_dir)

            # Extract repository from path to check target version and asset patterns
            path_parts = relative_path.parts
            if len(path_parts) >= 2:
                repo_folder = path_parts[0]  # e.g., 'open-policy-agent_gatekeeper'
                repository_name = repo_folder.replace('_', '/')

                # Get repository-specific configuration
                repo_override = repository_overrides.get(repository_name, {})
                target_version = repo_override.get('target_version')
                asset_patterns = repo_override.get('asset_patterns')

                # If no asset patterns specified for this repo, use default extensions
                if not asset_patterns:
                    # Fallback to original behavior for repositories without asset patterns
                    if file_path.suffix not in ['.gz', '.zip']:
                        print(f'Skipping {relative_path} (no asset patterns configured, using default .gz/.zip filter)')
                        skipped_count += 1
                        continue

                # Check if this file should be uploaded (version and asset pattern filtering)
                if not should_upload_file(relative_path, target_version, version_db, asset_patterns):
                    print(f'Skipping {relative_path} (not matching target version or asset pattern criteria)')
                    skipped_count += 1
                    continue

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
        print('\nINFO: No release files uploaded.')
        if skipped_count > 0:
            print(f'Skipped {skipped_count} files due to target version filtering.')
        else:
            print('This is normal when all monitored releases are already at their latest versions.')

        # Show what files were found for debugging
        file_count = sum(1 for p in downloads_dir.rglob('*') if p.is_file())
        if file_count > 0:
            print(f'\nFound {file_count} total files in downloads directory.')
    else:
        print(f'\nSUCCESS: Uploaded {uploaded_count} files to Artifactory.')
        if skipped_count > 0:
            print(f'Skipped {skipped_count} files due to target version filtering.')


if __name__ == '__main__':
    main()
