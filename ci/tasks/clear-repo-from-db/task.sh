#!/bin/bash

set -o errexit
set -o pipefail

# Clear Repository from Database Task
# Removes a specific repository from the version database to force re-download

echo "Starting repository clear operation from version database..."

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

# Validate repository parameter
if [ -z "$REPO_NAME" ]; then
    echo "Error: REPO_NAME parameter is required"
    echo "Usage: fly trigger-job -j pipeline-name/force-download-repo -v force_download_repo=\"owner/repo\""
    exit 1
fi

echo "Target repository: $REPO_NAME"

# Clear the specific repository from version database
echo "Clearing $REPO_NAME from version database..."
python3 scripts/clear-version-entry-artifactory.py "$REPO_NAME" || {
    echo "Failed to clear repository from database, but continuing..."
    exit 0  # Don't fail the entire job if this step fails
}

echo "Repository clear operation completed successfully"