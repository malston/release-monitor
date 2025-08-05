#!/usr/bin/env python3
"""
View the contents of the version database from multiple storage backends.

Supports:
- Artifactory (via HTTP REST API)
- S3/MinIO (via boto3)
- Local file (direct file access)

Storage backend is auto-detected based on environment variables.

Usage:
    python3 show-version-db.py [--backend=auto|artifactory|s3|local] [--verbose]
"""

import os
import sys
import json
import argparse


def setup_artifactory_client():
    """Setup Artifactory client configuration."""

    # Required environment variables
    artifactory_url = os.environ.get('ARTIFACTORY_URL')
    if not artifactory_url:
        return None, "ARTIFACTORY_URL environment variable not set"

    repository = os.environ.get('ARTIFACTORY_REPOSITORY')
    if not repository:
        return None, "ARTIFACTORY_REPOSITORY environment variable not set"

    # Authentication - prefer API key over username/password
    api_key = os.environ.get('ARTIFACTORY_API_KEY')
    username = os.environ.get('ARTIFACTORY_USERNAME')
    password = os.environ.get('ARTIFACTORY_PASSWORD')

    headers = {}
    auth = None

    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
        auth_type = "API key"
    elif username and password:
        from requests.auth import HTTPBasicAuth
        auth = HTTPBasicAuth(username, password)
        auth_type = f"username/password for user: {username}"
    else:
        return None, "No authentication credentials found. Set ARTIFACTORY_API_KEY or ARTIFACTORY_USERNAME/ARTIFACTORY_PASSWORD"

    # SSL verification
    verify_ssl = os.environ.get('ARTIFACTORY_SKIP_SSL_VERIFICATION', 'false').lower() != 'true'

    config = {
        'url': artifactory_url,
        'repository': repository,
        'headers': headers,
        'auth': auth,
        'verify_ssl': verify_ssl,
        'auth_type': auth_type
    }

    return config, None


def setup_s3_client():
    """Setup S3/MinIO client configuration."""

    bucket = os.environ.get('VERSION_DB_S3_BUCKET')
    if not bucket:
        return None, "VERSION_DB_S3_BUCKET environment variable not set"

    prefix = os.environ.get('VERSION_DB_S3_PREFIX', 'release-monitor/')
    region = os.environ.get('VERSION_DB_S3_REGION')
    endpoint = os.environ.get('S3_ENDPOINT')

    config = {
        'bucket': bucket,
        'prefix': prefix,
        'region': region,
        'endpoint': endpoint
    }

    return config, None


def setup_local_client():
    """Setup local file client configuration."""

    # Check common locations for version database
    possible_paths = [
        os.environ.get('VERSION_DB_PATH'),
        os.environ.get('DOWNLOAD_DIR', '.') + '/version_db.json',
        './downloads/version_db.json',
        './version_db.json'
    ]

    version_db_path = None
    for path in possible_paths:
        if path and os.path.exists(path):
            version_db_path = path
            break

    if not version_db_path:
        return None, f"Version database file not found. Checked: {[p for p in possible_paths if p]}"

    config = {
        'path': version_db_path
    }

    return config, None


def detect_storage_backend():
    """Auto-detect which storage backend to use based on environment variables."""

    # Priority order: Artifactory -> S3 -> Local

    # Check Artifactory
    if os.environ.get('ARTIFACTORY_URL') and os.environ.get('ARTIFACTORY_REPOSITORY'):
        return 'artifactory'

    # Check S3
    if os.environ.get('VERSION_DB_S3_BUCKET'):
        return 's3'

    # Fallback to local
    return 'local'


def fetch_version_db_artifactory(config, verbose=False):
    """Fetch version database from Artifactory."""

    try:
        import requests
    except ImportError:
        return None, "requests library not available. Install with: pip install requests"

    if not config['verify_ssl']:
        if verbose:
            print("WARNING: Skipping SSL verification for Artifactory endpoint")
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if verbose:
        print(f"Connecting to Artifactory at {config['url']}...")
        print(f"Using {config['auth_type']}")

    # Download version database
    url = f"{config['url'].rstrip('/')}/{config['repository']}/release-monitor/version_db.json"

    try:
        if verbose:
            print(f"Fetching version database from: {url}")

        response = requests.get(
            url,
            headers=config['headers'],
            auth=config['auth'],
            verify=config['verify_ssl'],
            timeout=30
        )

        if response.status_code == 404:
            return None, f"No version database found in Artifactory at: {url}"

        response.raise_for_status()
        version_data = response.json()

        return version_data, None

    except requests.exceptions.RequestException as e:
        error_msg = f'Error fetching version database: {e}'
        if hasattr(e, 'response') and e.response:
            error_msg += f' (status: {e.response.status_code})'
        return None, error_msg
    except json.JSONDecodeError as e:
        return None, f'Error parsing JSON response: {e}'


