#!/bin/bash
# Download releases from Artifactory to local directory

set -euo pipefail

# Default configuration
DEFAULT_ARTIFACTORY_URL="http://localhost:8081/artifactory"
DEFAULT_REPOSITORY="generic-releases"
DEFAULT_OUTPUT_DIR="./artifactory-downloads"

# Use environment variables or defaults
ARTIFACTORY_URL="${ARTIFACTORY_URL:-$DEFAULT_ARTIFACTORY_URL}"
ARTIFACTORY_REPOSITORY="${ARTIFACTORY_REPOSITORY:-$DEFAULT_REPOSITORY}"
OUTPUT_DIR="${OUTPUT_DIR:-$DEFAULT_OUTPUT_DIR}"

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Artifactory Release Downloader${NC}"
echo "=================================="
echo -e "📍 Artifactory URL: ${GREEN}$ARTIFACTORY_URL${NC}"
echo -e "📦 Repository: ${GREEN}$ARTIFACTORY_REPOSITORY${NC}"
echo -e "📂 Output Directory: ${GREEN}$OUTPUT_DIR${NC}"
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}⚠️  Python 3 is required but not found${NC}"
    exit 1
fi

# Install dependencies if needed
echo "🔧 Checking Python dependencies..."
python3 -c "import requests" 2>/dev/null || {
    echo "📦 Installing requests library..."
    pip3 install --user requests || {
        echo -e "${YELLOW}⚠️  Failed to install requests. You may need to run: pip3 install requests${NC}"
        exit 1
    }
}

# Export environment variables
export ARTIFACTORY_URL
export ARTIFACTORY_REPOSITORY

# Run the download script with all arguments passed through
echo ""
echo "📥 Starting download..."
echo ""

python3 "$(dirname "$0")/download-from-artifactory.py" "$@"

echo ""
echo -e "${GREEN}✅ Download complete!${NC}"

# Show download location if successful
if [ -d "$OUTPUT_DIR" ]; then
    echo ""
    echo "📋 Downloaded files:"
    find "$OUTPUT_DIR" -type f -name "*.tar.gz" -o -name "*.zip" | head -20
    
    TOTAL_FILES=$(find "$OUTPUT_DIR" -type f | wc -l | tr -d ' ')
    if [ "$TOTAL_FILES" -gt 20 ]; then
        echo "... and $((TOTAL_FILES - 20)) more files"
    fi
fi