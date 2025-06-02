#!/bin/bash
# Test script for Minio connectivity and operations

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://localhost:9000}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-release-monitor-user}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-release-monitor-pass}"
OUTPUT_BUCKET="release-monitor-output"
ARTIFACTS_BUCKET="release-monitor-artifacts"

echo "🧪 Testing Minio connectivity..."
echo "   Endpoint: $MINIO_ENDPOINT"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for required tools
if ! command_exists aws; then
    echo -e "${RED}❌ AWS CLI not found. Please install it first.${NC}"
    echo "   Install with: pip install awscli"
    exit 1
fi

# Function to run AWS S3 command with Minio endpoint
aws_minio() {
    aws --endpoint-url "$MINIO_ENDPOINT" \
        --aws-access-key-id "$MINIO_ACCESS_KEY" \
        --aws-secret-access-key "$MINIO_SECRET_KEY" \
        --region us-east-1 \
        s3 "$@"
}

# Function to run AWS S3API command with Minio endpoint
aws_minio_api() {
    aws --endpoint-url "$MINIO_ENDPOINT" \
        --aws-access-key-id "$MINIO_ACCESS_KEY" \
        --aws-secret-access-key "$MINIO_SECRET_KEY" \
        --region us-east-1 \
        s3api "$@"
}

echo "1️⃣  Testing connection to Minio..."
if aws_minio ls >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Successfully connected to Minio${NC}"
else
    echo -e "${RED}❌ Failed to connect to Minio${NC}"
    echo "   Make sure Minio is running: docker-compose up -d"
    exit 1
fi

echo ""
echo "2️⃣  Checking buckets..."
if aws_minio ls | grep -q "$OUTPUT_BUCKET"; then
    echo -e "${GREEN}✅ Output bucket exists: $OUTPUT_BUCKET${NC}"
else
    echo -e "${YELLOW}⚠️  Output bucket not found, creating...${NC}"
    aws_minio mb "s3://$OUTPUT_BUCKET"
fi

if aws_minio ls | grep -q "$ARTIFACTS_BUCKET"; then
    echo -e "${GREEN}✅ Artifacts bucket exists: $ARTIFACTS_BUCKET${NC}"
else
    echo -e "${YELLOW}⚠️  Artifacts bucket not found, creating...${NC}"
    aws_minio mb "s3://$ARTIFACTS_BUCKET"
fi

echo ""
echo "3️⃣  Testing write operations..."
TEST_FILE="/tmp/test-minio-$(date +%s).json"
echo '{"test": "data", "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$TEST_FILE"

if aws_minio cp "$TEST_FILE" "s3://$OUTPUT_BUCKET/test/test-file.json"; then
    echo -e "${GREEN}✅ Successfully uploaded test file${NC}"
else
    echo -e "${RED}❌ Failed to upload test file${NC}"
    rm -f "$TEST_FILE"
    exit 1
fi

echo ""
echo "4️⃣  Testing read operations..."
DOWNLOAD_FILE="/tmp/test-minio-download-$(date +%s).json"
if aws_minio cp "s3://$OUTPUT_BUCKET/test/test-file.json" "$DOWNLOAD_FILE"; then
    echo -e "${GREEN}✅ Successfully downloaded test file${NC}"
    echo "   Content: $(cat "$DOWNLOAD_FILE")"
    rm -f "$DOWNLOAD_FILE"
else
    echo -e "${RED}❌ Failed to download test file${NC}"
    rm -f "$TEST_FILE"
    exit 1
fi

echo ""
echo "5️⃣  Testing versioning..."
if aws_minio_api get-bucket-versioning --bucket "$OUTPUT_BUCKET" 2>/dev/null | grep -q "Enabled"; then
    echo -e "${GREEN}✅ Versioning is enabled on output bucket${NC}"
else
    echo -e "${YELLOW}⚠️  Versioning not enabled, enabling...${NC}"
    aws_minio_api put-bucket-versioning --bucket "$OUTPUT_BUCKET" \
        --versioning-configuration Status=Enabled
fi

echo ""
echo "6️⃣  Testing Python boto3 connectivity..."
python3 << EOF
import boto3
from botocore.client import Config

try:
    # Create S3 client for Minio
    s3_client = boto3.client(
        's3',
        endpoint_url='$MINIO_ENDPOINT',
        aws_access_key_id='$MINIO_ACCESS_KEY',
        aws_secret_access_key='$MINIO_SECRET_KEY',
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    # List buckets
    response = s3_client.list_buckets()
    print("✅ Python boto3 connection successful")
    print(f"   Found {len(response['Buckets'])} buckets")
    
except Exception as e:
    print(f"❌ Python boto3 connection failed: {e}")
    exit(1)
EOF

echo ""
echo "7️⃣  Cleaning up test files..."
aws_minio rm "s3://$OUTPUT_BUCKET/test/test-file.json" 2>/dev/null || true
rm -f "$TEST_FILE"

echo ""
echo -e "${GREEN}🎉 All Minio tests passed!${NC}"
echo ""
echo "📋 Configuration Summary:"
echo "   - Endpoint: $MINIO_ENDPOINT"
echo "   - Access Key: $MINIO_ACCESS_KEY"
echo "   - Output Bucket: $OUTPUT_BUCKET"
echo "   - Artifacts Bucket: $ARTIFACTS_BUCKET"
echo ""
echo "🚀 Ready to use with release-monitor!"