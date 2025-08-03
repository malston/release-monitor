#!/bin/bash
# Script to set up Minio credentials in Concourse

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "🔐 Setting up Minio credentials for Concourse"
echo ""

# Default values (from docker-compose.yml)
DEFAULT_MINIO_ENDPOINT="http://localhost:9000"
DEFAULT_MINIO_ACCESS_KEY="release-monitor-user"
DEFAULT_MINIO_SECRET_KEY="release-monitor-pass"

# Function to check if credhub is available
check_credhub() {
    if command -v credhub >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to check if vault is available
check_vault() {
    if command -v vault >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Method 1: Using Credhub
setup_credhub() {
    echo -e "${GREEN}Setting up credentials in Credhub...${NC}"

    # Check if logged in to Credhub
    if ! credhub api >/dev/null 2>&1; then
        echo -e "${YELLOW}Please login to Credhub first:${NC}"
        echo "  credhub login -s https://your-credhub-server -u username -p password"
        exit 1
    fi

    # Set Minio credentials
    credhub set -n /concourse/main/s3_access_key -t value -v "$DEFAULT_MINIO_ACCESS_KEY"
    credhub set -n /concourse/main/s3_secret_key -t value -v "$DEFAULT_MINIO_SECRET_KEY"
    credhub set -n /concourse/main/s3_endpoint -t value -v "$DEFAULT_MINIO_ENDPOINT"
    credhub set -n /concourse/main/s3_region -t value -v "us-east-1"

    # Set bucket names
    credhub set -n /concourse/main/s3_monitor_bucket -t value -v "release-monitor-output"
    credhub set -n /concourse/main/s3_releases_bucket -t value -v "release-monitor-artifacts"

    echo -e "${GREEN}✅ Credentials stored in Credhub${NC}"
}

# Method 2: Using Vault
setup_vault() {
    echo -e "${GREEN}Setting up credentials in Vault...${NC}"

    # Check if logged in to Vault
    if ! vault status >/dev/null 2>&1; then
        echo -e "${YELLOW}Please login to Vault first:${NC}"
        echo "  vault login"
        exit 1
    fi

    # Set Minio credentials
    vault kv put concourse/main \
        s3_access_key="$DEFAULT_MINIO_ACCESS_KEY" \
        s3_secret_key="$DEFAULT_MINIO_SECRET_KEY" \
        s3_endpoint="$DEFAULT_MINIO_ENDPOINT" \
        s3_region="us-east-1" \
        s3_monitor_bucket="release-monitor-output" \
        s3_releases_bucket="release-monitor-artifacts"

    echo -e "${GREEN}✅ Credentials stored in Vault${NC}"
}

# Method 3: Using fly CLI with variables
setup_fly_vars() {
    echo -e "${GREEN}Setting up credentials using fly variables...${NC}"

    # Prompt for target
    read -p "Enter Concourse target name (e.g., test): " CONCOURSE_TARGET

    # Check if target exists
    if ! fly -t "$CONCOURSE_TARGET" status >/dev/null 2>&1; then
        echo -e "${RED}Error: Target '$CONCOURSE_TARGET' not found${NC}"
        echo "Please login first: fly -t $CONCOURSE_TARGET login"
        exit 1
    fi

    # Create a temporary vars file
    VARS_FILE=$(mktemp)
    cat >"$VARS_FILE" <<EOF
# Minio S3-compatible credentials
s3_access_key: $DEFAULT_MINIO_ACCESS_KEY
s3_secret_key: $DEFAULT_MINIO_SECRET_KEY
s3_endpoint: $DEFAULT_MINIO_ENDPOINT
s3_region: us-east-1

# S3-compatible settings for Minio
s3_disable_ssl: true
s3_skip_ssl_verification: true

# Bucket names
s3_monitor_bucket: release-monitor-output
s3_releases_bucket: release-monitor-artifacts

# Version DB settings
version_db_s3_bucket: release-monitor-output
version_db_s3_prefix: version-db/
use_s3_version_db: true
repository_overrides: |-
  {
    "kubernetes/kubernetes": {
      "asset_patterns": ["kubernetes-client-*.tar.gz", "kubernetes-server-*.tar.gz"],
      "include_prereleases": false
    },
    "istio/istio": {
      "asset_patterns": ["istio-*.linux-amd64.tar.gz"],
      "include_prereleases": false
    },
    "open-policy-agent/gatekeeper": {
      "asset_patterns": ["gatekeeper-*.linux-amd64.tar.gz"],
      "include_prereleases": false
    }
  }
EOF

    echo ""
    echo "Variables file created at: $VARS_FILE"
    echo ""
    echo "To deploy the pipeline with these credentials, run:"
    echo ""
    echo -e "${YELLOW}fly -t $CONCOURSE_TARGET set-pipeline \\
  -p github-release-monitor-minio \\
  -c ci/pipeline-s3-compatible.yml \\
  -l params/global-s3-compatible.yml \\
  -l params/minio-local.yml \\
  -l $VARS_FILE \\
  --var git_private_key=\"\$(cat ~/.ssh/id_ed25519)\" \\
  --var github_token=\$GITHUB_TOKEN${NC}"

    echo ""
    echo -e "${GREEN}✅ Variables file ready for pipeline deployment${NC}"
}

# Method 4: Direct command line variables
show_direct_method() {
    echo -e "${GREEN}Direct command line method:${NC}"
    echo ""
    echo "You can also pass credentials directly when setting the pipeline:"
    echo ""
    echo -e "${YELLOW}fly -t test set-pipeline \\
  -p github-release-monitor-minio \\
  -c ci/pipeline-s3-compatible.yml \\
  -l params/global-s3-compatible.yml \\
  -l params/minio-local.yml \\
  --var s3_access_key=\"$DEFAULT_MINIO_ACCESS_KEY\" \\
  --var s3_secret_key=\"$DEFAULT_MINIO_SECRET_KEY\" \\
  --var s3_endpoint=\"$DEFAULT_MINIO_ENDPOINT\" \\
  --var s3_region=\"us-east-1\" \\
  --var s3_disable_ssl=\"true\" \\
  --var s3_skip_ssl_verification=\"true\" \\
  --var s3_monitor_bucket=\"release-monitor-output\" \\
  --var s3_releases_bucket=\"release-monitor-artifacts\" \\
  --var git_private_key=\"\$(cat ~/.ssh/id_ed25519)\" \\
  --var github_token=\"\$GITHUB_TOKEN\"${NC}"
}

# Main menu
echo "Choose a method to set up credentials:"
echo ""
echo "1) Credhub (recommended for production)"
echo "2) Vault"
echo "3) Fly variables file"
echo "4) Direct command line (show example)"
echo ""
read -p "Select method (1-4): " choice

case $choice in
1)
    if check_credhub; then
        setup_credhub
    else
        echo -e "${RED}Credhub CLI not found. Please install it first.${NC}"
        exit 1
    fi
    ;;
2)
    if check_vault; then
        setup_vault
    else
        echo -e "${RED}Vault CLI not found. Please install it first.${NC}"
        exit 1
    fi
    ;;
3)
    setup_fly_vars
    ;;
4)
    show_direct_method
    ;;
*)
    echo -e "${RED}Invalid choice${NC}"
    exit 1
    ;;
esac

echo ""
echo "📋 Next steps:"
echo "1. Ensure Minio is running: docker-compose up -d"
echo "2. Test Minio connectivity: ./scripts/test-minio.sh"
echo "3. Deploy the pipeline with your chosen method"
echo "4. Trigger the pipeline to test the integration"
