#!/bin/bash

set -o errexit
set -o pipefail

# GitHub Release Monitoring Task
# Checks repositories for new releases and outputs structured data

echo "Starting GitHub release monitoring..."

# Navigate to app directory
cd /app

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