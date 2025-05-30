#!/bin/sh

set -e

# GitHub Release Tarball Download Task
# Downloads release tarballs and uploads them to S3

echo "Starting tarball download and S3 upload process..."

# Install required tools
echo "Installing required tools..."
apk add --no-cache jq aws-cli curl

RELEASES_FILE="/input/releases.json"

# Validate input file exists
if [ ! -f "$RELEASES_FILE" ]; then
    echo "No releases file found at: $RELEASES_FILE"
    exit 0
fi

# Check for new releases
NEW_RELEASES=$(jq -r '.new_releases_found' "$RELEASES_FILE")
echo "Processing $NEW_RELEASES new releases"

if [ "$NEW_RELEASES" -eq 0 ]; then
    echo "No new releases to process - task completed"
    exit 0
fi

# Validate required environment variables
if [ -z "$S3_BUCKET" ] || [ -z "$S3_REGION" ]; then
    echo "Error: S3_BUCKET and S3_REGION environment variables are required"
    exit 1
fi

echo "Using S3 bucket: $S3_BUCKET (region: $S3_REGION)"

# Create tarballs directory
mkdir -p /tarballs

# Process each new release
echo "Processing releases..."
jq -c '.releases[]' "$RELEASES_FILE" | while read -r release; do
    REPO=$(echo "$release" | jq -r '.repository')
    TAG=$(echo "$release" | jq -r '.tag_name')
    TARBALL_URL=$(echo "$release" | jq -r '.tarball_url')
    
    echo ""
    echo "Processing: $REPO:$TAG"
    echo "  Tarball URL: $TARBALL_URL"
    
    # Create safe filename
    SAFE_REPO=$(echo "$REPO" | tr '/' '-')
    TARBALL_FILE="${SAFE_REPO}-${TAG}.tar.gz"
    LOCAL_PATH="/tarballs/$TARBALL_FILE"
    S3_PATH="s3://$S3_BUCKET/tarballs/$SAFE_REPO/$TARBALL_FILE"
    
    # Download tarball
    echo "  Downloading tarball..."
    if curl -L -o "$LOCAL_PATH" "$TARBALL_URL"; then
        echo "  ✓ Download successful"
        
        # Verify file was downloaded and has content
        if [ -s "$LOCAL_PATH" ]; then
            FILE_SIZE=$(du -h "$LOCAL_PATH" | cut -f1)
            echo "  File size: $FILE_SIZE"
            
            # Upload to S3
            echo "  Uploading to S3: $S3_PATH"
            if aws s3 cp "$LOCAL_PATH" "$S3_PATH" --region "$S3_REGION"; then
                echo "  ✓ Upload successful"
                
                # Clean up local file to save space
                rm "$LOCAL_PATH"
            else
                echo "  ✗ Upload failed"
                exit 1
            fi
        else
            echo "  ✗ Downloaded file is empty"
            exit 1
        fi
    else
        echo "  ✗ Download failed"
        exit 1
    fi
done

echo ""
echo "Tarball download and upload task completed successfully"