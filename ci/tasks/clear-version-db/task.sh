#!/bin/bash

set -o errexit
set -o pipefail

# Clear Version Database Task
# Clears the entire version database from Artifactory to force re-downloads

echo "Starting version database clear operation..."

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

# Run the clear database script
echo "Clearing version database..."
python3 scripts/clear-version-db-artifactory.py

echo "Version database clear completed successfully"