#!/bin/bash

set -o errexit
set -o pipefail

# Local Development Setup Script
# Helps developers set up their local environment safely

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "Setting up local development environment..."

# Create local config if it doesn't exist
if [[ ! -f "${PROJECT_ROOT}/config-local.yaml" ]]; then
    echo "Creating local configuration file..."
    cp "${PROJECT_ROOT}/config-local.yaml.example" "${PROJECT_ROOT}/config-local.yaml"
    echo "✓ Created config-local.yaml from template"
    echo "  Please edit config-local.yaml with your test repositories"
else
    echo "✓ config-local.yaml already exists"
fi

# Create .env file if it doesn't exist
if [[ ! -f "${PROJECT_ROOT}/.env" ]]; then
    echo "Creating environment variables file..."
    cp "${PROJECT_ROOT}/.env.example" "${PROJECT_ROOT}/.env"
    echo "✓ Created .env from template"
    echo "  Please edit .env with your actual API tokens and credentials"
    echo "  IMPORTANT: Never commit the .env file!"
else
    echo "✓ .env already exists"
fi

# Create Python virtual environment if it doesn't exist
if [[ ! -d "${PROJECT_ROOT}/venv" ]]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "${PROJECT_ROOT}/venv"
    echo "✓ Created Python virtual environment"
else
    echo "✓ Python virtual environment already exists"
fi

# Install dependencies
echo "Installing Python dependencies..."
source "${PROJECT_ROOT}/venv/bin/activate"
"${PROJECT_ROOT}/venv/bin/pip" install -r "${PROJECT_ROOT}/requirements.txt"
echo "✓ Dependencies installed"

# Check git status
echo ""
echo "Git status check:"
cd "${PROJECT_ROOT}"

# Check if any sensitive files might be staged
SENSITIVE_FILES=$(git status --porcelain | grep -E "\.(env|key|pem|token)" || true)
if [[ -n "$SENSITIVE_FILES" ]]; then
    echo "⚠️  WARNING: Potentially sensitive files detected in git:"
    echo "$SENSITIVE_FILES"
    echo "   Make sure these files are in .gitignore!"
fi

echo ""
echo "🎉 Local development setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your GitHub token: GITHUB_TOKEN=your_token_here"
echo "2. Edit config-local.yaml with test repositories"
echo "3. Activate virtual environment: source venv/bin/activate"
echo "4. Run tests: python3 test.py"
echo "5. Run monitoring: ./scripts/monitor.sh --config config-local.yaml"