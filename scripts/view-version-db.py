#!/usr/bin/env python3
"""
View the contents of the S3 version database.

Usage:
    python3 view-version-db.py
"""

import os
import boto3
import json
from botocore.config import Config
from datetime import datetime

def view_version_db():
    """View the current version database."""
    
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
    
    # Build client arguments
    client_kwargs = {
        'service_name': 's3',
        'endpoint_url': endpoint_url,
        'aws_access_key_id': access_key,
        'aws_secret_access_key': secret_key,
        'region_name': 'us-east-1',
        'config': client_config
    }
    
    # Configure SSL verification
    if skip_ssl_verification:
        print("WARNING: Skipping SSL verification for S3 endpoint")
        client_kwargs['verify'] = False
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Create S3 client
    s3 = boto3.client(**client_kwargs)
    
    # Download current version database
    version_db_key = 'version-db/version_db.json'
    
    try:
        response = s3.get_object(Bucket=bucket, Key=version_db_key)
        version_data = json.loads(response['Body'].read())
        print(f"\nVersion database from s3://{bucket}/{version_db_key}")
        print("=" * 70)
        
        # Show metadata
        metadata = version_data.get('metadata', {})
        print(f"Last updated: {metadata.get('last_updated', 'unknown')}")
        print(f"Total repositories: {metadata.get('total_repositories', 0)}")
        print(f"Total downloads: {metadata.get('total_downloads', 0)}")
        
        # Show repositories
        print("\nTracked repositories:")
        print("-" * 70)
        
        repos = version_data.get('repositories', {})
        if not repos:
            print("  No repositories tracked yet")
        else:
            for repo_key, repo_data in sorted(repos.items()):
                repo_name = repo_key.replace('_', '/')
                version = repo_data.get('current_version', 'unknown')
                last_checked = repo_data.get('last_checked', 'unknown')
                downloads = repo_data.get('download_count', 0)
                
                print(f"\n  {repo_name}:")
                print(f"    Current version: {version}")
                print(f"    Last checked: {last_checked}")
                print(f"    Downloads: {downloads}")
                
                # Show recent downloads if any
                download_history = repo_data.get('download_history', [])
                if download_history:
                    print(f"    Recent downloads:")
                    for dl in download_history[-3:]:  # Show last 3
                        print(f"      - {dl.get('version')} at {dl.get('timestamp')}")
                
    except s3.exceptions.NoSuchKey:
        print("No version database found in S3")
        print(f"Expected location: s3://{bucket}/{version_db_key}")
    except Exception as e:
        print(f"Error downloading version database: {e}")

if __name__ == '__main__':
    view_version_db()