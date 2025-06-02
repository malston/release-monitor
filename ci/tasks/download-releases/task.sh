#!/bin/bash

set -euo pipefail

# GitHub Release Download Task for Concourse
# Downloads GitHub release assets based on monitor output

echo "=================================================="
echo "GitHub Release Download Task"
echo "=================================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    if [[ "${VERBOSE:-false}" == "true" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
}

# Error handling
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        log_error "Task failed with exit code $exit_code"
        
        # Create failure marker for pipeline visibility
        echo "{\"status\": \"failed\", \"error\": \"Task execution failed\", \"exit_code\": $exit_code}" > /tmp/downloads/download_status.json
    fi
    exit $exit_code
}

trap cleanup EXIT

# Validate required environment variables
log_info "Validating environment..."

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
    log_error "GITHUB_TOKEN is required but not set"
    exit 1
fi

# Set default values
DOWNLOAD_DIR="${DOWNLOAD_DIR:-/tmp/downloads}"
VERSION_DB_PATH="${VERSION_DB_PATH:-/tmp/version-db/version_db.json}"
CONFIG_FILE="${CONFIG_FILE:-config.yaml}"
VERBOSE="${VERBOSE:-false}"
DRY_RUN="${DRY_RUN:-false}"

# S3 storage configuration (optional)
USE_S3_VERSION_DB="${USE_S3_VERSION_DB:-false}"
VERSION_DB_S3_BUCKET="${VERSION_DB_S3_BUCKET:-}"
VERSION_DB_S3_PREFIX="${VERSION_DB_S3_PREFIX:-release-monitor/}"
VERSION_DB_S3_REGION="${VERSION_DB_S3_REGION:-}"
S3_ENDPOINT="${S3_ENDPOINT:-}"

# Export S3 endpoint for boto3 to use
if [[ -n "$S3_ENDPOINT" ]]; then
    export AWS_ENDPOINT_URL="$S3_ENDPOINT"
    export AWS_ENDPOINT_URL_S3="$S3_ENDPOINT"
    log_info "  S3 Endpoint: $S3_ENDPOINT"
fi

# Log configuration
log_info "Configuration:"
log_info "  Download Directory: $DOWNLOAD_DIR"
if [[ "$USE_S3_VERSION_DB" == "true" ]]; then
    log_info "  Version DB: S3 (s3://$VERSION_DB_S3_BUCKET/$VERSION_DB_S3_PREFIX)"
else
    log_info "  Version DB Path: $VERSION_DB_PATH"
fi
log_info "  Config File: $CONFIG_FILE"
log_info "  Verbose: $VERBOSE"
log_info "  Dry Run: $DRY_RUN"

# Check Python and dependencies
log_info "Checking Python environment..."

if ! command -v python3 &> /dev/null; then
    log_error "Python 3 is not available"
    exit 1
fi

python3 --version

# Install Python dependencies
log_info "Installing Python dependencies..."
cd /opt/release-monitor

if [[ -f requirements.txt ]]; then
    pip3 install --quiet -r requirements.txt
else
    log_warn "requirements.txt not found, installing basic dependencies"
    pip3 install --quiet requests PyYAML
fi

# Install AWS SDK if using S3 version database
if [[ "$USE_S3_VERSION_DB" == "true" ]]; then
    log_info "Installing AWS SDK for S3 version database..."
    pip3 install --quiet boto3
fi

# Verify input files exist
log_info "Checking input files..."

if [[ ! -f "/tmp/monitor-output/latest-releases.json" ]]; then
    log_error "Monitor output file not found: /tmp/monitor-output/latest-releases.json"
    exit 1
fi

MONITOR_OUTPUT="/tmp/monitor-output/latest-releases.json"

log_info "Found monitor output at: $MONITOR_OUTPUT"

if [[ ! -f "$CONFIG_FILE" ]]; then
    log_error "Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Create output directories
log_info "Preparing output directories..."
mkdir -p "$DOWNLOAD_DIR"
mkdir -p "$(dirname "$VERSION_DB_PATH")"

# Check monitor output content
log_info "Analyzing monitor output..."

# Check if monitor output is valid JSON
if ! python3 -c "import json; json.load(open('$MONITOR_OUTPUT'))" 2>/dev/null; then
    log_error "Monitor output is not valid JSON"
    exit 1
fi

# Count new releases
NEW_RELEASES=$(python3 -c "import json; data=json.load(open('$MONITOR_OUTPUT')); print(data.get('new_releases_found', 0))")

