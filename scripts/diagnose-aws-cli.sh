#!/bin/bash
# AWS CLI Diagnostic Script for Minio Integration

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 AWS CLI Diagnostic Tool${NC}"
echo "This script helps diagnose AWS CLI issues when connecting to Minio"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check 1: AWS CLI Installation
echo -e "${BLUE}1️⃣  Checking AWS CLI Installation${NC}"
if command_exists aws; then
    AWS_VERSION=$(aws --version 2>&1 || echo "Version detection failed")
    echo -e "${GREEN}✅ AWS CLI found${NC}"
    echo "   Version: $AWS_VERSION"

    # Check AWS CLI type (v1 vs v2)
    if echo "$AWS_VERSION" | grep -q "aws-cli/2"; then
        echo "   Type: AWS CLI v2 (recommended)"
    elif echo "$AWS_VERSION" | grep -q "aws-cli/1"; then
        echo "   Type: AWS CLI v1 (older version)"
    else
        echo -e "${YELLOW}   Type: Unknown version${NC}"
    fi
else
    echo -e "${RED}❌ AWS CLI not found${NC}"
    echo ""
    echo "📥 Installation Options:"
    echo ""
    echo "🍎 macOS:"
    echo "   brew install awscli"
    echo ""
    echo "🐧 Linux:"
    echo "   # AWS CLI v2 (recommended)"
    echo "   curl 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o 'awscliv2.zip'"
    echo "   unzip awscliv2.zip"
    echo "   sudo ./aws/install"
    echo ""
    echo "   # Or via pip"
    echo "   pip install awscli"
    echo ""
    echo "🪟 Windows:"
    echo "   Download installer from: https://aws.amazon.com/cli/"
    echo ""
    exit 1
fi

# Check 2: Basic AWS functionality
echo ""
echo -e "${BLUE}2️⃣  Testing Basic AWS Functionality${NC}"
if aws help >/dev/null 2>&1; then
    echo -e "${GREEN}✅ AWS help command works${NC}"
else
    echo -e "${RED}❌ AWS help command failed${NC}"
    echo "   This indicates a broken AWS CLI installation"
fi

# Check 3: S3 command availability
echo ""
echo -e "${BLUE}3️⃣  Testing S3 Command Availability${NC}"
if aws s3 help >/dev/null 2>&1; then
    echo -e "${GREEN}✅ AWS S3 commands available${NC}"
else
    echo -e "${RED}❌ AWS S3 commands not available${NC}"
    echo "   This might indicate an incomplete installation"

    # Try to get more specific error
    echo ""
    echo "Attempting to run aws s3 help for more details:"
    aws s3 help 2>&1 | head -10 || echo "Command failed completely"
fi

# Check 4: Python and boto3 (alternative)
echo ""
echo -e "${BLUE}4️⃣  Checking Python boto3 Alternative${NC}"
if command_exists python3; then
    echo -e "${GREEN}✅ Python3 found${NC}"

    # Check boto3 availability
    python3 -c "import boto3; print('✅ boto3 available')" 2>/dev/null || {
        echo -e "${YELLOW}⚠️  boto3 not available${NC}"
        echo "   Install with: pip install boto3"
    }
else
    echo -e "${RED}❌ Python3 not found${NC}"
fi

# Check 5: Network connectivity to Minio
echo ""
echo -e "${BLUE}5️⃣  Testing Network Connectivity to Minio${NC}"
MINIO_HOST="localhost"
MINIO_PORT="9000"

if command_exists nc; then
    if nc -z "$MINIO_HOST" "$MINIO_PORT" 2>/dev/null; then
        echo -e "${GREEN}✅ Can connect to Minio at $MINIO_HOST:$MINIO_PORT${NC}"
    else
        echo -e "${RED}❌ Cannot connect to Minio at $MINIO_HOST:$MINIO_PORT${NC}"
        echo "   Make sure Minio is running: docker-compose up -d"
    fi
elif command_exists telnet; then
    timeout 5 telnet "$MINIO_HOST" "$MINIO_PORT" </dev/null >/dev/null 2>&1 && {
        echo -e "${GREEN}✅ Can connect to Minio at $MINIO_HOST:$MINIO_PORT${NC}"
    } || {
        echo -e "${RED}❌ Cannot connect to Minio at $MINIO_HOST:$MINIO_PORT${NC}"
        echo "   Make sure Minio is running: docker-compose up -d"
    }
