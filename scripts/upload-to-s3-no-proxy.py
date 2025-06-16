#!/usr/bin/env python3
"""
Upload release files to S3 storage with proxy bypass.
This script temporarily disables proxy for S3 uploads.
"""

import os
import sys
import boto3
from botocore.config import Config
from pathlib import Path

def main():
    """Upload release files to S3 storage."""
    
    # Save original proxy settings
    original_http_proxy = os.environ.get('HTTP_PROXY')
    original_https_proxy = os.environ.get('HTTPS_PROXY')
    
    try:
        # Temporarily disable proxy for S3 uploads
        if 'HTTP_PROXY' in os.environ:
            del os.environ['HTTP_PROXY']
        if 'HTTPS_PROXY' in os.environ:
            del os.environ['HTTPS_PROXY']
        if 'http_proxy' in os.environ:
            del os.environ['http_proxy']
        if 'https_proxy' in os.environ:
            del os.environ['https_proxy']
            
        print("Temporarily disabled proxy for S3 upload")
        
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
        
        # Find downloads directory
        downloads_dir = None
        for path in [Path('/tmp/downloads'), Path('../downloads'), Path('downloads')]:
            if path.exists():
                downloads_dir = path
                print(f'Found downloads directory at: {downloads_dir}')
                break
        
        if not downloads_dir:
            print('ERROR: Could not find downloads directory!')
            sys.exit(1)
            
        uploaded_count = 0
        
        for file_path in downloads_dir.rglob('*'):
            if file_path.is_file() and (file_path.suffix in ['.gz', '.zip']):
                relative_path = file_path.relative_to(downloads_dir)
                s3_key = f'release-downloads/{relative_path}'
                
                print(f'Uploading {relative_path} to s3://{bucket}/{s3_key}')
                
                try:
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                    
                    s3.put_object(
                        Bucket=bucket,
                        Key=s3_key,
                        Body=file_data,
                        ContentLength=len(file_data),
                        ContentType='application/octet-stream'
                    )
                    uploaded_count += 1
                    print(f'  Success: Uploaded {len(file_data)} bytes')
                except Exception as e:
                    print(f'Error uploading {file_path}: {e}')
                    raise
        
        if uploaded_count == 0:
            print('\nINFO: No release files found to upload.')
            print('This is normal when all monitored releases are already at their latest versions.')
        else:
            print(f'\nSUCCESS: Uploaded {uploaded_count} files to S3.')
            
    finally:
        # Restore original proxy settings
        if original_http_proxy:
            os.environ['HTTP_PROXY'] = original_http_proxy
        if original_https_proxy:
            os.environ['HTTPS_PROXY'] = original_https_proxy


if __name__ == '__main__':
    main()