log_info "Monitor output analysis:"
log_info "  New releases found: $NEW_RELEASES"

if [[ "$NEW_RELEASES" -eq 0 ]]; then
    log_info "No new releases to download, creating empty status file"
    echo "{\"status\": \"success\", \"message\": \"No new releases to download\", \"downloads\": 0}" > /tmp/downloads/download_status.json
    exit 0
fi

# Create dynamic configuration for download
log_info "Creating download configuration..."

TEMP_CONFIG=$(mktemp)

# Build configuration with environment parameters
python3 - << EOF
import json
import yaml
import os

# Load base configuration
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)

# Update download configuration from environment
download_config = config.setdefault('download', {})
download_config['enabled'] = True
download_config['directory'] = '$DOWNLOAD_DIR'
download_config['version_db'] = '$VERSION_DB_PATH'

# Configure S3 storage if enabled
if '${USE_S3_VERSION_DB}' == 'true':
    s3_config = download_config.setdefault('s3_storage', {})
    s3_config['enabled'] = True
    s3_config['bucket'] = '${VERSION_DB_S3_BUCKET}'
    s3_config['prefix'] = '${VERSION_DB_S3_PREFIX}'
    if '${VERSION_DB_S3_REGION}':
        s3_config['region'] = '${VERSION_DB_S3_REGION}'
    if '${S3_ENDPOINT}':
        s3_config['endpoint_url'] = '${S3_ENDPOINT}'

# Parse JSON parameters from environment
try:
    asset_patterns = json.loads('${ASSET_PATTERNS:-["*.tar.gz", "*.zip"]}')
    download_config['asset_patterns'] = asset_patterns
except json.JSONDecodeError:
    download_config['asset_patterns'] = ['*.tar.gz', '*.zip']

# Handle repository overrides which might be multi-line JSON
repo_overrides_str = '''${REPOSITORY_OVERRIDES:-{}}'''
try:
    repo_overrides = json.loads(repo_overrides_str)
    if repo_overrides:
        download_config['repository_overrides'] = repo_overrides
except json.JSONDecodeError:
    # Try to parse as empty dict if parsing fails
    download_config['repository_overrides'] = {}

# Set other download parameters
# Convert bash true/false strings to Python booleans
download_config['include_prereleases'] = '${INCLUDE_PRERELEASES:-false}'.lower() == 'true'
download_config['verify_downloads'] = '${VERIFY_DOWNLOADS:-true}'.lower() == 'true'
download_config['cleanup_old_versions'] = '${CLEANUP_OLD_VERSIONS:-true}'.lower() == 'true'
download_config['keep_versions'] = int('${KEEP_VERSIONS:-5}')
download_config['timeout'] = int('${DOWNLOAD_TIMEOUT:-300}')

# Write updated configuration
with open('$TEMP_CONFIG', 'w') as f:
    yaml.dump(config, f)
EOF

log_debug "Generated configuration:"
if [[ "${VERBOSE:-false}" == "true" ]]; then
    cat "$TEMP_CONFIG"
fi

# Build download command arguments
DOWNLOAD_ARGS=(
    --config "$TEMP_CONFIG"
    --input "$MONITOR_OUTPUT"
)

if [[ "${VERBOSE:-false}" == "true" ]]; then
    DOWNLOAD_ARGS+=(--verbose)
fi

if [[ "${DRY_RUN:-false}" == "true" ]]; then
    DOWNLOAD_ARGS+=(--dry-run)
fi

# Execute download
log_info "Starting download process..."
log_info "Command: python3 download_releases.py ${DOWNLOAD_ARGS[*]}"

# Debug environment variables
log_info "Environment variables for S3:"
log_info "  AWS_ENDPOINT_URL: ${AWS_ENDPOINT_URL:-not set}"
log_info "  AWS_ENDPOINT_URL_S3: ${AWS_ENDPOINT_URL_S3:-not set}"
log_info "  AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:+set}"
log_info "  AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY:+set}"
log_info "  S3_ENDPOINT: ${S3_ENDPOINT:-not set}"

# Test S3 connection before running full download
log_info "Testing S3 connection..."
python3 - << 'EOF' || log_error "S3 connection test failed"
import boto3
import os
import sys

endpoint = os.environ.get('AWS_ENDPOINT_URL_S3')
print(f"Testing connection to S3 endpoint: {endpoint}")

try:
    s3 = boto3.client('s3', endpoint_url=endpoint)
    # Try to list buckets
    response = s3.list_buckets()
    print(f"Connection successful! Found {len(response.get('Buckets', []))} buckets")
    for bucket in response.get('Buckets', []):
        print(f"  - {bucket['Name']}")