def fetch_version_db_s3(config, verbose=False):
    """Fetch version database from S3/MinIO."""

    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError:
        return None, "boto3 library not available. Install with: pip install boto3"

    if verbose:
        print(f"Connecting to S3 bucket: {config['bucket']}")
        if config['endpoint']:
            print(f"Using custom endpoint: {config['endpoint']}")

    try:
        # Create S3 client
        s3_config = {}
        if config['region']:
            s3_config['region_name'] = config['region']
        if config['endpoint']:
            s3_config['endpoint_url'] = config['endpoint']

        # Check SSL verification
        verify_ssl = os.environ.get('S3_SKIP_SSL_VERIFICATION', 'false').lower() != 'true'
        if not verify_ssl:
            if verbose:
                print("WARNING: Skipping SSL verification for S3 endpoint")
            s3_config['verify'] = False

        s3_client = boto3.client('s3', **s3_config)

        # Download version database
        key = f"{config['prefix'].rstrip('/')}/version_db.json"

        if verbose:
            print(f"Fetching version database from s3://{config['bucket']}/{key}")

        response = s3_client.get_object(Bucket=config['bucket'], Key=key)
        version_data = json.loads(response['Body'].read().decode('utf-8'))

        return version_data, None

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            return None, f"No version database found at s3://{config['bucket']}/{key}"
        elif error_code == 'NoSuchBucket':
            return None, f"S3 bucket '{config['bucket']}' does not exist"
        else:
            return None, f"S3 error: {e}"
    except NoCredentialsError:
        return None, "AWS credentials not found. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
    except Exception as e:
        return None, f"Error fetching from S3: {e}"


def fetch_version_db_local(config, verbose=False):
    """Fetch version database from local file."""

    if verbose:
        print(f"Reading version database from: {config['path']}")

    try:
        with open(config['path'], 'r') as f:
            version_data = json.load(f)
        return version_data, None

    except FileNotFoundError:
        return None, f"Version database file not found: {config['path']}"
    except json.JSONDecodeError as e:
        return None, f"Error parsing JSON file: {e}"
    except Exception as e:
        return None, f"Error reading file: {e}"


def display_version_db(version_data, backend_name, verbose=False):
    """Display version database contents in a formatted way."""

    print(f"\nVersion Database ({backend_name})")
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
                # Show last 3 entries
                recent_downloads = download_history[-3:] if len(download_history) > 3 else download_history
                for dl in recent_downloads:
                    dl_version = dl.get('version', 'unknown')
                    dl_time = dl.get('downloaded_at', 'unknown')
                    dl_count = dl.get('download_count', 1)
                    size_info = ""
                    if 'total_size' in dl:
                        size_mb = dl['total_size'] / (1024 * 1024)
                        size_info = f" ({size_mb:.1f} MB)"
                    print(f"      - {dl_version} at {dl_time} ({dl_count} files{size_info})")

                if len(download_history) > 3:
                    print(f"      ... and {len(download_history) - 3} older entries")

    print(f"\nTotal repositories: {len(repos)}")

    if verbose:
        # Show additional statistics
        total_downloads = sum(
            len(repo_data.get('download_history', []))
            for repo_data in repos.values()
        )
        total_size = sum(
            sum(dl.get('total_size', 0) for dl in repo_data.get('download_history', []))
            for repo_data in repos.values()
        )

        print(f"Total download entries: {total_downloads}")
        if total_size > 0:
            total_size_gb = total_size / (1024 * 1024 * 1024)
            print(f"Total downloaded size: {total_size_gb:.2f} GB")


def main():
    """Main function."""

    parser = argparse.ArgumentParser(
        description='View version database contents from multiple storage backends',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Storage backends are auto-detected based on environment variables:

Artifactory:
  ARTIFACTORY_URL, ARTIFACTORY_REPOSITORY
  ARTIFACTORY_API_KEY or ARTIFACTORY_USERNAME/ARTIFACTORY_PASSWORD

S3/MinIO:
  VERSION_DB_S3_BUCKET
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
  Optional: S3_ENDPOINT, VERSION_DB_S3_REGION, VERSION_DB_S3_PREFIX

Local file:
  VERSION_DB_PATH or searches common locations
        """
    )

    parser.add_argument(
        '--backend',
        choices=['auto', 'artifactory', 's3', 'local'],
        default='auto',
        help='Storage backend to use (default: auto-detect)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    # Determine backend
    if args.backend == 'auto':
        backend = detect_storage_backend()
        if args.verbose:
            print(f"Auto-detected storage backend: {backend}")
    else:
        backend = args.backend

    # Setup client configuration
    if backend == 'artifactory':
        config, error = setup_artifactory_client()
        fetch_func = fetch_version_db_artifactory
        backend_name = "Artifactory"
    elif backend == 's3':
        config, error = setup_s3_client()
        fetch_func = fetch_version_db_s3
        backend_name = "S3/MinIO"
    elif backend == 'local':
        config, error = setup_local_client()
        fetch_func = fetch_version_db_local
        backend_name = "Local File"
    else:
        print(f"ERROR: Unknown backend: {backend}")
        sys.exit(1)

    if error:
        print(f"ERROR: {error}")
        sys.exit(1)

    # Fetch version database
    version_data, error = fetch_func(config, args.verbose)

    if error:
        print(f"ERROR: {error}")
        sys.exit(1)

    if not version_data:
        print("No version database found")
        sys.exit(1)

    # Display results
    display_version_db(version_data, backend_name, args.verbose)


if __name__ == '__main__':
    main()
