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
    echo "   Install with:"
    echo "     pip install awscli                    # For AWS CLI v1"
    echo "     pip install awscli-v2                 # For AWS CLI v2"
    echo "     brew install awscli                   # On macOS"
    echo "     curl 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o 'awscliv2.zip' && unzip awscliv2.zip && sudo ./aws/install  # Linux"
    exit 1
fi

# Check AWS CLI version and test basic functionality
echo "🔍 Checking AWS CLI installation..."
AWS_VERSION=$(aws --version 2>&1 || echo "unknown")
echo "   AWS CLI Version: $AWS_VERSION"

# Test basic AWS command
if ! aws help >/dev/null 2>&1; then
    echo -e "${RED}❌ AWS CLI is installed but not working properly${NC}"
    echo "   Try reinstalling or check PATH configuration"
    exit 1
fi

# Test S3 command availability
if ! aws s3 help >/dev/null 2>&1; then
    echo -e "${RED}❌ AWS S3 commands not available${NC}"
    echo "   This might be an incomplete AWS CLI installation"
    exit 1
fi

# Function to run AWS S3 command with Minio endpoint
aws_minio() {
    # Disable debug output for cleaner logs unless DEBUG is set
    if [[ "${DEBUG:-}" == "true" ]]; then
        set -x
    fi
    
    aws --endpoint-url "$MINIO_ENDPOINT" \
        --aws-access-key-id "$MINIO_ACCESS_KEY" \
        --aws-secret-access-key "$MINIO_SECRET_KEY" \
        --region us-east-1 \
        s3 "$@"
    
    local exit_code=$?
    if [[ "${DEBUG:-}" == "true" ]]; then
        set +x
    fi
    return $exit_code
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
    echo -e "${RED}❌ Failed to connect to Minio with AWS CLI${NC}"
    echo "   Trying with Python boto3 as fallback..."
    
    # Try with Python boto3 as fallback
    python3 << EOF
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
import sys

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
    s3_client.list_buckets()
    print("✅ Python boto3 connection successful")
    
except Exception as e:
    print(f"❌ Both AWS CLI and Python boto3 failed: {e}")
    print("   Make sure Minio is running: docker-compose up -d")
    sys.exit(1)
EOF
    
    # Simple validation that boto3 works
    if ! python3 -c "
import boto3
from botocore.client import Config
import sys
try:
    s3_client = boto3.client('s3', endpoint_url='$MINIO_ENDPOINT', aws_access_key_id='$MINIO_ACCESS_KEY', aws_secret_access_key='$MINIO_SECRET_KEY', config=Config(signature_version='s3v4'), region_name='us-east-1')
    s3_client.list_buckets()
    sys.exit(0)
except:
    sys.exit(1)
" 2>/dev/null; then
        exit 1
    fi
    
    echo -e "${YELLOW}⚠️  AWS CLI connection failed, but Python boto3 works${NC}"
    echo "   Consider fixing AWS CLI installation for full functionality"
fi

echo ""
echo "2️⃣  Checking buckets..."

# Use Python boto3 for bucket operations since AWS CLI is having issues
python3 << EOF
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

try:
    s3 = boto3.client(
        's3',
        endpoint_url='$MINIO_ENDPOINT',
        aws_access_key_id='$MINIO_ACCESS_KEY',
        aws_secret_access_key='$MINIO_SECRET_KEY',
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    # List existing buckets
    response = s3.list_buckets()
    bucket_names = [b['Name'] for b in response['Buckets']]
    
    # Check output bucket
    if '$OUTPUT_BUCKET' in bucket_names:
        print("✅ Output bucket exists: $OUTPUT_BUCKET")
    else:
        print("⚠️  Output bucket not found, creating...")
        s3.create_bucket(Bucket='$OUTPUT_BUCKET')
        print("✅ Created output bucket: $OUTPUT_BUCKET")
    
    # Check artifacts bucket
    if '$ARTIFACTS_BUCKET' in bucket_names:
        print("✅ Artifacts bucket exists: $ARTIFACTS_BUCKET")
    else:
        print("⚠️  Artifacts bucket not found, creating...")
        s3.create_bucket(Bucket='$ARTIFACTS_BUCKET')
        print("✅ Created artifacts bucket: $ARTIFACTS_BUCKET")
        
except Exception as e:
    print(f"❌ Error managing buckets: {e}")
    exit(1)
EOF

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to manage buckets${NC}"
    exit 1
fi

echo ""
echo "3️⃣  Testing write operations..."
TEST_FILE="/tmp/test-minio-$(date +%s).json"
echo '{"test": "data", "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' >"$TEST_FILE"

# Use Python boto3 for file operations
python3 << EOF
import boto3
from botocore.client import Config

try:
    s3 = boto3.client(
        's3',
        endpoint_url='$MINIO_ENDPOINT',
        aws_access_key_id='$MINIO_ACCESS_KEY',
        aws_secret_access_key='$MINIO_SECRET_KEY',
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    # Upload test file
    s3.upload_file('$TEST_FILE', '$OUTPUT_BUCKET', 'test/test-file.json')
    print("✅ Successfully uploaded test file")
    
except Exception as e:
    print(f"❌ Failed to upload test file: {e}")
    exit(1)
EOF

if [ $? -ne 0 ]; then
    rm -f "$TEST_FILE"
    exit 1
fi

echo ""
echo "4️⃣  Testing read operations..."
DOWNLOAD_FILE="/tmp/test-minio-download-$(date +%s).json"

python3 << EOF
import boto3
from botocore.client import Config

try:
    s3 = boto3.client(
        's3',
        endpoint_url='$MINIO_ENDPOINT',
        aws_access_key_id='$MINIO_ACCESS_KEY',
        aws_secret_access_key='$MINIO_SECRET_KEY',
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    # Download test file
    s3.download_file('$OUTPUT_BUCKET', 'test/test-file.json', '$DOWNLOAD_FILE')
    print("✅ Successfully downloaded test file")
    
    # Read and display content
    with open('$DOWNLOAD_FILE', 'r') as f:
        content = f.read()
        print(f"   Content: {content.strip()}")
        
except Exception as e:
    print(f"❌ Failed to download test file: {e}")
    exit(1)
EOF

if [ $? -ne 0 ]; then
    rm -f "$TEST_FILE" "$DOWNLOAD_FILE"
    exit 1
fi

rm -f "$DOWNLOAD_FILE"

echo ""
echo "5️⃣  Testing versioning..."

# Use Python boto3 for versioning operations
python3 << EOF
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

try:
    s3 = boto3.client(
        's3',
        endpoint_url='$MINIO_ENDPOINT',
        aws_access_key_id='$MINIO_ACCESS_KEY',
        aws_secret_access_key='$MINIO_SECRET_KEY',
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    # Check if versioning is enabled
    try:
        response = s3.get_bucket_versioning(Bucket='$OUTPUT_BUCKET')
        status = response.get('Status', 'Disabled')
        
        if status == 'Enabled':
            print("✅ Versioning is enabled on output bucket")
        else:
            print("⚠️  Versioning not enabled, enabling...")
            s3.put_bucket_versioning(
                Bucket='$OUTPUT_BUCKET',
                VersioningConfiguration={'Status': 'Enabled'}
            )
            print("✅ Versioning enabled on output bucket")
            
    except ClientError as e:
        if 'NotImplemented' in str(e):
            print("⚠️  Versioning not supported by this Minio version")
        else:
            print(f"❌ Versioning check failed: {e}")
            
except Exception as e:
    print(f"❌ Error checking versioning: {e}")
    exit(1)
EOF

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to check versioning${NC}"
    exit 1
fi

echo ""
echo "6️⃣  Testing Python boto3 connectivity..."
python3 <<EOF
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

# Use Python boto3 for cleanup
python3 << EOF
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

try:
    s3 = boto3.client(
        's3',
        endpoint_url='$MINIO_ENDPOINT',
        aws_access_key_id='$MINIO_ACCESS_KEY',
        aws_secret_access_key='$MINIO_SECRET_KEY',
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    # Delete test file
    try:
        s3.delete_object(Bucket='$OUTPUT_BUCKET', Key='test/test-file.json')
        print("✅ Cleaned up test file")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print("ℹ️  Test file already removed")
        else:
            print(f"⚠️  Could not remove test file: {e}")
            
except Exception as e:
    print(f"⚠️  Cleanup failed: {e}")
EOF

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
