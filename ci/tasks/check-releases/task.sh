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

# Display summary
NEW_RELEASES=$(jq '.new_releases_found' /release-output/releases.json)
TOTAL_REPOS=$(jq '.total_repositories_checked' /release-output/releases.json)

cat <<EOF
Release monitoring completed:
✓ Checked ${TOTAL_REPOS} repositories
✓ Found ${NEW_RELEASES} new releases
EOF

if [[ "${NEW_RELEASES}" -gt 0 ]]; then
    echo ""
    echo "New releases found:"
    jq -r '.releases[] | "  - \(.repository): \(.tag_name)"' /release-output/releases.json
fi

echo "Release monitoring task completed successfully"