#!/bin/bash

set -o errexit
set -o pipefail

# Fetch Monitor Output from Artifactory Task
# Downloads the latest-releases.json file from Artifactory storage

echo "Starting fetch of monitor output from Artifactory..."

# Debug: Check required environment variables
if [ -z "$ARTIFACTORY_URL" ]; then
    echo "ERROR: ARTIFACTORY_URL environment variable is not set!"
    exit 1
fi

if [ -z "$ARTIFACTORY_REPOSITORY" ]; then
    echo "ERROR: ARTIFACTORY_REPOSITORY environment variable is not set!"
    exit 1
fi

if [ -z "$ARTIFACTORY_API_KEY" ] && [ -z "$ARTIFACTORY_USERNAME" ]; then
    echo "ERROR: Either ARTIFACTORY_API_KEY or ARTIFACTORY_USERNAME/ARTIFACTORY_PASSWORD must be set!"
    exit 1
fi

echo "Artifactory URL: $ARTIFACTORY_URL"
echo "Repository: $ARTIFACTORY_REPOSITORY"

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install --quiet requests

# Set output directory (allow override via environment variable)
OUTPUT_DIR="${OUTPUT_DIR:-/monitor-output}"
echo "Output directory: $OUTPUT_DIR"

# Download latest-releases.json from Artifactory
echo "Downloading monitor output from Artifactory..."
python3 scripts/fetch-monitor-output.py --output-dir "$OUTPUT_DIR"

echo "Monitor output fetch completed successfully"