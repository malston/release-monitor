#!/bin/bash

# Validation script for simplified Concourse pipeline
# This script validates the pipeline configuration without S3 dependencies

set -o errexit
set -o pipefail

echo "Validating simplified Concourse pipeline configuration..."

# Check if required files exist
REQUIRED_FILES=(
    "ci/pipeline-simple.yml"
    "ci/tasks/check-releases-simple/task.yml"
    "ci/tasks/check-releases-simple/task.sh"
    "params/global.yml"
    "params/test.yml"
    "config.yaml"
    "requirements.txt"
)

echo "Checking required files..."
for file in "${REQUIRED_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        echo "✓ $file"
    else
        echo "❌ Missing required file: $file"
        exit 1
    fi
done

# Validate YAML syntax
echo -e "\nValidating YAML syntax..."
if command -v yamllint &> /dev/null; then
    yamllint ci/pipeline-simple.yml ci/tasks/check-releases-simple/task.yml params/*.yml
    echo "✓ YAML syntax validation passed"
elif python3 -c "import yaml" 2>/dev/null; then
    for yaml_file in ci/pipeline-simple.yml ci/tasks/check-releases-simple/task.yml params/global.yml params/test.yml; do
        if python3 -c "import yaml; yaml.safe_load(open('$yaml_file'))" 2>/dev/null; then
            echo "✓ $yaml_file"
        else
            echo "❌ Invalid YAML: $yaml_file"
            exit 1
        fi
    done
else
    echo "⚠️  No YAML validator found (yamllint or Python yaml module)"
fi

# Check script permissions
echo -e "\nChecking script permissions..."
if [[ -x "ci/tasks/check-releases-simple/task.sh" ]]; then
    echo "✓ task.sh is executable"
else
    echo "❌ task.sh is not executable"
    exit 1
fi

# Check if fly CLI is available (optional)
echo -e "\nChecking Concourse CLI..."
if command -v fly &> /dev/null; then
    echo "✓ Concourse fly CLI is available"
    
    # Validate pipeline syntax with fly
    if fly validate-pipeline -c ci/pipeline-simple.yml &>/dev/null; then
        echo "✓ Pipeline syntax validation passed"
    else
        echo "❌ Pipeline syntax validation failed"
        exit 1
    fi
else
    echo "⚠️  Concourse fly CLI not found - skipping pipeline syntax validation"
    echo "   Install from: https://concourse-ci.org/download.html"
fi

# Check environment variables guidance
echo -e "\nEnvironment variable requirements for deployment:"
echo "  Required: GITHUB_TOKEN"
echo "  Optional: git_private_key (for private repositories)"
echo ""
echo "To deploy the simplified pipeline:"
echo "  make pipeline-set-test-simple              # For public repositories"
echo "  make pipeline-set-test-simple-with-key     # For private repositories"

echo -e "\n✅ Simplified pipeline validation completed successfully!"
echo ""
echo "Key benefits of the simplified pipeline:"
echo "  • No S3 configuration required"
echo "  • Perfect for getting started"
echo "  • Results logged to console"
echo "  • Validates repository configuration"
echo "  • Easy to troubleshoot"