#!/bin/bash

set -o errexit
set -o pipefail

# Show Version Database Task
# Displays the current contents of the version database from multiple storage backends
# Auto-detects backend: Artifactory, S3/MinIO, or Local file

echo "Starting version database display..."

# Detect storage backend and show configuration
if [[ -n "$ARTIFACTORY_URL" && -n "$ARTIFACTORY_REPOSITORY" ]]; then
    echo "Detected storage backend: Artifactory"
    echo "Artifactory URL: $ARTIFACTORY_URL"
    echo "Repository: $ARTIFACTORY_REPOSITORY"

    # Validate Artifactory authentication
    if [[ -z "$ARTIFACTORY_API_KEY" && -z "$ARTIFACTORY_USERNAME" ]]; then
        echo "ERROR: Either ARTIFACTORY_API_KEY or ARTIFACTORY_USERNAME/ARTIFACTORY_PASSWORD must be set!"
        exit 1
    fi

    # Install requests for Artifactory
    echo "Installing Python dependencies for Artifactory..."
    pip3 install --quiet requests

elif [[ -n "$VERSION_DB_S3_BUCKET" ]]; then
    echo "Detected storage backend: S3/MinIO"
    echo "S3 Bucket: $VERSION_DB_S3_BUCKET"
    echo "S3 Prefix: ${VERSION_DB_S3_PREFIX:-release-monitor/}"

    if [[ -n "$S3_ENDPOINT" ]]; then
        echo "S3 Endpoint: $S3_ENDPOINT"
    fi

    # Validate S3 credentials
    if [[ -z "$AWS_ACCESS_KEY_ID" && -z "$AWS_SECRET_ACCESS_KEY" ]]; then
        echo "WARNING: AWS credentials not found. Make sure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are set"
    fi

    # Install boto3 for S3
    echo "Installing Python dependencies for S3..."
    pip3 install --quiet boto3

else
    echo "Detected storage backend: Local file"

    # Check for common version database file locations
    POSSIBLE_PATHS=(
        "${VERSION_DB_PATH}"
        "${DOWNLOAD_DIR:-./downloads}/version_db.json"
        "./downloads/version_db.json"
        "./version_db.json"
    )

    FOUND_PATH=""
    for path in "${POSSIBLE_PATHS[@]}"; do
        if [[ -n "$path" && -f "$path" ]]; then
            FOUND_PATH="$path"
            break
        fi
    done

    if [[ -n "$FOUND_PATH" ]]; then
        echo "Found version database at: $FOUND_PATH"
    else
        echo "WARNING: No version database file found in common locations"
        echo "Checked paths: ${POSSIBLE_PATHS[*]}"
    fi
fi

# Run the unified show database script
echo "Displaying version database contents..."
python3 scripts/show-version-db.py --verbose

echo "Version database display completed successfully"
