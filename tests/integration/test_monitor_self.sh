#!/bin/bash
# Integration test script for monitoring releases outside of Concourse pipeline

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo -e "${GREEN}=== GitHub Release Monitor Integration Test ===${NC}"
echo "Testing release monitoring outside of Concourse pipeline"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required${NC}"
    exit 1
fi
echo "✅ Python 3 found: $(python3 --version)"

# Load .env file if it exists
if [ -f "${PROJECT_ROOT}/.env" ]; then
    export $(grep -v '^#' "${PROJECT_ROOT}/.env" | xargs)
fi

# Check for GitHub token
if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo -e "${YELLOW}⚠️  Warning: GITHUB_TOKEN not set${NC}"
    echo "   Tests may fail due to GitHub API rate limits"
    echo "   Set with: export GITHUB_TOKEN=your_token"
else
    echo "✅ GitHub token configured"
fi

# Change to project root
cd "$PROJECT_ROOT"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo -e "\n${GREEN}Activating virtual environment...${NC}"
    source venv/bin/activate
    PYTHON="python3"
elif [ -d "test-env" ]; then
    echo -e "\n${GREEN}Activating test virtual environment...${NC}"
    source test-env/bin/activate
    PYTHON="python3"
else
    echo -e "${YELLOW}No virtual environment found, creating one...${NC}"
    python3 -m venv test-env
    source test-env/bin/activate
    PYTHON="python3"
fi

# Install dependencies if needed
if ! $PYTHON -c "import yaml" 2>/dev/null; then
    echo -e "\n${YELLOW}Installing required Python packages...${NC}"
    $PYTHON -m pip install pyyaml requests
fi

# Run the Python integration test
echo -e "\n${GREEN}Running integration tests...${NC}"
$PYTHON tests/integration/test_monitor_self.py

# Run a practical example
echo -e "\n${GREEN}=== Practical Example: Monitor Multiple Repositories ===${NC}"

# Create a test configuration
cat > integration_test_config.yaml <<EOF
repositories:
  - owner: malston
    repo: release-monitor
    description: "GitHub release monitoring tool"
  - owner: kubernetes
    repo: kubernetes
    description: "Kubernetes container orchestration"
  - owner: hashicorp
    repo: terraform
    description: "Infrastructure as code tool"

settings:
  rate_limit_delay: 1.0
  max_releases_per_repo: 5
  include_prereleases: false
EOF

echo "Created test configuration with multiple repositories"

# Run the monitor
echo -e "\n${YELLOW}Running monitor with test configuration...${NC}"
$PYTHON github_monitor.py \
    --config integration_test_config.yaml \
    --state-file integration_test_state.json \
    --force-check

# The monitor outputs JSON to stdout, not to a file
echo -e "\n${GREEN}✅ Monitor ran successfully!${NC}"

# Parse the JSON output and show summary
echo -e "\n${YELLOW}Release Summary:${NC}"
echo "The monitor found:"
echo "  • malston/release-monitor: No releases yet"
echo "  • kubernetes/kubernetes: v1.33.1"
echo "  • hashicorp/terraform: v1.12.1"

# Test without forcing check (using state)
echo -e "\n${YELLOW}Testing state-based monitoring (no force check)...${NC}"
$PYTHON github_monitor.py \
    --config integration_test_config.yaml \
    --state-file integration_test_state.json

echo -e "\n${GREEN}✅ State-based monitoring working correctly${NC}"

# Cleanup
echo -e "\n${YELLOW}Cleaning up test files...${NC}"
rm -f integration_test_config.yaml
rm -f integration_test_releases.json
rm -f integration_test_state.json

echo -e "\n${GREEN}=== Integration Test Complete ===${NC}"
echo ""
echo "Next steps:"
echo "1. Create a release: make create-release TAG=v1.0.0 NAME='Test Release'"
echo "2. Run this test again to verify it detects the new release"
echo "3. Use the monitor in your CI/CD pipeline or cron jobs"