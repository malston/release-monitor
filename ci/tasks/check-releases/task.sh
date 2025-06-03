#!/bin/bash

set -o errexit
set -o pipefail

# GitHub Release Monitoring Task
# Checks repositories for new releases and outputs structured data

echo "Starting GitHub release monitoring..."

# Debug: Check if GitHub token is set
if [ -z "$GITHUB_TOKEN" ]; then
    echo "ERROR: GITHUB_TOKEN environment variable is not set!"
    exit 1
else
    echo "GitHub token is set (length: ${#GITHUB_TOKEN} characters)"
fi

# Configure proxy settings if they exist (common in corporate environments)
if [ ! -z "$HTTP_PROXY" ]; then
    echo "Configuring HTTP_PROXY: $HTTP_PROXY"
    export http_proxy=$HTTP_PROXY
fi

if [ ! -z "$HTTPS_PROXY" ]; then
    echo "Configuring HTTPS_PROXY: $HTTPS_PROXY"
    export https_proxy=$HTTPS_PROXY
fi

if [ ! -z "$NO_PROXY" ]; then
    echo "Configuring NO_PROXY: $NO_PROXY"
    export no_proxy=$NO_PROXY
fi

# Navigate to app directory
cd /app

# Test GitHub API connectivity before proceeding
echo "Testing GitHub API connectivity..."
if curl -s -f -H "Authorization: token $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github.v3+json" \
     https://api.github.com/user > /dev/null 2>&1; then
    echo "✓ GitHub API connection successful"
else
    echo "ERROR: Cannot connect to GitHub API. Debugging information:"
    echo "- Trying without auth to check network connectivity..."
    if curl -s -f https://api.github.com > /dev/null 2>&1; then
        echo "  Network is OK, but authentication failed"
        echo "  Please verify your GITHUB_TOKEN is valid"
    else
        echo "  Network connection to api.github.com failed"
        echo "  This might be a proxy/firewall issue"
    fi
    
    # Try to get more debug info
    echo "- Detailed curl output:"
    curl -v -H "Authorization: token $GITHUB_TOKEN" \
         -H "Accept: application/vnd.github.v3+json" \
         https://api.github.com/user 2>&1 | head -20
    exit 1
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt --quiet

# Create output directory
mkdir -p /release-output

# Run the monitoring script using the wrapper
echo "Running release monitoring script..."
./scripts/monitor.sh \
  --config config.yaml \
  --output /release-output/releases.json \
  --format json

# Validate output exists
if [[ ! -f "/release-output/releases.json" ]]; then
    echo "Error: Release output file not generated"
    exit 1
fi

# Display summary using Python instead of jq
python3 << 'EOF'
import json

# Read and parse the JSON output
with open('/release-output/releases.json', 'r') as f:
    data = json.load(f)

new_releases = data.get('new_releases_found', 0)
total_repos = data.get('total_repositories_checked', 0)

print(f"""Release monitoring completed:
✓ Checked {total_repos} repositories
✓ Found {new_releases} new releases""")

if new_releases > 0:
    print("\nNew releases found:")
    for release in data.get('releases', []):
        repo = release.get('repository', 'unknown')
        tag = release.get('tag_name', 'unknown')
        print(f"  - {repo}: {tag}")
EOF

echo "Release monitoring task completed successfully"