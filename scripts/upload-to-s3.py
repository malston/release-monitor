#!/usr/bin/env python3
"""
Upload downloaded release files to S3-compatible storage.

This script uploads all .gz and .zip files from the downloads directory
to S3-compatible storage (AWS S3, MinIO, etc.).
"""

import os
import sys
import boto3
from botocore.config import Config
from boto3.s3.transfer import TransferConfig
from pathlib import Path


def main():
    """Upload release files to S3 storage."""
    
    # Configure S3 client with SSL verification settings
    endpoint_url = os.environ.get('S3_ENDPOINT')
    skip_ssl_verification = os.environ.get('S3_SKIP_SSL_VERIFICATION', 'false').lower() == 'true'
    
    # Configure boto3 client config
    client_config = Config(
        signature_version='s3v4',
        s3={'addressing_style': 'path'}
    )
    
    s3_kwargs = {
        'region_name': os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'),
        'config': client_config
    }
    
    # Configure SSL verification
    if skip_ssl_verification:
        print("WARNING: Skipping SSL verification for S3 endpoint")
        s3_kwargs['verify'] = False
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    if endpoint_url:
        s3_kwargs['endpoint_url'] = endpoint_url
        print(f'Using S3-compatible endpoint: {endpoint_url}')
    
    s3 = boto3.client('s3', **s3_kwargs)
    bucket = os.environ['S3_BUCKET']
    
    # Configure transfer to avoid multipart uploads which cause ContentLength issues
    transfer_config = TransferConfig(
        multipart_threshold=1024 * 1024 * 1024,  # 1GB - effectively disable multipart for our files
        max_concurrency=1,
        multipart_chunksize=1024 * 1024 * 1024,
        use_threads=False
    )
    
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
                # Get file size for debugging
                file_size = file_path.stat().st_size
                print(f'  File size: {file_size} bytes')
                
                # Use upload_file with custom config to avoid multipart uploads
                s3.upload_file(
                    str(file_path),
                    bucket,
                    s3_key,
                    Config=transfer_config
                )
                uploaded_count += 1
                print(f'  Success: Uploaded {file_size} bytes')
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