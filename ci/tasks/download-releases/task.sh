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

# Artifactory storage configuration (optional)
ARTIFACTORY_URL="${ARTIFACTORY_URL:-}"
ARTIFACTORY_REPOSITORY="${ARTIFACTORY_REPOSITORY:-}"

# Auto-detect Artifactory usage if URL and repository are provided
if [[ -n "$ARTIFACTORY_URL" && -n "$ARTIFACTORY_REPOSITORY" ]]; then
    USE_ARTIFACTORY_VERSION_DB="${USE_ARTIFACTORY_VERSION_DB:-true}"
else
    USE_ARTIFACTORY_VERSION_DB="${USE_ARTIFACTORY_VERSION_DB:-false}"
fi
ARTIFACTORY_USERNAME="${ARTIFACTORY_USERNAME:-}"
ARTIFACTORY_PASSWORD="${ARTIFACTORY_PASSWORD:-}"
ARTIFACTORY_API_KEY="${ARTIFACTORY_API_KEY:-}"
ARTIFACTORY_PATH_PREFIX="${ARTIFACTORY_PATH_PREFIX:-release-monitor/}"
ARTIFACTORY_SKIP_SSL_VERIFICATION="${ARTIFACTORY_SKIP_SSL_VERIFICATION:-false}"

# Export S3 endpoint for boto3 to use
if [[ -n "$S3_ENDPOINT" ]]; then
    export AWS_ENDPOINT_URL="$S3_ENDPOINT"
    export AWS_ENDPOINT_URL_S3="$S3_ENDPOINT"
    log_info "  S3 Endpoint: $S3_ENDPOINT"
fi

# Log configuration
log_info "Configuration:"
log_info "  Download Directory: $DOWNLOAD_DIR"
if [[ "$USE_ARTIFACTORY_VERSION_DB" == "true" ]]; then
    log_info "  Version DB: Artifactory ($ARTIFACTORY_URL repository: $ARTIFACTORY_REPOSITORY)"
elif [[ "$USE_S3_VERSION_DB" == "true" ]]; then
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

# Install Artifactory dependencies if using Artifactory version database
if [[ "$USE_ARTIFACTORY_VERSION_DB" == "true" ]]; then
    log_info "Installing dependencies for Artifactory version database..."
    pip3 install --quiet requests urllib3
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

# Configure Artifactory storage if enabled
if '${USE_ARTIFACTORY_VERSION_DB}' == 'true':
    artifactory_config = download_config.setdefault('artifactory_storage', {})
    artifactory_config['enabled'] = True
    artifactory_config['base_url'] = '${ARTIFACTORY_URL}'
    artifactory_config['repository'] = '${ARTIFACTORY_REPOSITORY}'
    artifactory_config['path_prefix'] = '${ARTIFACTORY_PATH_PREFIX}'
    if '${ARTIFACTORY_USERNAME}':
        artifactory_config['username'] = '${ARTIFACTORY_USERNAME}'
    if '${ARTIFACTORY_PASSWORD}':
        artifactory_config['password'] = '${ARTIFACTORY_PASSWORD}'
    if '${ARTIFACTORY_API_KEY}':
        artifactory_config['api_key'] = '${ARTIFACTORY_API_KEY}'
    artifactory_config['verify_ssl'] = '${ARTIFACTORY_SKIP_SSL_VERIFICATION}'.lower() != 'true'

# Configure S3 storage if enabled (fallback after Artifactory)
elif '${USE_S3_VERSION_DB}' == 'true':
    s3_config = download_config.setdefault('s3_storage', {})
    s3_config['enabled'] = True
    s3_config['bucket'] = '${VERSION_DB_S3_BUCKET}'
    s3_config['prefix'] = '${VERSION_DB_S3_PREFIX}'
    if '${VERSION_DB_S3_REGION}':
        s3_config['region'] = '${VERSION_DB_S3_REGION}'
    if '${S3_ENDPOINT}':
        s3_config['endpoint_url'] = '${S3_ENDPOINT}'

# Handle repository overrides first to determine if we need global patterns
# Use os.environ.get to properly handle multiline JSON
repo_overrides_str = os.environ.get('REPOSITORY_OVERRIDES', '{}')
repo_overrides = {}
try:
    repo_overrides = json.loads(repo_overrides_str)
    download_config['repository_overrides'] = repo_overrides
    if repo_overrides:
        print(f"DEBUG: Successfully parsed repository overrides: {list(repo_overrides.keys())}")
        for repo, config in repo_overrides.items():
            if 'target_version' in config:
                print(f"DEBUG: {repo} has target_version: {config['target_version']}")
    else:
        print("DEBUG: Repository overrides are empty")
