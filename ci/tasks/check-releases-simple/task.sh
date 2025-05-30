#!/bin/bash

set -o errexit
set -o pipefail

# GitHub Release Monitoring Task (Simple Version)
# Checks repositories for new releases without S3 dependencies

echo "Starting GitHub release monitoring (simple mode)..."

# Navigate to app directory
cd /app

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt --quiet

# Create output directory
mkdir -p /release-output

# Run the monitoring script without S3 storage
echo "Running release monitoring script..."
export GITHUB_TOKEN="${GITHUB_TOKEN}"

# Use local file-based storage instead of S3
python3 github_monitor.py \
  --config "${CONFIG_FILE}" \
  --output-format json \
  --output-file /release-output/releases.json \
  --force-check

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

print(f"""Release monitoring completed (simple mode):
✓ Checked {total_repos} repositories
✓ Found {new_releases} new releases
✓ Using local file storage (no S3 required)""")

if new_releases > 0:
    print("\nNew releases found:")
    for release in data.get('releases', []):
        repo = release.get('repository', 'unknown')
        tag = release.get('tag_name', 'unknown')
        print(f"  - {repo}: {tag}")
else:
    print("\n✓ All repositories are up to date")

print(f"\nDetailed results available in: /release-output/releases.json")
EOF

echo "Release monitoring task completed successfully (simple mode)"