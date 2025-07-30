#!/bin/bash

set -o errexit
set -o pipefail

# Upload to Artifactory Task
# Uploads downloaded release artifacts to Artifactory storage

echo "Starting upload of release artifacts to Artifactory..."

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

# Run the upload script
echo "Uploading artifacts to Artifactory..."
python3 scripts/upload-to-artifactory.py

echo "Artifact upload completed successfully"