except json.JSONDecodeError as e:
    print(f"DEBUG: Failed to parse REPOSITORY_OVERRIDES: {e}")
    print(f"DEBUG: REPOSITORY_OVERRIDES content: {repr(repo_overrides_str)}")
    # Try to parse as empty dict if parsing fails
    download_config['repository_overrides'] = {}

# Parse global asset patterns - use minimal patterns if repository overrides exist
if repo_overrides:
    # If we have repository overrides with asset_patterns, use minimal global fallback
    has_asset_patterns = any('asset_patterns' in config for config in repo_overrides.values())
    if has_asset_patterns:
        # Use empty global patterns, rely on repository overrides
        download_config['asset_patterns'] = []
    else:
        # Repository overrides exist but no asset_patterns specified, use defaults
        try:
            asset_patterns = json.loads('${ASSET_PATTERNS:-["*.tar.gz", "*.zip"]}')
            download_config['asset_patterns'] = asset_patterns
        except json.JSONDecodeError:
            download_config['asset_patterns'] = ['*.tar.gz', '*.zip']
else:
    # No repository overrides, use global patterns
    try:
        asset_patterns = json.loads('${ASSET_PATTERNS:-["*.tar.gz", "*.zip"]}')
        download_config['asset_patterns'] = asset_patterns
    except json.JSONDecodeError:
        download_config['asset_patterns'] = ['*.tar.gz', '*.zip']

# Set other download parameters
# Convert bash true/false strings to Python booleans
download_config['include_prereleases'] = '${INCLUDE_PRERELEASES:-false}'.lower() == 'true'
download_config['verify_downloads'] = '${VERIFY_DOWNLOADS:-true}'.lower() == 'true'
download_config['cleanup_old_versions'] = '${CLEANUP_OLD_VERSIONS:-true}'.lower() == 'true'
download_config['keep_versions'] = int('${KEEP_VERSIONS:-5}')
download_config['timeout'] = int('${DOWNLOAD_TIMEOUT:-300}')

# Debug: Print final configuration before writing
print("DEBUG: Final download_config before YAML dump:")
print(f"DEBUG: repository_overrides = {download_config.get('repository_overrides', 'NOT_FOUND')}")
print("DEBUG: Main config object before YAML dump:")
print(f"DEBUG: config['download']['repository_overrides'] = {config.get('download', {}).get('repository_overrides', 'NOT_FOUND')}")

# Ensure download_config changes are saved back to main config
config['download'] = download_config

# Write updated configuration
with open('$TEMP_CONFIG', 'w') as f:
    yaml.dump(config, f)

# Debug: Read and print the YAML file that was written
print("DEBUG: Reading back the generated YAML config:")
with open('$TEMP_CONFIG', 'r') as f:
    written_config = yaml.safe_load(f)
    print(f"DEBUG: Written repository_overrides = {written_config.get('download', {}).get('repository_overrides', 'NOT_FOUND')}")
EOF

log_debug "REPOSITORY_OVERRIDES environment variable:"
log_debug "${REPOSITORY_OVERRIDES:-<empty>}"

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
if [[ "$USE_ARTIFACTORY_VERSION_DB" == "true" ]]; then
    log_info "Environment variables for Artifactory:"
    log_info "  ARTIFACTORY_URL: ${ARTIFACTORY_URL:-not set}"
    log_info "  ARTIFACTORY_REPOSITORY: ${ARTIFACTORY_REPOSITORY:-not set}"
    log_info "  ARTIFACTORY_PATH_PREFIX: ${ARTIFACTORY_PATH_PREFIX:-release-monitor/}"
    log_info "  ARTIFACTORY_USERNAME: ${ARTIFACTORY_USERNAME:+set}"
    log_info "  ARTIFACTORY_PASSWORD: ${ARTIFACTORY_PASSWORD:+set}"
    log_info "  ARTIFACTORY_API_KEY: ${ARTIFACTORY_API_KEY:+set}"
    log_info "  ARTIFACTORY_SKIP_SSL_VERIFICATION: ${ARTIFACTORY_SKIP_SSL_VERIFICATION:-false}"
