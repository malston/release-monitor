#!/bin/bash

# GitHub Release Downloader - Bash Wrapper
# Provides a convenient interface for downloading GitHub releases

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default values
CONFIG_FILE="${PROJECT_ROOT}/config.yaml"
INPUT_FILE="-"
OUTPUT_FILE=""
VERBOSE=""
DRY_RUN=""
STATUS=""

# Help function
show_help() {
    cat << EOF
GitHub Release Downloader

Downloads GitHub release assets based on monitor output and version comparison.

USAGE:
    $0 [OPTIONS]

OPTIONS:
    -c, --config FILE       Configuration file (default: config.yaml)
    -i, --input FILE        Monitor output file, - for stdin (default: -)
    -o, --output FILE       Output file for results (default: stdout)
    -v, --verbose           Enable verbose logging
    -n, --dry-run           Show what would be downloaded without downloading
    -s, --status            Show status report and exit
    -h, --help              Show this help message

ENVIRONMENT VARIABLES:
    GITHUB_TOKEN           GitHub API token (required)
    PYTHON                 Python executable to use (default: python3)

EXAMPLES:
    # Download from monitor output file
    $0 --input releases.json --config config.yaml

    # Download from stdin (typical pipeline usage)
    ./scripts/monitor.sh | $0

    # Dry run to see what would be downloaded
    $0 --input releases.json --dry-run

    # Get status report
    $0 --status

    # Verbose output with custom config
    $0 --config custom.yaml --verbose

CONFIGURATION:
    The configuration file should include a 'download' section:

    download:
      enabled: true
      directory: ./downloads
      asset_patterns:
        - "*.tar.gz"
        - "*.zip"
        - "!*-sources.zip"
      include_prereleases: false
      verify_downloads: true
      cleanup_old_versions: true
      keep_versions: 5

INTEGRATION:
    This script is designed to work with the GitHub release monitor:
    
    # Monitor and download in one pipeline
    ./scripts/monitor.sh | ./scripts/download.sh

    # Save monitor output and process later
    ./scripts/monitor.sh --output releases.json
    ./scripts/download.sh --input releases.json

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        -i|--input)
            INPUT_FILE="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE="--verbose"
            shift
            ;;
        -n|--dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        -s|--status)
            STATUS="--status"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option $1${NC}" >&2
            echo "Use --help for usage information." >&2
            exit 1
            ;;
    esac
done

# Check for required environment variables
if [[ -z "${GITHUB_TOKEN:-}" ]]; then
    echo -e "${RED}Error: GITHUB_TOKEN environment variable is required${NC}" >&2
    echo "Get your token from: https://github.com/settings/tokens" >&2
    exit 1
fi

# Determine Python executable
PYTHON="${PYTHON:-python3}"

# Check if Python is available
if ! command -v "$PYTHON" &> /dev/null; then
    echo -e "${RED}Error: Python ($PYTHON) not found${NC}" >&2
    exit 1
fi

# Check if config file exists (unless we're just getting status)
if [[ -z "$STATUS" && ! -f "$CONFIG_FILE" ]]; then
    echo -e "${RED}Error: Configuration file not found: $CONFIG_FILE${NC}" >&2
    echo "Create a configuration file or specify a different one with --config" >&2
    exit 1
fi

# Change to project root
cd "$PROJECT_ROOT"

# Build command arguments
ARGS=()

if [[ -n "$CONFIG_FILE" ]]; then
    ARGS+=(--config "$CONFIG_FILE")
fi

if [[ -n "$INPUT_FILE" ]]; then
    ARGS+=(--input "$INPUT_FILE")
fi

if [[ -n "$OUTPUT_FILE" ]]; then
    ARGS+=(--output "$OUTPUT_FILE")
fi

if [[ -n "$VERBOSE" ]]; then
    ARGS+=($VERBOSE)
fi

if [[ -n "$DRY_RUN" ]]; then
    ARGS+=($DRY_RUN)
fi

if [[ -n "$STATUS" ]]; then
    ARGS+=($STATUS)
fi

# Show what we're doing (unless getting status)
if [[ -z "$STATUS" && -n "$VERBOSE" ]]; then
    echo -e "${GREEN}GitHub Release Downloader${NC}"
    echo "Config: $CONFIG_FILE"
    echo "Input: $INPUT_FILE"
    echo "Output: ${OUTPUT_FILE:-stdout}"
    if [[ -n "$DRY_RUN" ]]; then
        echo -e "${YELLOW}Mode: DRY RUN${NC}"
    fi
    echo ""
fi

# Execute the download script
exec "$PYTHON" download_releases.py "${ARGS[@]}"