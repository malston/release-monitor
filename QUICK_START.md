# Quick Start Guide for Non-Python Developers

This guide helps you get started with the GitHub Release Monitoring tool without needing deep Python knowledge.

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
cd release-monitoring

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
```

### Clean Up
```bash
# Clean generated files
make clean

# Remove everything (including setup)
make clean-all
```

### Deploy to Concourse
```bash
# Deploy to lab environment
make pipeline-set-lab

# Deploy to production (be careful!)
make pipeline-set-prod
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