else
    echo -e "${YELLOW}⚠️  No network testing tools available (nc or telnet)${NC}"
    echo "   Cannot test connectivity to Minio"
fi

# Check 6: Environment variables
echo ""
echo -e "${BLUE}6️⃣  Checking Environment Variables${NC}"
if [[ -n "${AWS_ACCESS_KEY_ID:-}" ]]; then
    echo -e "${YELLOW}⚠️  AWS_ACCESS_KEY_ID is set in environment${NC}"
    echo "   This might interfere with Minio credentials"
fi

if [[ -n "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
    echo -e "${YELLOW}⚠️  AWS_SECRET_ACCESS_KEY is set in environment${NC}"
    echo "   This might interfere with Minio credentials"
fi

if [[ -n "${AWS_DEFAULT_REGION:-}" ]]; then
    echo "   AWS_DEFAULT_REGION: $AWS_DEFAULT_REGION"
fi

if [[ -n "${AWS_PROFILE:-}" ]]; then
    echo "   AWS_PROFILE: $AWS_PROFILE"
fi

# Check 7: Test simple Minio operation
echo ""
echo -e "${BLUE}7️⃣  Testing Simple Minio Operation${NC}"

# Default Minio credentials from docker-compose
MINIO_ENDPOINT="http://localhost:9000"
MINIO_ACCESS_KEY="release-monitor-user"
MINIO_SECRET_KEY="release-monitor-pass"

echo "Testing with credentials:"
echo "   Endpoint: $MINIO_ENDPOINT"
echo "   Access Key: $MINIO_ACCESS_KEY"
echo "   Secret Key: ${MINIO_SECRET_KEY:0:4}***"

# Try AWS CLI first
echo ""
echo "Trying AWS CLI..."
if aws --endpoint-url "$MINIO_ENDPOINT" \
   --aws-access-key-id "$MINIO_ACCESS_KEY" \
   --aws-secret-access-key "$MINIO_SECRET_KEY" \
   --region us-east-1 \
   s3 ls >/dev/null 2>&1; then
    echo -e "${GREEN}✅ AWS CLI can connect to Minio${NC}"
else
    echo -e "${RED}❌ AWS CLI cannot connect to Minio${NC}"

    # Show the actual error
    echo ""
    echo "Full error output:"
    aws --endpoint-url "$MINIO_ENDPOINT" \
        --aws-access-key-id "$MINIO_ACCESS_KEY" \
        --aws-secret-access-key "$MINIO_SECRET_KEY" \
        --region us-east-1 \
        s3 ls 2>&1 | head -5
fi

# Try Python boto3 as alternative
echo ""
echo "Trying Python boto3..."
python3 << EOF
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

try:
    s3_client = boto3.client(
        's3',
        endpoint_url='$MINIO_ENDPOINT',
        aws_access_key_id='$MINIO_ACCESS_KEY',
        aws_secret_access_key='$MINIO_SECRET_KEY',
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )

    # Test connection
    response = s3_client.list_buckets()
    print("✅ Python boto3 can connect to Minio")
    print(f"   Found {len(response['Buckets'])} buckets")

except Exception as e:
    print(f"❌ Python boto3 cannot connect to Minio: {e}")
EOF

# Recommendations
echo ""
echo -e "${BLUE}📋 Recommendations${NC}"
echo ""

if ! aws s3 help >/dev/null 2>&1; then
    echo -e "${YELLOW}🔧 AWS CLI Issues Detected:${NC}"
    echo "   1. Reinstall AWS CLI (preferably v2)"
    echo "   2. Check PATH configuration"
    echo "   3. Use Python boto3 as alternative"
    echo ""
fi

echo -e "${GREEN}💡 Quick Fixes:${NC}"
echo ""
echo "1. 📦 Install/Update AWS CLI:"
echo "   macOS: brew install awscli"
echo "   Linux: curl 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o 'awscliv2.zip' && unzip awscliv2.zip && sudo ./aws/install"
echo ""
echo "2. 🐍 Use Python boto3 instead:"
echo "   pip install boto3"
echo "   Use scripts with Python boto3 calls"
echo ""
echo "3. 🚀 Start Minio if not running:"
echo "   docker-compose up -d"
echo ""
echo "4. 🔍 Debug with verbose output:"
echo "   DEBUG=true ./scripts/test-minio.sh"
echo ""

echo -e "${BLUE}✨ Diagnostic complete!${NC}"
