#!/usr/bin/env python3
"""
Test script to verify proxy and SSL settings for GitHub downloads.
"""

import os
import requests
import urllib3

# Test environment variables
print("=== Environment Variables ===")
print(f"HTTP_PROXY: {os.getenv('HTTP_PROXY', 'Not set')}")
print(f"HTTPS_PROXY: {os.getenv('HTTPS_PROXY', 'Not set')}")
print(f"NO_PROXY: {os.getenv('NO_PROXY', 'Not set')}")
print(f"GITHUB_SKIP_SSL_VERIFICATION: {os.getenv('GITHUB_SKIP_SSL_VERIFICATION', 'Not set')}")
print()

# Create a session with proper configuration
session = requests.Session()

# Configure proxy settings
proxy_settings = {}
if os.getenv('HTTP_PROXY') or os.getenv('http_proxy'):
    proxy_settings['http'] = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
if os.getenv('HTTPS_PROXY') or os.getenv('https_proxy'):
    proxy_settings['https'] = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')

if proxy_settings:
    session.proxies = proxy_settings
    print(f"Configured proxy settings: {proxy_settings}")

# Configure SSL verification
skip_ssl_verification = os.environ.get('GITHUB_SKIP_SSL_VERIFICATION', 'false').lower() == 'true'
if skip_ssl_verification:
    print("SSL verification disabled")
    session.verify = False
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
else:
    print("SSL verification enabled")

print()

# Test URLs
test_urls = [
    {
        'name': 'GitHub API',
        'url': 'https://api.github.com'
    },
    {
        'name': 'GitHub Release (will redirect)',
        'url': 'https://github.com/wavefrontHQ/observability-for-kubernetes/releases/download/v2.30.0/wavefront-operator.yaml'
    }
]

print("=== Testing Connections ===")
for test in test_urls:
    print(f"\nTesting {test['name']}: {test['url']}")
    try:
        # Test with allow_redirects=False first to see the redirect
        response = session.get(test['url'], allow_redirects=False, timeout=10)
        print(f"  Initial response: {response.status_code}")
        
        if response.status_code in [301, 302, 303, 307, 308]:
            redirect_url = response.headers.get('Location')
            print(f"  Redirect to: {redirect_url}")
            
            # Follow the redirect
            print(f"  Following redirect...")
            final_response = session.get(redirect_url, timeout=10)
            print(f"  Final response: {final_response.status_code}")
            print(f"  Content type: {final_response.headers.get('content-type', 'Not specified')}")
            print(f"  Content length: {final_response.headers.get('content-length', 'Not specified')} bytes")
        else:
            print(f"  Content type: {response.headers.get('content-type', 'Not specified')}")
            
    except requests.exceptions.SSLError as e:
        print(f"  SSL Error: {str(e)}")
        print(f"  This suggests SSL verification is still enabled for this domain")
    except requests.exceptions.ProxyError as e:
        print(f"  Proxy Error: {str(e)}")
    except requests.exceptions.ConnectionError as e:
        print(f"  Connection Error: {str(e)}")
    except Exception as e:
        print(f"  Error: {type(e).__name__}: {str(e)}")

print("\n=== Recommendations ===")
print("1. Ensure GITHUB_SKIP_SSL_VERIFICATION=true is set")
print("2. Ensure HTTP_PROXY and HTTPS_PROXY are properly configured")
print("3. Check if objects.githubusercontent.com needs to be in NO_PROXY")
print("4. Consider using curl with -k flag as a workaround if Python requests fails")