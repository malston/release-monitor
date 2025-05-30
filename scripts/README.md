# Scripts Directory

This directory contains executable scripts for the GitHub release monitoring system.

## Scripts

### monitor.sh

Universal wrapper script for GitHub repository monitoring, suitable for both local development and CI/CD environments.

**Purpose**: Provides a bash interface to the Python monitoring script with parameter validation, environment setup, and proper path resolution from the scripts directory.

**Usage**:

```bash
./scripts/monitor.sh [OPTIONS]

Options:
  -c, --config FILE      Configuration file (default: config.yaml)
  -o, --output FILE      Output file (default: stdout)
  -f, --format FORMAT    Output format: json|yaml (default: json)
  -s, --state-file FILE  State file for tracking (default: release_state.json)
  --force-check          Check all releases regardless of timestamps
  -h, --help             Show help message
```

**Environment Variables**:

- `GITHUB_TOKEN`: GitHub API token (required)

**Features**:

- Parameter validation
- Environment variable checking
- Automatic dependency installation
- Error handling and exit codes
- Smart path resolution for both local and CI execution

## Integration

### Local Development

Use `monitor.sh` for local testing and development:

```bash
export GITHUB_TOKEN="your_token"
./scripts/monitor.sh --config config.yaml --output releases.json
```

### CI/CD Pipeline

The `check-releases` Concourse task uses the same `monitor.sh` script:

```bash
./scripts/monitor.sh --config config.yaml --output /release-output/releases.json --format json
```

### Testing

The test suite validates the script:

```bash
python3 test.py
```

## Dependencies

The script requires:

- Python 3.7+
- Dependencies listed in `requirements.txt`
- GitHub API token in environment

## Error Handling

The script provides:

- Clear error messages
- Non-zero exit codes on failure
- Validation of required parameters
- Dependency checking
