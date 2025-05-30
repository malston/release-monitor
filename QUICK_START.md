# Quick Start Guide for Non-Python Developers

This guide helps you get started with the GitHub Release Monitor tool without needing deep Python knowledge.

## Prerequisites

You need:

- A computer with macOS, Linux, or WSL on Windows
- Git installed
- Python 3.7+ installed (check with `python3 --version`)
- A GitHub personal access token

## 1. Initial Setup (One Time)

```bash
# Clone the repository
git clone <repository-url>
cd release-monitor

# Run the setup (creates everything you need)
make setup

# This created two important files:
# - .env (for your GitHub token)
# - config-local.yaml (for test repositories)
```

## 2. Configure Your GitHub Token

Edit the `.env` file:

```bash
# Open in your favorite editor
nano .env  # or vim, code, etc.

# Add your GitHub token:
GITHUB_TOKEN=ghp_your_actual_token_here
```

## 3. Configure Repositories to Monitor

Edit `config-local.yaml`:

```yaml
repositories:
  - owner: kubernetes
    repo: kubernetes
    description: "Kubernetes"
  
  - owner: docker
    repo: cli
    description: "Docker CLI"
```

## 4. Run the Monitoring

```bash
# Run with your local config
make run-local

# Or run with the default config
make run

# Watch for new releases every 5 minutes
make watch
```

## 5. Common Tasks

### See Available Commands

```bash
make help
```

### Run Tests

```bash
make test
```

### Validate Everything

```bash
make check

# Or validate just the simplified pipeline
make validate-simple
```

### Clean Up

```bash
# Clean generated files
make clean

# Remove everything (including setup)
make clean-all
```

### Deploy to Concourse

**Option 1: Simplified Pipeline (Recommended for Getting Started)**

No S3 configuration required - results are logged to console:

```bash
# Set your GitHub token first
export GITHUB_TOKEN="your_github_token_here"

# Validate the simplified pipeline
make validate-simple

# Deploy simplified pipeline (public repos)
make pipeline-set-test-simple

# Deploy simplified pipeline (private repos with SSH key)
make pipeline-set-test-simple-with-key
```

**Option 2: Full Pipeline with S3 Storage**

Requires S3 configuration for storing results and downloads:

```bash
# Set your GitHub token first
export GITHUB_TOKEN="your_github_token_here"

# Deploy to test environment (public repos)
make pipeline-set-test

# Deploy to production (be careful!)
make pipeline-set-prod
```

**For Private Repositories (SSH Key Required):**

```bash
# Set your GitHub token first
export GITHUB_TOKEN="your_github_token_here"

# Deploy to test environment with SSH key
make pipeline-set-test-with-key

# Or manually specify the SSH key
fly -t test set-pipeline \
  -p github-release-monitor \
  -c ci/pipeline.yml \
  -l params/global.yml \
  -l params/test.yml \
  --var git_private_key="$(cat ~/.ssh/id_ed25519)" \
  --var github_token="$GITHUB_TOKEN"
```

**Which Option Should I Choose?**

- **Simplified Pipeline**: Perfect for getting started, testing, or when you just need to monitor releases without storing artifacts
- **Full Pipeline**: Use when you need to store results in S3, download release artifacts, or have advanced storage requirements

**Note:** The SSH key is only needed if you're monitoring private repositories. For public repositories, the default targets work fine.

**SSH Key Setup:** If you don't have an SSH key, create one:

```bash
# Modern Ed25519 key (recommended)
ssh-keygen -t ed25519 -C "your_email@example.com"

# Or traditional RSA key
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# Add to GitHub
cat ~/.ssh/id_ed25519.pub  # Copy and add to GitHub SSH keys
```

## 6. Troubleshooting

### "Command not found: make"

Install make:

- macOS: `xcode-select --install`
- Ubuntu/Debian: `sudo apt-get install build-essential`
- RHEL/CentOS: `sudo yum groupinstall "Development Tools"`

### "Python not found"

Install Python 3:

- macOS: `brew install python3`
- Ubuntu/Debian: `sudo apt-get install python3`
- RHEL/CentOS: `sudo yum install python3`

### "No module named 'yaml'"

```bash
# The setup should handle this, but if not:
make install
```

### "GITHUB_TOKEN environment variable is required"

Make sure you edited `.env` with your actual GitHub token.

### See What's Configured

```bash
make show-config
```

## 7. Examples

### See JSON Output

```bash
make example-json
```

### See YAML Output

```bash
make example-yaml
```

### Show Only New Releases

```bash
make example-new-releases
```

## 8. Development Workflow

1. Make changes to the code
2. Run tests: `make test`
3. Validate pipeline: `make validate`
4. Check everything: `make check`
5. See what changed: `make git-status`

## Need More Help?

- Run `make help` to see all commands
- Read [CONTRIBUTING.md](CONTRIBUTING.md) for detailed development guide
- Check the main [README.md](README.md) for full documentation

## Quick Reference Card

```bash
# Daily Use
make run-local      # Run with your config
make watch          # Run continuously
make show-config    # See current settings

# Development
make test           # Run tests
make check          # Run all checks
make clean          # Clean up files

# Help
make help           # Show all commands
make                # Same as make help
```

That's it! You're ready to monitor GitHub releases without being a Python expert.