elif [[ "$USE_S3_VERSION_DB" == "true" ]]; then
    log_info "Environment variables for S3:"
    log_info "  AWS_ENDPOINT_URL: ${AWS_ENDPOINT_URL:-not set}"
    log_info "  AWS_ENDPOINT_URL_S3: ${AWS_ENDPOINT_URL_S3:-not set}"
    log_info "  AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:+set}"
    log_info "  AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY:+set}"
    log_info "  S3_ENDPOINT: ${S3_ENDPOINT:-not set}"
    log_info "  S3_SKIP_SSL_VERIFICATION: ${S3_SKIP_SSL_VERIFICATION:-false}"
fi

# Test storage backend connection before running full download
if [[ "$USE_ARTIFACTORY_VERSION_DB" == "true" ]]; then
    log_info "Testing Artifactory connection..."
    python3 - << 'EOF' || log_error "Artifactory connection test failed"
import requests
import os
import sys
from urllib.parse import urljoin

base_url = os.environ.get('ARTIFACTORY_URL')
repository = os.environ.get('ARTIFACTORY_REPOSITORY')
username = os.environ.get('ARTIFACTORY_USERNAME')
password = os.environ.get('ARTIFACTORY_PASSWORD')
api_key = os.environ.get('ARTIFACTORY_API_KEY')
verify_ssl = os.environ.get('ARTIFACTORY_SKIP_SSL_VERIFICATION', '').lower() != 'true'

print(f"Testing connection to Artifactory: {base_url}")

try:
    # Set up authentication
    auth = None
    headers = {}
    if api_key:
        headers['X-JFrog-Art-Api'] = api_key
        print("Using API key authentication")
    elif username and password:
        auth = (username, password)
        print("Using username/password authentication")
    else:
        print("WARNING: No authentication configured")

    if not verify_ssl:
        print("WARNING: Skipping SSL verification for Artifactory")

    # Test system ping
    ping_url = urljoin(base_url, '/api/system/ping')
    response = requests.get(ping_url, auth=auth, headers=headers, verify=verify_ssl, timeout=10)

    if response.status_code == 200:
        print("Connection successful! Artifactory is reachable")

        # Test repository access
        repo_url = urljoin(base_url, f'/api/repositories/{repository}')
        repo_response = requests.get(repo_url, auth=auth, headers=headers, verify=verify_ssl, timeout=10)

        if repo_response.status_code == 200:
            print(f"Repository '{repository}' is accessible")
        else:
            print(f"WARNING: Repository '{repository}' may not exist or is not accessible (status: {repo_response.status_code})")
    else:
        print(f"ERROR: Failed to ping Artifactory (status: {response.status_code})")
        sys.exit(1)

except Exception as e:
    print(f"ERROR: Failed to connect to Artifactory: {e}")
    sys.exit(1)
EOF

elif [[ "$USE_S3_VERSION_DB" == "true" ]]; then
    log_info "Testing S3 connection..."
    python3 - << 'EOF' || log_error "S3 connection test failed"
import boto3
import os
import sys

endpoint = os.environ.get('AWS_ENDPOINT_URL_S3')
print(f"Testing connection to S3 endpoint: {endpoint}")

try:
    # Check if we should skip SSL verification
    verify_ssl = os.environ.get('S3_SKIP_SSL_VERIFICATION', '').lower() != 'true'

    if not verify_ssl:
        print("WARNING: Skipping SSL verification for S3 endpoint")
        s3 = boto3.client('s3', endpoint_url=endpoint, verify=False)
    else:
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

else
    log_info "Using local file storage - no connection test needed"
fi

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

    exit "$DOWNLOAD_EXIT_CODE"
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

if [[ "$USE_ARTIFACTORY_VERSION_DB" == "true" ]]; then
    log_info "Version database is managed in Artifactory ($ARTIFACTORY_URL repository: $ARTIFACTORY_REPOSITORY)"
elif [[ "$USE_S3_VERSION_DB" == "true" ]]; then
    log_info "Version database is managed in S3 (s3://$VERSION_DB_S3_BUCKET/$VERSION_DB_S3_PREFIX)"
elif [[ -f "$VERSION_DB_PATH" ]]; then
    log_info "Version database updated: $VERSION_DB_PATH"

    if [[ "${VERBOSE:-false}" == "true" ]]; then
        log_debug "Version database contents:"
        python3 -m json.tool < "$VERSION_DB_PATH" | head -20
    fi
else
    log_warn "Version database not found: $VERSION_DB_PATH"
fi

# Cleanup temporary files
rm -f "$TEMP_CONFIG" "$DOWNLOAD_OUTPUT" "$DOWNLOAD_ERROR"

log_info "Task completed successfully"
echo "=================================================="
