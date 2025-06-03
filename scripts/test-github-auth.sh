#!/bin/bash
# Test GitHub API authentication and connectivity
# This script helps diagnose 401 Unauthorized errors

set -e

echo "=== GitHub API Authentication Test ==="
echo

# Check if token is set
if [ -z "$GITHUB_TOKEN" ]; then
    echo "ERROR: GITHUB_TOKEN environment variable is not set"
    echo "Please set: export GITHUB_TOKEN='your-github-token'"
    exit 1
fi

echo "✓ GitHub token is set (${#GITHUB_TOKEN} characters)"
echo

# Display proxy settings if configured
if [ ! -z "$HTTP_PROXY" ] || [ ! -z "$HTTPS_PROXY" ]; then
    echo "Proxy configuration detected:"
    [ ! -z "$HTTP_PROXY" ] && echo "  HTTP_PROXY: $HTTP_PROXY"
    [ ! -z "$HTTPS_PROXY" ] && echo "  HTTPS_PROXY: $HTTPS_PROXY"
    [ ! -z "$NO_PROXY" ] && echo "  NO_PROXY: $NO_PROXY"
    echo
fi

# Test 1: Basic API connectivity (no auth)
echo "Test 1: Checking network connectivity to GitHub API..."
if curl -s -f https://api.github.com > /dev/null 2>&1; then
    echo "✓ Network connection successful"
else
    echo "✗ Cannot reach api.github.com"
    echo "  This might be a network/firewall issue"
    exit 1
fi
echo

# Test 2: Authenticated API call
echo "Test 2: Testing authenticated API access..."
RESPONSE=$(curl -s -w "\n%{http_code}" -H "Authorization: token $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github.v3+json" \
     https://api.github.com/user 2>&1)

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ Authentication successful"
    USERNAME=$(echo "$BODY" | grep -o '"login":"[^"]*' | cut -d'"' -f4)
    echo "  Authenticated as: $USERNAME"
else
    echo "✗ Authentication failed (HTTP $HTTP_CODE)"
    echo "  Response: $BODY"
    
    if [ "$HTTP_CODE" = "401" ]; then
        echo
        echo "Possible causes:"
        echo "  1. Invalid or expired GitHub token"
        echo "  2. Token lacks necessary permissions"
        echo "  3. Token format is incorrect (should not include 'Bearer' prefix)"
        echo
        echo "To create a new token:"
        echo "  1. Go to https://github.com/settings/tokens"
        echo "  2. Click 'Generate new token (classic)'"
        echo "  3. Select 'repo' scope for private repos, or no scopes for public repos only"
    fi
fi
echo

# Test 3: Check rate limit
echo "Test 3: Checking API rate limit..."
RATE_LIMIT=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github.v3+json" \
     https://api.github.com/rate_limit 2>&1)

if echo "$RATE_LIMIT" | grep -q "rate"; then
    REMAINING=$(echo "$RATE_LIMIT" | grep -o '"remaining":[0-9]*' | head -1 | cut -d: -f2)
    LIMIT=$(echo "$RATE_LIMIT" | grep -o '"limit":[0-9]*' | head -1 | cut -d: -f2)
    echo "✓ Rate limit: $REMAINING/$LIMIT requests remaining"
else
    echo "✗ Could not check rate limit"
fi
echo

# Test 4: Test specific repository access
echo "Test 4: Testing access to kubernetes/kubernetes repository..."
K8S_RESPONSE=$(curl -s -w "\n%{http_code}" -H "Authorization: token $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github.v3+json" \
     https://api.github.com/repos/kubernetes/kubernetes/releases/latest 2>&1)

K8S_CODE=$(echo "$K8S_RESPONSE" | tail -n1)

if [ "$K8S_CODE" = "200" ]; then
    echo "✓ Can access kubernetes/kubernetes releases"
else
    echo "✗ Cannot access kubernetes/kubernetes releases (HTTP $K8S_CODE)"
    if [ "$K8S_CODE" = "404" ]; then
        echo "  Note: This might mean the repository has no releases"
    fi
fi
echo

# Test 5: Python requests library test
echo "Test 5: Testing Python requests library with proxy settings..."
python3 << 'EOF'
import os
import sys
import requests

# Set up session like github_monitor.py does
session = requests.Session()
session.headers.update({
    'Authorization': f'token {os.getenv("GITHUB_TOKEN")}',
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': 'GitHub-Release-Monitor/1.0'
})

# Configure proxy settings from environment if present
proxy_settings = {}
if os.getenv('HTTP_PROXY') or os.getenv('http_proxy'):
    proxy_settings['http'] = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
if os.getenv('HTTPS_PROXY') or os.getenv('https_proxy'):
    proxy_settings['https'] = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')

if proxy_settings:
    session.proxies = proxy_settings
    print(f"  Using proxy settings: {list(proxy_settings.keys())}")

try:
    response = session.get('https://api.github.com/user')
    if response.status_code == 200:
        print("✓ Python requests library works correctly")
    else:
        print(f"✗ Python requests returned HTTP {response.status_code}")
        print(f"  Response: {response.text[:200]}")
except Exception as e:
    print(f"✗ Python requests failed: {e}")
EOF
echo

echo "=== Test Summary ==="
echo "If all tests passed, your GitHub token and network configuration are correct."
echo "If you're still getting 401 errors, check:"
echo "  1. The token is being passed correctly to the Concourse pipeline"
echo "  2. No special characters in the token are being escaped incorrectly"
echo "  3. The Concourse worker has the correct proxy settings"