#!/usr/bin/env python3
"""
Upload downloaded release files to S3-compatible storage.

This script uploads all .gz and .zip files from the downloads directory
to S3-compatible storage (AWS S3, MinIO, etc.).
"""

import os
import sys
import boto3
from pathlib import Path


def main():
    """Upload release files to S3 storage."""
    
    # Configure S3 client
    endpoint_url = os.environ.get('S3_ENDPOINT')
    s3_kwargs = {
        'region_name': os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
    }
    
    if endpoint_url:
        s3_kwargs['endpoint_url'] = endpoint_url
        print(f'Using S3-compatible endpoint: {endpoint_url}')
    
    s3 = boto3.client('s3', **s3_kwargs)
    bucket = os.environ['S3_BUCKET']
    
    # Find and upload all release files
    downloads_dir = Path('../downloads')
    if not downloads_dir.exists():
        print(f'ERROR: {downloads_dir} does not exist!')
        sys.exit(1)
        
    uploaded_count = 0
    
    for file_path in downloads_dir.rglob('*'):
        if file_path.is_file() and (file_path.suffix in ['.gz', '.zip']):
            # Create S3 key maintaining directory structure
            relative_path = file_path.relative_to(downloads_dir)
            s3_key = f'release-downloads/{relative_path}'
            
            print(f'Uploading {relative_path} to s3://{bucket}/{s3_key}')
            
            try:
                with open(file_path, 'rb') as f:
                    s3.put_object(Bucket=bucket, Key=s3_key, Body=f)
                uploaded_count += 1
                print(f'  Success: Uploaded {file_path.stat().st_size} bytes')
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
        print(f'\nSUCCESS: Uploaded {uploaded_count} files to S3.')


if __name__ == '__main__':
    main()