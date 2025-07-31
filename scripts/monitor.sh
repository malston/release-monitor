#!/bin/bash

set -o errexit
set -o pipefail

# GitHub Repository Release Monitoring Script
# Bash wrapper for use in Concourse pipelines

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONFIG_FILE="${APP_DIR}/config.yaml"
STATE_FILE="${APP_DIR}/release_state.json"
OUTPUT_FILE=""
OUTPUT_FORMAT="json"
FORCE_CHECK=false

# Function to display usage
usage() {
    local exit_code=${1:-1}
    cat <<EOF
Usage: $0 [OPTIONS]

Monitor GitHub repositories for new releases

Options:
  -c, --config FILE      Configuration file (default: ${CONFIG_FILE})
  -o, --output FILE      Output file (default: stdout)
  -f, --format FORMAT    Output format: json|yaml (default: json)
  -s, --state-file FILE  State file for tracking (default: ${STATE_FILE})
  --force-check          Check all releases regardless of timestamps
  -h, --help             Show this help message

Environment Variables:
  GITHUB_TOKEN           GitHub API token (required)

EOF
    exit "$exit_code"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -f|--format)
            OUTPUT_FORMAT="$2"
            shift 2
            ;;
        -s|--state-file)
            STATE_FILE="$2"
            shift 2
            ;;
        --force-check)
            FORCE_CHECK=true
            shift
            ;;
        -h|--help)
            usage 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate required environment variables
if [[ -z "${GITHUB_TOKEN}" ]]; then
    echo "Error: GITHUB_TOKEN environment variable is required"
    exit 1
fi

# Validate configuration file exists
if [[ ! -f "${CONFIG_FILE}" ]]; then
    echo "Error: Configuration file not found: ${CONFIG_FILE}"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is required but not installed"
    exit 1
fi

# Install requirements if pip is available and not in virtual env
if [[ -z "${VIRTUAL_ENV}" ]] && command -v pip3 &> /dev/null && [[ -f "${APP_DIR}/requirements.txt" ]]; then
    echo "Installing Python dependencies..."
    pip3 install -r "${APP_DIR}/requirements.txt" --quiet
fi

# Build Python command
PYTHON_CMD="python3 ${APP_DIR}/github_monitor.py"
PYTHON_CMD="${PYTHON_CMD} --config ${CONFIG_FILE}"
PYTHON_CMD="${PYTHON_CMD} --format ${OUTPUT_FORMAT}"
PYTHON_CMD="${PYTHON_CMD} --state-file ${STATE_FILE}"

if [[ -n "${OUTPUT_FILE}" ]]; then
    PYTHON_CMD="${PYTHON_CMD} --output ${OUTPUT_FILE}"
fi

if [[ "${FORCE_CHECK}" == "true" ]]; then
    PYTHON_CMD="${PYTHON_CMD} --force-check"
fi

# Execute the Python script
echo "Starting GitHub repository monitoring..."
echo "Config: ${CONFIG_FILE}"
echo "Output format: ${OUTPUT_FORMAT}"
if [[ -n "${OUTPUT_FILE}" ]]; then
    echo "Output file: ${OUTPUT_FILE}"
fi

eval "${PYTHON_CMD}"

exit_code=$?

if [[ ${exit_code} -eq 0 ]]; then
    echo "Monitoring completed successfully"
else
    echo "Monitoring failed with exit code: ${exit_code}"
fi

exit ${exit_code}
