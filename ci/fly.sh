#!/bin/bash

set -o errexit
set -o pipefail

# Concourse Fly Script for GitHub Release Monitor Pipeline
# Usage: ./fly.sh set|destroy [options]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_NAME="github-release-monitor"
TARGET=""
FOUNDATION=""

# Function to display usage
usage() {
    local exit_code=${1:-1}
    cat <<EOF
Usage: $0 <command> [options]

Commands:
  set       Deploy/update the pipeline
  destroy   Delete the pipeline

Options:
  -t, --target TARGET     Concourse target (required)
  -f, --foundation FOUNDATION   Foundation name for parameter files
  -h, --help              Show this help message

Examples:
  ./fly.sh set -t prod -f lab
  ./fly.sh destroy -t prod

EOF
    exit "$exit_code"
}

# Parse command line arguments
COMMAND=""

# Check for help first
for arg in "$@"; do
    if [[ "$arg" == "-h" || "$arg" == "--help" ]]; then
        usage 0
    fi
done

if [[ $# -gt 0 ]]; then
    COMMAND="$1"
    shift
fi

while [[ $# -gt 0 ]]; do
    case $1 in
    -t | --target)
        TARGET="$2"
        shift 2
        ;;
    -f | --foundation)
        FOUNDATION="$2"
        shift 2
        ;;
    -h | --help)
        usage 0
        ;;
    *)
        echo "Unknown option: $1"
        usage
        ;;
    esac
done

# Validate required parameters
if [[ -z "${COMMAND}" ]]; then
    echo "Error: Command is required"
    usage
fi

if [[ -z "${TARGET}" ]]; then
    echo "Error: Target is required"
    usage
fi

# Validate command
case "${COMMAND}" in
set | destroy) ;;
*)
    echo "Error: Invalid command '${COMMAND}'. Use 'set' or 'destroy'"
    usage
    ;;
esac

# Check if fly is available
if ! command -v fly &>/dev/null; then
    echo "Error: fly CLI is required but not installed"
    echo "Install from: https://concourse-ci.org/download.html"
    exit 1
fi

# Build parameter files list
PARAM_FILES=()

# Add foundation-specific parameters if foundation is specified
if [[ -n "${FOUNDATION}" ]]; then
    FOUNDATION_PARAMS="${SCRIPT_DIR}/../params/${FOUNDATION}.yml"
    if [[ -f "${FOUNDATION_PARAMS}" ]]; then
        PARAM_FILES+=("-l" "${FOUNDATION_PARAMS}")
        echo "Using foundation parameters: ${FOUNDATION_PARAMS}"
    else
        echo "Warning: Foundation parameter file not found: ${FOUNDATION_PARAMS}"
    fi
fi

# Add global parameters
GLOBAL_PARAMS="${SCRIPT_DIR}/../params/global.yml"
if [[ -f "${GLOBAL_PARAMS}" ]]; then
    PARAM_FILES+=("-l" "${GLOBAL_PARAMS}")
    echo "Using global parameters: ${GLOBAL_PARAMS}"
fi

# Execute command
case "${COMMAND}" in
set)
    echo "Deploying pipeline '${PIPELINE_NAME}' to target '${TARGET}'..."

    fly -t "${TARGET}" set-pipeline \
        -p "${PIPELINE_NAME}" \
        -c "${SCRIPT_DIR}/pipeline.yml" \
        "${PARAM_FILES[@]}"

    cat <<EOF

Pipeline deployed successfully!
To unpause the pipeline, run:
  fly -t ${TARGET} unpause-pipeline -p ${PIPELINE_NAME}
EOF
    ;;

destroy)
    echo "Destroying pipeline '${PIPELINE_NAME}' from target '${TARGET}'..."

    fly -t "${TARGET}" destroy-pipeline \
        -p "${PIPELINE_NAME}" \
        --non-interactive

    echo "Pipeline destroyed successfully!"
    ;;
esac
