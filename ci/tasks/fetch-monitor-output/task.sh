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

if [ -z "$ARTIFACTORY_API_KEY" ]; then
    echo "ERROR: ARTIFACTORY_API_KEY environment variable is not set!"
    exit 1
fi

echo "Artifactory URL: $ARTIFACTORY_URL"
echo "Repository: $ARTIFACTORY_REPOSITORY"

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install --quiet requests

# Create output directory
mkdir -p /monitor-output

# Download latest-releases.json from Artifactory
echo "Downloading monitor output from Artifactory..."
python3 scripts/fetch-monitor-output.py

echo "Monitor output fetch completed successfully"