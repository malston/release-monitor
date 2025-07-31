#!/bin/bash
# Alternative upload script using AWS CLI instead of boto3
# This might work better with S3-compatible services

set -e

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "AWS CLI not found. Installing..."
    pip install awscli
fi

# Configure AWS CLI with environment variables
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"

# S3 endpoint and bucket
S3_ENDPOINT="${S3_ENDPOINT:-}"
S3_BUCKET="${S3_BUCKET}"

# SSL verification
if [[ "${S3_SKIP_SSL_VERIFICATION}" == "true" ]]; then
    NO_VERIFY="--no-verify-ssl"
else
    NO_VERIFY=""
fi

# Build AWS CLI options
AWS_OPTS=""
if [[ -n "${S3_ENDPOINT}" ]]; then
    AWS_OPTS="--endpoint-url ${S3_ENDPOINT}"
fi

echo "Uploading files to S3 using AWS CLI..."
echo "Endpoint: ${S3_ENDPOINT:-AWS S3}"
echo "Bucket: ${S3_BUCKET}"

# Find and upload files
UPLOAD_COUNT=0

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
cd "${DOWNLOADS_DIR}"

for file in $(find . -type f \( -name "*.gz" -o -name "*.zip" \) ); do
    # Remove leading ./
    relative_path="${file#./}"
    s3_key="release-downloads/${relative_path}"

    echo "Uploading ${relative_path} to s3://${S3_BUCKET}/${s3_key}"

    if aws s3 cp "${file}" "s3://${S3_BUCKET}/${s3_key}" ${AWS_OPTS} ${NO_VERIFY}; then
        echo "  Success!"
        ((UPLOAD_COUNT++))
    else
        echo "  Failed!"
    fi
done

echo ""
echo "Uploaded ${UPLOAD_COUNT} files to S3"
