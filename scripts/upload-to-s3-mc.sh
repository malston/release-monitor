#!/bin/bash
# Upload release files to S3 using MinIO client (mc)
# This is more compatible with S3-compatible services than boto3

set -e

# S3 configuration from environment
S3_ENDPOINT="${S3_ENDPOINT:-https://cml-clfn.s3.cf.example.com:443}"
S3_BUCKET="${S3_BUCKET:-release-monitor-artifacts}"
AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}"
AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}"

# SSL verification
if [[ "${S3_SKIP_SSL_VERIFICATION}" == "true" ]]; then
    INSECURE="--insecure"
    echo "WARNING: Skipping SSL verification for S3 endpoint"
else
    INSECURE=""
fi

echo "Configuring mc for S3-compatible endpoint..."
echo "Endpoint: ${S3_ENDPOINT}"
echo "Bucket: ${S3_BUCKET}"

# Configure mc alias for the S3 endpoint
# Using a unique alias name to avoid conflicts
ALIAS="s3upload"
mc alias set ${ALIAS} ${S3_ENDPOINT} ${AWS_ACCESS_KEY_ID} ${AWS_SECRET_ACCESS_KEY} ${INSECURE}

# Find the downloads directory
if [[ -d "/tmp/downloads" ]]; then
    DOWNLOADS_DIR="/tmp/downloads"
elif [[ -d "../downloads" ]]; then
    DOWNLOADS_DIR="../downloads"
elif [[ -d "downloads" ]]; then
    DOWNLOADS_DIR="downloads"
else
    echo "ERROR: Could not find downloads directory!"
    exit 1
fi

echo "Using downloads directory: ${DOWNLOADS_DIR}"

# Create the target path in the bucket
TARGET_PATH="${ALIAS}/${S3_BUCKET}/release-downloads/"

# Upload all .gz and .zip files, preserving directory structure
echo "Starting upload to ${TARGET_PATH}..."
echo ""

# Count files for progress tracking
TOTAL_FILES=$(find ${DOWNLOADS_DIR} -type f \( -name "*.gz" -o -name "*.zip" \) | wc -l)
UPLOADED=0

# Upload files
find ${DOWNLOADS_DIR} -type f \( -name "*.gz" -o -name "*.zip" \) | while read file; do
    # Get relative path from downloads directory
    REL_PATH="${file#${DOWNLOADS_DIR}/}"
    
    echo "Uploading: ${REL_PATH}"
    
    # Upload file preserving directory structure
    if mc cp ${INSECURE} "${file}" "${TARGET_PATH}${REL_PATH}"; then
        ((UPLOADED++)) || true
        echo "  ✓ Success"
    else
        echo "  ✗ Failed"
    fi
    echo ""
done

echo "=========================================="
echo "Upload complete!"
echo "Total files found: ${TOTAL_FILES}"
echo "Successfully uploaded: ${UPLOADED}"
echo "=========================================="

# Optional: List uploaded files
echo ""
echo "Listing uploaded files:"
mc ls ${INSECURE} ${TARGET_PATH} --recursive | grep -E "\\.(gz|zip)$" | tail -20

# Clean up alias
mc alias rm ${ALIAS}