# GitHub Repository Release Monitor

🔍 **Never miss a critical update again!** A lightweight Python tool that monitors GitHub repositories for new releases, perfect for CI/CD pipelines, dependency tracking, and security updates.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.7+-green.svg)](https://www.python.org)
[![Concourse CI](https://img.shields.io/badge/works%20with-Concourse%20CI-blue)](https://concourse-ci.org)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Good First Issues](https://img.shields.io/github/issues/malston/release-monitor/good%20first%20issue)](https://github.com/malston/release-monitor/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)

**Quick Start**: New to Python? See our [Quick Start Guide](QUICK_START.md) for non-Python developers.

**Contributing**: Want to contribute? Please read our [Contributing Guide](CONTRIBUTING.md) for development setup, coding standards, and submission guidelines.

## 🚀 Why Use GitHub Release Monitor?

- **🔄 Automated Dependency Tracking**: Know instantly when your dependencies release new versions
- **🔐 Security Updates**: Stay on top of critical security patches
- **📊 CI/CD Integration**: Built specifically for Concourse pipelines (but works anywhere!)
- **💾 Stateful Monitoring**: Only alerts on truly new releases, not ones you've seen
- **🎯 Flexible Output**: JSON or YAML output for easy integration
- **⚡ Lightweight**: Simple Python script with minimal dependencies

Perfect for teams who need to:
- Track when Kubernetes, Terraform, or other tools release updates
- Automate dependency updates in their CI/CD pipelines  
- Monitor security tools for latest versions
- Build compliance reports showing update status

### 📸 Quick Example

```bash
$ python3 github_monitor.py --config config.yaml

{
  "timestamp": "2025-05-30T13:40:38.695772+00:00",
  "total_repositories_checked": 3,
  "new_releases_found": 2,
  "releases": [
    {
      "repository": "kubernetes/kubernetes",
      "tag_name": "v1.33.1",
      "name": "Kubernetes v1.33.1",
      "published_at": "2025-05-15T17:49:01Z",
      "html_url": "https://github.com/kubernetes/kubernetes/releases/tag/v1.33.1"
    },
    {
      "repository": "hashicorp/terraform", 
      "tag_name": "v1.12.1",
      "name": "v1.12.1",
      "published_at": "2025-05-21T13:02:01Z",
      "html_url": "https://github.com/hashicorp/terraform/releases/tag/v1.12.1"
    }
  ]
}
```

## Features

- **GitHub API Integration**: Authenticates with GitHub API using personal access tokens
- **Rate Limiting**: Built-in protection against API rate limits with automatic retry
- **State Tracking**: Maintains state between runs to detect only new releases
- **Multiple Output Formats**: Supports JSON and YAML output
- **Concourse Integration**: Designed for use in Concourse pipelines with bash wrapper
- **Error Handling**: Comprehensive error handling for network issues and API failures
- **Configurable**: YAML-based configuration for repository lists and settings

## Requirements

- Python 3.7+
- GitHub personal access token
- Dependencies: `requests`, `PyYAML`

## Installation

### Quick Start (Recommended)

Use the Makefile for easy setup:

```bash
# Complete setup
make setup

# Edit .env with your GitHub token
# Edit config-local.yaml with test repositories

# Run monitoring
make run
```

### Manual Installation

1. Clone or download the repository
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Set up your GitHub token:

   ```bash
   export GITHUB_TOKEN="your_personal_access_token"
   ```

## Configuration

Create a `config.yaml` file to specify repositories to monitor:

```yaml
repositories:
  - owner: kubernetes
    repo: kubernetes
    description: "Kubernetes container orchestration platform"
  
  - owner: istio
    repo: istio
    description: "Istio service mesh"

settings:
  rate_limit_delay: 1.0
  max_releases_per_repo: 10
  include_prereleases: false
```

## Usage

### Python Script

```bash
# Basic usage
python3 github_monitor.py --config config.yaml

# Save output to file
python3 github_monitor.py --config config.yaml --output releases.json

# YAML output format
python3 github_monitor.py --config config.yaml --format yaml

# Force check all releases (ignore timestamps)
python3 github_monitor.py --config config.yaml --force-check
```

### Bash Wrapper

```bash
# Basic usage
./scripts/monitor.sh

# Custom configuration
./scripts/monitor.sh --config custom-config.yaml --output releases.json

# YAML output
./scripts/monitor.sh --format yaml

# Force check
./scripts/monitor.sh --force-check
```

## Output Format

The script outputs structured data about new releases:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "total_repositories_checked": 8,
  "new_releases_found": 2,
  "releases": [
    {
      "repository": "kubernetes/kubernetes",
      "owner": "kubernetes",
      "repo": "kubernetes",
      "tag_name": "v1.29.1",
      "name": "v1.29.1",
      "published_at": "2024-01-14T15:20:30Z",
      "tarball_url": "https://api.github.com/repos/kubernetes/kubernetes/tarball/v1.29.1",
      "zipball_url": "https://api.github.com/repos/kubernetes/kubernetes/zipball/v1.29.1",
      "html_url": "https://github.com/kubernetes/kubernetes/releases/tag/v1.29.1",
      "prerelease": false,
      "draft": false
    }
  ]
}
```

## Concourse Integration

The project includes a complete Concourse CI/CD pipeline structure:

```text
ci/
├── pipeline.yml                      # Main pipeline definition
├── fly.sh                           # Deployment script
└── tasks/
    ├── check-releases/
    │   ├── task.yml                 # Task configuration
    │   └── task.sh                  # Task execution script
    └── download-tarballs/
        ├── task.yml                 # Task configuration
        └── task.sh                  # Task execution script

scripts/
└── monitor.sh                       # Universal monitoring script wrapper

params/
├── global.yml                       # Global parameters
├── lab.yml                         # Lab environment parameters
└── prod.yml                        # Production environment parameters
```

### Pipeline Setup

1. Configure parameters in `params/` directory:
   - Edit `global.yml` for shared configuration
   - Create environment-specific files (e.g., `lab.yml`, `prod.yml`)

2. Deploy the pipeline using the fly script:

   ```bash
   # Deploy to lab environment
   ./ci/fly.sh set -t lab -f lab

   # Deploy to production
   ./ci/fly.sh set -t prod -f prod
   ```

3. Unpause the pipeline:

   ```bash
   fly -t your-target unpause-pipeline -p github-release-monitor
   ```

### Pipeline Features

- **Scheduled Execution**: Runs monitoring every hour (configurable)
- **Release Detection**: Identifies new releases since last run
- **Tarball Download**: Downloads and stores release tarballs in S3
- **Structured Output**: Provides JSON output for downstream processing

## State Management

The script maintains state in `release_state.json` to track:

- Last checked timestamp for each repository
- Last overall run timestamp

This ensures only new releases are reported on subsequent runs.

## Error Handling

- **API Rate Limiting**: Automatic retry with exponential backoff
- **Network Errors**: Graceful handling of connection issues
- **Missing Releases**: Handles repositories with no releases
- **Invalid Configuration**: Clear error messages for configuration issues

## Environment Variables

- `GITHUB_TOKEN` (required): GitHub personal access token
- `AWS_ACCESS_KEY_ID` (Concourse): AWS access key for S3
- `AWS_SECRET_ACCESS_KEY` (Concourse): AWS secret key for S3

## Examples

### Basic Monitoring

```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"
./scripts/monitor.sh --config config.yaml
```

### Continuous Integration

```bash
# In a CI environment
./scripts/monitor.sh \
  --config config.yaml \
  --output /tmp/releases.json \
  --format json

# Process results
if [ $(jq '.new_releases_found' /tmp/releases.json) -gt 0 ]; then
  echo "New releases found, triggering downstream jobs"
  # Trigger additional pipeline steps
fi
```

### Custom Repository List

Create a custom configuration for specific projects:

```yaml
repositories:
  - owner: your-org
    repo: your-project
    description: "Internal project"
  
  - owner: hashicorp
    repo: terraform
    description: "Infrastructure as code"

settings:
  rate_limit_delay: 2.0  # Slower API calls
  include_prereleases: true  # Include pre-releases
```

## Troubleshooting

### Common Issues

1. **Rate Limiting**: Increase `rate_limit_delay` in configuration
2. **Token Issues**: Ensure `GITHUB_TOKEN` has proper permissions
3. **Network Errors**: Check connectivity to api.github.com
4. **State File Errors**: Check write permissions for state file location

### Debug Mode

Enable verbose logging by setting the log level:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Security Considerations

- Store GitHub tokens securely (environment variables, secret management)
- Use minimal token permissions (public repository read access)
- Regularly rotate access tokens
- Avoid logging sensitive information

## Performance

- Default rate limiting: 1 second between API calls
- Typical execution time: < 2 minutes for 10 repositories
- Memory usage: < 50MB for typical workloads
- Network usage: ~1KB per repository check

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details on:

- Setting up your development environment
- Code standards and best practices
- Testing requirements
- Pull request process
- Security considerations

For quick local setup, run:
```bash
./scripts/setup-local.sh
```

## Development Tools

### Makefile Commands

A Makefile is provided for common development tasks:

```bash
# Setup and Installation
make setup          # Complete local development setup
make install        # Install Python dependencies
make clean          # Clean generated files
make clean-all      # Clean everything including venv

# Development
make run            # Run monitoring with default config
make run-local      # Run with local config
make test           # Run all tests
make check          # Run lint, validate, and test
make watch          # Run continuously (every 5 minutes)

# CI/CD Pipeline
make validate       # Validate pipeline configuration
make pipeline-set-lab   # Deploy to lab
make pipeline-set-prod  # Deploy to production

# Help
make help           # Show all available commands
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for detailed information.

### 🎯 Where to Start Contributing

#### Good First Issues
Perfect for newcomers to the project:
- [🏷️ Good First Issues](https://github.com/malston/release-monitor/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) - Beginner-friendly tasks
- [🤝 Help Wanted](https://github.com/malston/release-monitor/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22) - Issues where we need help
- [✨ Enhancements](https://github.com/malston/release-monitor/issues?q=is%3Aissue+is%3Aopen+label%3Aenhancement) - New features and improvements

#### Types of Contributions We're Looking For
- 🐛 **Bug Fixes** - Help us squash bugs
- 📚 **Documentation** - Improve docs, add examples, fix typos
- ✨ **New Features** - Add support for new CI/CD tools (GitHub Actions, GitLab CI, etc.)
- 🧪 **Tests** - Increase test coverage
- 🎨 **Code Quality** - Refactoring and improvements
- 🌍 **Examples** - Add more use cases and integration examples

#### Quick Start for Contributors
1. **Find an Issue**: Browse [open issues](https://github.com/malston/release-monitor/issues) or create a new one
2. **Comment**: Let us know you're working on it
3. **Fork & Clone**: See our [Contributing Guide](CONTRIBUTING.md#fork-and-clone)
4. **Make Changes**: Follow our coding standards
5. **Submit PR**: We'll review and provide feedback

### Quick Links for Contributors

- [🍴 Fork the repository](https://github.com/malston/release-monitor/fork)
- [🐛 Report a bug](https://github.com/malston/release-monitor/issues/new?template=bug_report.md)
- [💡 Request a feature](https://github.com/malston/release-monitor/issues/new?template=feature_request.md)
- [📖 Contributing Guide](CONTRIBUTING.md)
- [👥 Contributors](CONTRIBUTORS.md)
- [💬 Discussions](https://github.com/malston/release-monitor/discussions) (coming soon)

## License

This project is provided as-is for educational and operational use.