except Exception as e:
    print(f"ERROR: Failed to connect to S3: {e}")
    sys.exit(1)
EOF

START_TIME=$(date +%s)

# Run download with visible output for debugging
log_info "Running download script with visible output..."

# Run with timeout but show output in real-time
# Use 600s (10 minutes) timeout to allow for large file downloads
timeout 600s python3 download_releases.py "${DOWNLOAD_ARGS[@]}" 2>&1 | tee /tmp/download_output.log
DOWNLOAD_EXIT_CODE=${PIPESTATUS[0]}

# Check if it was killed by timeout
if [[ $DOWNLOAD_EXIT_CODE -eq 124 ]]; then
    log_error "Download process timed out after 600 seconds (10 minutes)"
    log_error "This usually indicates a connection issue or very large files"
fi

# Copy output for processing
DOWNLOAD_OUTPUT=/tmp/download_output.log
DOWNLOAD_ERROR=/tmp/download_output.log

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Process results
log_info "Download completed in ${DURATION} seconds with exit code: $DOWNLOAD_EXIT_CODE"

# Show output
if [[ -s "$DOWNLOAD_OUTPUT" ]]; then
    log_info "Download output:"
    cat "$DOWNLOAD_OUTPUT"
fi

if [[ -s "$DOWNLOAD_ERROR" ]]; then
    log_warn "Download errors/warnings:"
    cat "$DOWNLOAD_ERROR"
fi

# Parse download results
if [[ $DOWNLOAD_EXIT_CODE -eq 0 ]]; then
    log_info "Download completed successfully"
    
    # Try to parse download results from output
    if [[ -s "$DOWNLOAD_OUTPUT" ]]; then
        # Copy download results to output
        cp "$DOWNLOAD_OUTPUT" /tmp/downloads/download_results.json
        
        # Create status summary
        python3 - << EOF > /tmp/downloads/download_status.json
import json

try:
    with open('$DOWNLOAD_OUTPUT', 'r') as f:
        results = json.load(f)
    
    status = {
        "status": "success",
        "message": "Downloads completed successfully",
        "duration_seconds": $DURATION,
        "summary": {
            "total_releases": results.get('total_releases_checked', 0),
            "new_downloads": results.get('new_downloads', 0),
            "skipped_releases": results.get('skipped_releases', 0),
            "failed_downloads": results.get('failed_downloads', 0)
        }
    }
    
    print(json.dumps(status, indent=2))
    
except Exception as e:
    fallback = {
        "status": "success",
        "message": "Downloads completed (results parsing failed)",
        "duration_seconds": $DURATION,
        "error": str(e)
    }
    print(json.dumps(fallback, indent=2))
EOF
    fi
    
else
    log_error "Download failed with exit code: $DOWNLOAD_EXIT_CODE"
    
    # Create failure status
    echo "{\"status\": \"failed\", \"message\": \"Download process failed\", \"exit_code\": $DOWNLOAD_EXIT_CODE, \"duration_seconds\": $DURATION}" > /tmp/downloads/download_status.json
    
    exit $DOWNLOAD_EXIT_CODE
fi

# Validate outputs exist
log_info "Validating outputs..."

if [[ -d "$DOWNLOAD_DIR" ]]; then
    DOWNLOAD_COUNT=$(find "$DOWNLOAD_DIR" -type f ! -name "*.sha256" ! -name "*.json" | wc -l)
    log_info "Downloaded files: $DOWNLOAD_COUNT"
    
    if [[ "${VERBOSE:-false}" == "true" ]]; then
        log_debug "Download directory contents:"
        find "$DOWNLOAD_DIR" -type f | head -20
    fi
else
    log_warn "Download directory does not exist: $DOWNLOAD_DIR"
fi

if [[ -f "$VERSION_DB_PATH" ]]; then
    log_info "Version database updated: $VERSION_DB_PATH"
    
    if [[ "${VERBOSE:-false}" == "true" ]]; then
        log_debug "Version database contents:"
        cat "$VERSION_DB_PATH" | python3 -m json.tool | head -20
    fi
else
    log_warn "Version database not found: $VERSION_DB_PATH"
fi

# Cleanup temporary files
rm -f "$TEMP_CONFIG" "$DOWNLOAD_OUTPUT" "$DOWNLOAD_ERROR"

log_info "Task completed successfully"
echo "=================================================="