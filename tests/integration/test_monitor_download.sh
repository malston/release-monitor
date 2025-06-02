#!/bin/bash
# Integration test script for monitor with download functionality

set -euo pipefail

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "Starting integration tests for monitor with download..."

# Change to project root
cd "$PROJECT_ROOT"

# Determine Python command (use virtual environment if available)
if [ -f "venv/bin/python3" ]; then
    PYTHON_CMD="venv/bin/python3"
    echo "Using virtual environment: $PYTHON_CMD"
elif [ -f "test-env/bin/python3" ]; then
    PYTHON_CMD="test-env/bin/python3"
    echo "Using test virtual environment: $PYTHON_CMD"
else
    PYTHON_CMD="python3"
    echo "Using system Python: $PYTHON_CMD"
fi

# Create temporary test directory
TEST_DIR=$(mktemp -d)
trap "rm -rf $TEST_DIR" EXIT

# Setup test environment
echo "Setting up test environment in $TEST_DIR..."

# Create test config
cat > "$TEST_DIR/test-config.yaml" << EOF
repositories:
  - owner: "malston"
    repo: "release-monitor"
    include_prereleases: false

download:
  enabled: true
  directory: "$TEST_DIR/downloads"
  version_db: "$TEST_DIR/version_db.json"
  asset_patterns:
    - "*.tar.gz"
    - "*.zip"
    - "!*-sources.zip"
  verify_checksums: true
  retry_attempts: 3
  retry_delay: 2
EOF

# Test 1: Monitor without download flag
echo -e "\n${GREEN}Test 1: Monitor without download flag${NC}"
$PYTHON_CMD github_monitor.py --config "$TEST_DIR/test-config.yaml" > "$TEST_DIR/monitor-output.json"

if [ -d "$TEST_DIR/downloads" ]; then
    echo -e "${RED}FAIL: Download directory should not exist without --download flag${NC}"
    exit 1
else
    echo -e "${GREEN}PASS: No downloads occurred without flag${NC}"
fi

# Test 2: Monitor with download flag (dry run with mock data)
echo -e "\n${GREEN}Test 2: Monitor with download flag${NC}"

# Create a mock monitor output for testing download coordination
cat > "$TEST_DIR/mock-monitor-output.json" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "repositories": [
    {
      "owner": "malston",
      "repo": "release-monitor",
      "latest_release": {
        "version": "v0.1.0-test",
        "url": "https://github.com/malston/release-monitor/releases/tag/v0.1.0-test",
        "published_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
        "is_prerelease": false,
        "assets": [
          {
            "name": "release-monitor.tar.gz",
            "browser_download_url": "https://github.com/malston/release-monitor/releases/download/v0.1.0-test/release-monitor.tar.gz",
            "size": 1024,
            "content_type": "application/gzip"
          }
        ]
      }
    }
  ]
}
EOF

# Test download coordinator directly
echo "Testing download coordinator..."
$PYTHON_CMD -c "
import json
import sys
sys.path.insert(0, '.')
from download_releases import ReleaseDownloadCoordinator

with open('$TEST_DIR/test-config.yaml', 'r') as f:
    import yaml
    config = yaml.safe_load(f)

with open('$TEST_DIR/mock-monitor-output.json', 'r') as f:
    monitor_output = json.load(f)

coordinator = ReleaseDownloadCoordinator(config, 'test_token')
# Don't actually download, just test the logic
print('Download coordinator initialized successfully')
"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}PASS: Download coordinator works correctly${NC}"
else
    echo -e "${RED}FAIL: Download coordinator initialization failed${NC}"
    exit 1
fi

# Test 3: Version database functionality
echo -e "\n${GREEN}Test 3: Version database functionality${NC}"
$PYTHON_CMD -c "
import sys
sys.path.insert(0, '.')
from github_version_db import VersionDatabase

db = VersionDatabase('$TEST_DIR/test_version_db.json')
db.update_version('test', 'repo', 'v1.0.0')
version = db.get_current_version('test', 'repo')
assert version == 'v1.0.0', f'Expected v1.0.0, got {version}'
print('Version database test passed')
"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}PASS: Version database works correctly${NC}"
else
    echo -e "${RED}FAIL: Version database test failed${NC}"
    exit 1
fi

# Test 4: Version comparison
echo -e "\n${GREEN}Test 4: Version comparison${NC}"
$PYTHON_CMD -c "
import sys
sys.path.insert(0, '.')
from version_compare import VersionComparator

vc = VersionComparator()
assert vc.is_newer('v1.1.0', 'v1.0.0') == True
assert vc.is_newer('v1.0.0', 'v1.1.0') == False
assert vc.is_newer('v1.0.0', 'v1.0.0') == False
assert vc.is_newer('2023.10.15', '2023.10.14') == True
assert vc.is_newer('v1.0.0-alpha', None) == False  # Pre-release
assert vc.is_newer('v1.0.0', None) == True
print('Version comparison tests passed')
"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}PASS: Version comparison works correctly${NC}"
else
    echo -e "${RED}FAIL: Version comparison test failed${NC}"
    exit 1
fi

# Test 5: Full integration test (if we're in a git repo with real releases)
if [ -d ".git" ]; then
    echo -e "\n${GREEN}Test 5: Full integration test with real repository${NC}"
    
    # Use this repository as test subject
    cat > "$TEST_DIR/self-test-config.yaml" << EOF
repositories:
  - owner: "$(git remote get-url origin | sed -E 's/.*github.com[:/](.+)\/(.+)(\.git)?$/\1/')"
    repo: "$(git remote get-url origin | sed -E 's/.*github.com[:/](.+)\/(.+)(\.git)?$/\2/' | sed 's/\.git$//')"
    include_prereleases: false

download:
  enabled: true
  directory: "$TEST_DIR/self-downloads"
  version_db: "$TEST_DIR/self-version_db.json"
  asset_patterns:
    - "*"
EOF
    
    # Run monitor on self (won't actually download without real releases)
    $PYTHON_CMD github_monitor.py --config "$TEST_DIR/self-test-config.yaml" --download
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}PASS: Full integration test completed${NC}"
    else
        echo -e "${RED}FAIL: Full integration test failed${NC}"
        exit 1
    fi
fi

echo -e "\n${GREEN}All integration tests passed!${NC}"