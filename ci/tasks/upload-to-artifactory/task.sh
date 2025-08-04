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

# Check for authentication - either API key or username/password
if [ -z "$ARTIFACTORY_API_KEY" ] && [ -z "$ARTIFACTORY_USERNAME" ]; then
    echo "ERROR: Either ARTIFACTORY_API_KEY or ARTIFACTORY_USERNAME/ARTIFACTORY_PASSWORD must be set!"
    exit 1
fi

if [ -n "$ARTIFACTORY_API_KEY" ]; then
    echo "Using API key authentication"
elif [ -n "$ARTIFACTORY_USERNAME" ] && [ -n "$ARTIFACTORY_PASSWORD" ]; then
    echo "Using username/password authentication"
fi

echo "Artifactory URL: $ARTIFACTORY_URL"
echo "Repository: $ARTIFACTORY_REPOSITORY"

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install --quiet requests PyYAML

# Set default config path if not provided
CONFIG_PATH="${CONFIG_PATH:-config.yaml}"
echo "Using configuration file: $CONFIG_PATH"

# Run the upload script with configuration
echo "Uploading artifacts to Artifactory..."
python3 scripts/upload-to-artifactory.py --config "$CONFIG_PATH"

echo "Artifact upload completed successfully"
