#!/usr/bin/env python3
"""
Direct S3 upload using requests library for maximum control over headers.
This bypasses boto3's automatic header handling which may not work with
some S3-compatible services.
"""

import os
import requests
import hashlib
import hmac
import base64
from datetime import datetime
from urllib.parse import quote


def sign_request(method, canonical_uri, canonical_querystring, canonical_headers, 
                signed_headers, payload_hash, access_key, secret_key, region='us-east-1'):
    """Create AWS Signature Version 4 for S3 request."""
    
    # Create the string to sign
    algorithm = 'AWS4-HMAC-SHA256'
    credential_scope = f"{datetime.utcnow().strftime('%Y%m%d')}/{region}/s3/aws4_request"
    
    canonical_request = f"{method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
    
    string_to_sign = f"{algorithm}\n{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode()).hexdigest()}"
    
    # Create the signing key
    def sign(key, msg):
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
    
    date_key = sign(('AWS4' + secret_key).encode('utf-8'), datetime.utcnow().strftime('%Y%m%d'))
    date_region_key = sign(date_key, region)
    date_region_service_key = sign(date_region_key, 's3')
    signing_key = sign(date_region_service_key, 'aws4_request')
    
    # Create the signature
    signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
    
    return signature


def direct_s3_upload(bucket, key, data, content_type='application/octet-stream', 
                    endpoint_url=None, access_key=None, secret_key=None, verify_ssl=True):
    """
    Upload data directly to S3 using requests with explicit Content-Length.
    
    Args:
        bucket: S3 bucket name
        key: S3 object key
        data: Data to upload (bytes)
        content_type: MIME type
        endpoint_url: S3 endpoint URL
        access_key: AWS access key
        secret_key: AWS secret key
        verify_ssl: Whether to verify SSL certificates
    
    Returns:
        requests.Response object
    """
    
    # Get credentials from environment if not provided
    if not access_key:
        access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    if not secret_key:
        secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    
    if not access_key or not secret_key:
        raise ValueError("AWS credentials not provided")
    
    # Build URL
    if endpoint_url:
        # Remove protocol and port from endpoint for host header
        host = endpoint_url.replace('https://', '').replace('http://', '')
        if ':' in host:
            host = host.split(':')[0]
        url = f"{endpoint_url}/{bucket}/{key}"
    else:
        host = f"{bucket}.s3.amazonaws.com"
        url = f"https://{host}/{key}"
    
    # Calculate content hash
    content_hash = hashlib.sha256(data).hexdigest()
    content_length = len(data)
    
    # Prepare headers with explicit Content-Length
    timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    date = datetime.utcnow().strftime('%Y%m%d')
    
    headers = {
        'Host': host,
        'Content-Type': content_type,
        'Content-Length': str(content_length),
        'X-Amz-Content-Sha256': content_hash,
        'X-Amz-Date': timestamp,
    }
    
    # Create canonical request components
    canonical_uri = f"/{key}"
    canonical_querystring = ""
    canonical_headers = ""
    signed_headers = ""
    
    # Sort headers and create canonical form
    sorted_headers = sorted(headers.items())
    for header_name, header_value in sorted_headers:
        canonical_headers += f"{header_name.lower()}:{header_value}\n"
        if signed_headers:
            signed_headers += ";"
        signed_headers += header_name.lower()
    
    # Sign the request (simplified version - you may need full AWS4 signing)
    auth_header = f"AWS {access_key}:{base64.b64encode(hmac.new(secret_key.encode(), f'PUT\n\n{content_type}\n{timestamp}\n/{bucket}/{key}'.encode(), hashlib.sha1).digest()).decode()}"
    headers['Authorization'] = auth_header
    
    # Make the request
    try:
        response = requests.put(
            url,
            data=data,
            headers=headers,
            verify=verify_ssl,
            timeout=300  # 5 minute timeout
        )
        return response
    except Exception as e:
        print(f"Direct upload failed: {e}")
        raise


if __name__ == '__main__':
    # Test the direct upload
    test_data = b"Hello, World!"
    try:
        response = direct_s3_upload(
            bucket='test-bucket',
            key='test-key.txt',
            data=test_data,
            content_type='text/plain',
            endpoint_url=os.environ.get('S3_ENDPOINT'),
            verify_ssl=os.environ.get('S3_SKIP_SSL_VERIFICATION', 'false').lower() != 'true'
        )
        print(f"Upload response: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
    except Exception as e:
        print(f"Test failed: {e}")