#!/usr/bin/env python3
"""
Clear the entire S3 version database.

This script deletes the version database file from S3-compatible storage,
forcing all releases to be re-downloaded on the next pipeline run.
"""

import os
import sys
import boto3


def main():
    """Clear the entire version database from S3 storage."""
    
    endpoint_url = os.environ.get('S3_ENDPOINT')
    s3_kwargs = {
        'region_name': 'us-east-1'
    }
    if endpoint_url:
        s3_kwargs['endpoint_url'] = endpoint_url
        print(f'Using S3-compatible endpoint: {endpoint_url}')
    
    s3 = boto3.client('s3', **s3_kwargs)
    bucket = os.environ['S3_BUCKET']
    
    # Delete the version database
    try:
        s3.delete_object(Bucket=bucket, Key='version-db/version_db.json')
        print(f'Successfully cleared version database from s3://{bucket}/version-db/version_db.json')
        print('Next pipeline run will download all releases as new')
    except Exception as e:
        print(f'Error clearing version database: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()