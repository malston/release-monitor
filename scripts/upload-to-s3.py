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
from pathlib import Path


def main():
    """Upload release files to S3 storage."""

    # Configure S3 client with SSL verification settings
    endpoint_url = os.environ.get('S3_ENDPOINT')
    skip_ssl_verification = os.environ.get('S3_SKIP_SSL_VERIFICATION', 'false').lower() == 'true'

    # Check for proxy settings
    http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
    https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
    no_proxy = os.environ.get('NO_PROXY') or os.environ.get('no_proxy')

    if http_proxy or https_proxy:
        print(f'Proxy detected:')
        print(f'  HTTP_PROXY: {http_proxy}')
        print(f'  HTTPS_PROXY: {https_proxy}')
        print(f'  NO_PROXY: {no_proxy}')

        # Check if S3 endpoint should bypass proxy
        if endpoint_url and 'example.com' in endpoint_url:
            if not no_proxy or 'example.com' not in no_proxy:
                print(f'WARNING: S3 endpoint {endpoint_url} may be going through proxy')
                print(f'Consider adding your S3 domain to NO_PROXY environment variable')

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

    # Find and upload all release files
    # Check multiple possible locations for the downloads directory
    possible_paths = [
        Path('/tmp/downloads'),           # Absolute path used by pipeline
        Path('../downloads'),             # Relative path from scripts/
        Path('downloads'),                # Current directory
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

                # Read file data
                with open(file_path, 'rb') as f:
                    file_data = f.read()

                # Try with explicit headers and metadata
                content_length = len(file_data)
                print(f'  Content-Length: {content_length}')

                # Use put_object with all possible parameters
                response = s3.put_object(
                    Bucket=bucket,
                    Key=s3_key,
                    Body=file_data,
                    ContentLength=content_length,
                    ContentType='application/octet-stream',
                    ContentEncoding='identity',
                    Metadata={
                        'uploaded-by': 'release-monitor',
                        'original-size': str(content_length)
                    }
                )
                print(f'  Upload response: {response.get("ResponseMetadata", {}).get("HTTPStatusCode")}')
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
