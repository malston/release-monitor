# Contributing to GitHub Release Monitor

Thank you for your interest in contributing to the GitHub Release Monitor project! This document provides guidelines and instructions for contributing code, reporting issues, and improving the project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Security Considerations](#security-considerations)
- [Documentation](#documentation)
- [Getting Help](#getting-help)

## Getting Started

### Prerequisites

- Python 3.7 or higher
- Git
- A GitHub account and personal access token
- Basic knowledge of:
  - Python and bash scripting
  - YAML configuration
  - Concourse CI/CD (for pipeline contributions)

### Fork and Clone

We use the GitHub fork-and-pull model for contributions. This ensures a clean separation between the main repository and your development work.

1. **Fork the repository on GitHub:**
   - Navigate to https://github.com/malston/release-monitor
   - Click the "Fork" button in the top-right corner
   - This creates your own copy of the repository under your GitHub account

2. **Clone your fork locally:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/release-monitor.git
   cd release-monitor
   ```

3. **Add the upstream remote:**
   ```bash
   git remote add upstream https://github.com/malston/release-monitor.git
   ```

4. **Verify your remotes:**
   ```bash
   git remote -v
   # You should see:
   # origin    https://github.com/YOUR_USERNAME/release-monitor.git (fetch)
   # origin    https://github.com/YOUR_USERNAME/release-monitor.git (push)
   # upstream  https://github.com/malston/release-monitor.git (fetch)
   # upstream  https://github.com/malston/release-monitor.git (push)
   ```

## Development Setup

### Quick Setup

Use the Makefile for simple setup (recommended for non-Python developers):

```bash
make setup
```

Or use the setup script directly:

```bash
./scripts/setup-local.sh
```

This will:
- Create local configuration files from templates
- Set up Python virtual environment
- Install dependencies
- Check for potential security issues

### Manual Setup

If you prefer manual setup:

1. **Create Virtual Environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   ```bash
   cp .env.example .env
   cp config-local.yaml.example config-local.yaml
   ```

4. **Set Your GitHub Token:**
   Edit `.env` and add your GitHub personal access token:
   ```bash
   GITHUB_TOKEN=your_github_token_here
   ```

5. **Configure Test Repositories:**
   Edit `config-local.yaml` with repositories you want to test against.

## Code Standards

### Python Code

- Follow [PEP 8](https://pep8.org/) style guidelines
- Use type hints where appropriate
- Include docstrings for functions and classes
- Maximum line length: 100 characters
- Use meaningful variable and function names

### Bash Scripts

- Use `set -o errexit` and `set -o pipefail`
- Quote variables: `"${VARIABLE}"` not `$VARIABLE`
- Use descriptive function names
- Include comments for complex logic
- Follow existing script patterns in the codebase

### YAML Configuration

- Use 2-space indentation
- Follow existing structure and naming conventions
- Include comments for complex configurations
- Use underscore notation for Concourse variables (e.g., `github_token`)

### Commit Messages

Write clear, descriptive commit messages:

```
Short summary (50 chars or less)

More detailed explanation if needed. Wrap at 72 characters.
Include the motivation for the change and contrast with previous behavior.

- Bullet points are okay
- Use present tense: "Add feature" not "Added feature"
- Reference issues: "Fixes #123"
```

## Testing

### Running Tests

Using Make (recommended):
```bash
# Run all tests
make test

# Run all checks (lint, validate, test)
make check
```

Or manually:
```bash
# Activate virtual environment
source venv/bin/activate

# Run the test suite
python3 test.py

# Test specific functionality
./scripts/monitor.sh --config config-local.yaml --help
```

### Integration Tests

The project includes integration tests that demonstrate monitoring releases outside of Concourse pipelines. These tests are useful for verifying functionality in local development, cron jobs, or other CI/CD systems.

#### Running Integration Tests

```bash
# Run the full integration test suite
make integration-test

# Run just the Python integration test
make test-monitor-self
```

#### Creating Test Releases

To test release monitoring with actual releases:

```bash
# Create a GitHub release (requires GitHub CLI)
make create-release TAG=v1.0.0 NAME='Test Release 1.0.0' NOTES='Optional release notes'
```

#### What Integration Tests Do

1. **Monitor this repository** - Tests monitoring `malston/release-monitor` for releases
2. **Monitor other repositories** - Tests monitoring popular repos like `kubernetes/kubernetes`
3. **Test state tracking** - Verifies the monitor correctly tracks previously seen releases
4. **Test output formats** - Validates JSON and YAML output formats

#### Integration Test Requirements

- GitHub personal access token (set in `.env` file or `GITHUB_TOKEN` environment variable)
  - For basic monitoring: token needs `repo` scope
  - For creating releases: token needs `workflow` scope (or create releases manually on GitHub)
- Python virtual environment with dependencies installed
- GitHub CLI (`gh`) for creating test releases (optional)

### Test Requirements

- All new features must include tests
- Maintain or improve code coverage
- Test both success and error conditions
- Mock external dependencies (GitHub API calls)

### Validation

Before submitting changes, use the Makefile:

```bash
# Run all pre-commit checks
make pre-commit

# Or run individual checks:
make validate   # Validate pipeline syntax
make test       # Run test suite
make lint       # Check code style
```

Or manually:
```bash
# Validate Concourse pipeline syntax
./ci/validate.sh

# Run full test suite
python3 test.py

# Test scripts manually
./scripts/monitor.sh --config test-config.yaml --help
./ci/fly.sh --help
```

## Submitting Changes

### Pull Request Process

1. **Sync with Upstream:**
   Before starting work, ensure your fork is up to date:
   ```bash
   git checkout main
   git fetch upstream
   git merge upstream/main
   git push origin main
   ```

2. **Create a Feature Branch:**
   Always create a new branch from main for your work:
   ```bash
   git checkout -b feature/your-feature-name
   ```
   
   Use descriptive branch names:
   - `feature/add-slack-notifications`
   - `fix/handle-empty-releases`
   - `docs/update-setup-guide`

3. **Make Your Changes:**
   - Write code following the standards above
   - Add tests for new functionality
   - Update documentation if needed

4. **Test Your Changes:**
   ```bash
   # Run unit tests
   python3 test.py
   
   # Run integration tests
   make integration-test
   
   # Validate pipeline syntax
   ./ci/validate.sh
   ```

5. **Commit Your Changes:**
   ```bash
   git add .
   git commit -m "Add feature: description of your changes"
   ```

6. **Push to Your Fork:**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Create Pull Request:**
   - Go to your fork on GitHub
   - Click "Compare & pull request" button
   - Ensure the base repository is `malston/release-monitor` and base branch is `main`
   - Ensure the head repository is your fork and compare branch is your feature branch
   - Fill in the pull request template
   - Link to any related issues

8. **Keep Your PR Updated:**
   If the main branch is updated while your PR is open:
   ```bash
   git checkout main
   git fetch upstream
   git merge upstream/main
   git checkout feature/your-feature-name
   git rebase main
   git push --force-with-lease origin feature/your-feature-name
   ```

### Pull Request Guidelines

- Keep changes focused and atomic
- Include tests for new functionality
- Update documentation for user-facing changes
- Ensure CI/CD pipeline passes
- Respond to review feedback promptly

## Security Considerations

### Never Commit Secrets

- Never commit API tokens, passwords, or credentials
- Use `.env` files for local secrets (already in `.gitignore`)
- Use Concourse credential management for CI/CD
- Review the `.gitignore` file to understand what's excluded

### Security Best Practices

- Validate all user inputs
- Use secure defaults
- Avoid logging sensitive information
- Keep dependencies up to date
- Follow the principle of least privilege

### Reporting Security Issues

If you discover a security vulnerability:
1. **DO NOT** create a public issue
2. Email the maintainers directly (see README for contact info)
3. Include detailed information about the vulnerability
4. Allow time for the issue to be addressed before public disclosure

## Documentation

### What to Document

- New features and their usage
- Configuration options
- API changes
- Breaking changes
- Troubleshooting guides

### Documentation Standards

- Use clear, concise language
- Include code examples
- Update both inline comments and external docs
- Use proper markdown formatting
- Test all examples

### Files to Update

When making changes, consider updating:
- `README.md` - Main project documentation
- `ci/README.md` - CI/CD specific documentation
- `scripts/README.md` - Script usage documentation
- Inline code comments and docstrings

## Development Workflow

### Typical Development Flow

1. **Fork:** Fork the repository on GitHub (one-time setup)
2. **Clone:** Clone your fork locally
3. **Setup:** Use `./scripts/setup-local.sh` or `make setup`
4. **Sync:** Sync with upstream `main` branch
5. **Branch:** Create feature branch from `main`
6. **Develop:** Write code, tests, and documentation
7. **Test:** Run `make test`, `make integration-test`, and `./ci/validate.sh`
8. **Commit:** Use descriptive commit messages
9. **Push:** Push to your fork
10. **PR:** Create pull request to upstream repository

### Working with Forks

**Why we use forks:**
- Keeps the main repository clean
- Allows experimentation without affecting others
- Provides better security and access control
- Enables easier code review process

**Best practices:**
- Keep your fork's main branch in sync with upstream
- Never commit directly to main in your fork
- Always work in feature branches
- Delete branches after PRs are merged

### Working with Concourse

If modifying CI/CD components:

1. **Validate Syntax:**
   ```bash
   ./ci/validate.sh
   ```

2. **Test Locally:**
   ```bash
   # Test individual tasks
   ./scripts/monitor.sh --config test-config.yaml
   ```

3. **Document Changes:**
   - Update pipeline documentation
   - Include parameter changes in PR description

## Getting Help

### Resources

- **Documentation:** Start with the main README.md
- **Examples:** Check the `test-config.yaml` and example files
- **Issues:** Search existing GitHub issues
- **Code:** Read the existing codebase for patterns

### Asking Questions

When asking for help:
1. Search existing issues first
2. Provide context and specific error messages
3. Include steps to reproduce problems
4. Share relevant configuration (without secrets!)
5. Be respectful and patient

### Communication

- Use GitHub issues for bugs and feature requests
- Keep discussions focused and constructive
- Follow the project's code of conduct
- Be open to feedback and collaboration

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Maintain a welcoming environment

## Types of Contributions

We welcome various types of contributions:

- **Bug fixes** - Fix issues in existing functionality
- **Features** - Add new monitoring capabilities
- **Documentation** - Improve guides and examples
- **Testing** - Add test coverage and validation
- **Performance** - Optimize existing code
- **CI/CD** - Improve pipeline and automation
- **Security** - Enhance security practices

## Recognition

Contributors will be recognized in:
- Git commit history
- Pull request acknowledgments
- Release notes for significant contributions

Thank you for contributing to GitHub Release Monitor! 🎉