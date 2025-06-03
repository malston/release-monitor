#!/usr/bin/env python3
"""
Clear a specific repository from the S3 version database to force re-download.

Usage:
    python3 clear-version-entry.py <owner/repo>

Example:
    python3 clear-version-entry.py etcd-io/etcd
"""

import sys
import os
import boto3
import json
from botocore.config import Config
from pathlib import Path
from datetime import datetime

def clear_version_entry(repo_key):
    """Clear a specific repository from the version database."""

    # Get S3 configuration from environment
    endpoint_url = os.environ.get('S3_ENDPOINT', 'http://localhost:9000')
    access_key = os.environ.get('AWS_ACCESS_KEY_ID', 'release-monitor-user')
    secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY', 'release-monitor-pass')
    bucket = os.environ.get('S3_BUCKET', 'release-monitor-output')

    print(f"Connecting to S3 at {endpoint_url}...")

    # Configure SSL verification
    skip_ssl_verification = os.environ.get('S3_SKIP_SSL_VERIFICATION', 'false').lower() == 'true'
    
    # Configure boto3 client config
    client_config = Config(
        signature_version='s3v4',
        s3={'addressing_style': 'path'}
    )
    
    if skip_ssl_verification:
        print("WARNING: Skipping SSL verification for S3 endpoint")
        client_config.merge(Config(
            use_ssl=True,
            verify=False
        ))

    # Create S3 client
    s3 = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name='us-east-1',
        config=client_config
    )

    # Download current version database
    version_db_key = 'version-db/version_db.json'

    try:
        response = s3.get_object(Bucket=bucket, Key=version_db_key)
        version_data = json.loads(response['Body'].read())
        print(f"Downloaded version database from s3://{bucket}/{version_db_key}")
    except s3.exceptions.NoSuchKey:
        print("No version database found in S3")
        return
    except Exception as e:
        print(f"Error downloading version database: {e}")
        return

    # Check if repository exists (check both formats)
    repos = version_data.get('repositories', {})
    if repo_key not in repos and repo_key.replace('_', '/') not in repos:
        print(f"Repository {repo_key} not found in version database")
        print("Available repositories:")
        for repo in repos.keys():
            print(f"  - {repo}")
        return

    # Use the format that actually exists in the database
    if repo_key in repos:
        actual_key = repo_key
    else:
        actual_key = repo_key.replace('_', '/')

    # Remove the repository entry
    old_version = version_data['repositories'][actual_key].get('current_version', 'unknown')
    del version_data['repositories'][actual_key]

    # Update metadata
    version_data['metadata']['last_updated'] = datetime.now().isoformat()
    version_data['metadata']['total_repositories'] = len(version_data['repositories'])

    # Upload updated version database
    try:
        s3.put_object(
            Bucket=bucket,
            Key=version_db_key,
            Body=json.dumps(version_data, indent=2),
            ContentType='application/json'
        )
        print(f"Successfully removed {repo_key} (was at version {old_version})")
        print(f"Updated version database uploaded to s3://{bucket}/{version_db_key}")
        print(f"\nNext pipeline run will re-download releases for {repo_key}")
    except Exception as e:
        print(f"Error uploading updated version database: {e}")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    repo_key = sys.argv[1]
    if '/' not in repo_key:
        print("Error: Repository must be in format 'owner/repo'")
        sys.exit(1)

    # Replace / with _ for the key
    repo_key = repo_key.replace('/', '_')

    clear_version_entry(repo_key)
