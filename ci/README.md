# Concourse CI Structure

This directory contains the Concourse CI/CD pipeline for the GitHub release monitor.

## Structure

```text
ci/
├── pipeline.yml                      # Main pipeline definition
├── pipeline-s3-compatible.yml       # S3-compatible pipeline (MinIO support)
├── pipeline-simple.yml              # Simplified pipeline (no S3 required)
├── fly.sh                           # Pipeline deployment script
├── validate.sh                      # Pipeline validation script
├── README.md                        # This file
└── tasks/
    ├── check-releases/
    │   ├── task.yml                 # Task configuration
    │   └── task.sh                  # Task execution script
    ├── check-releases-simple/
    │   ├── task.yml                 # Task configuration (simplified)
    │   └── task.sh                  # Task execution script
    └── download-releases/
        ├── task.yml                 # Task configuration
        └── task.sh                  # Task execution script
```

## Tasks

### check-releases

- **Purpose**: Monitor GitHub repositories for new releases
- **Image**: `python:3.11-slim`
- **Input**: `release-monitor-repo` (source code)
- **Output**: `release-output` (JSON file with new releases)
- **Script**: `task.sh` installs dependencies and runs `github_monitor.py`

### check-releases-simple

- **Purpose**: Simplified monitoring for basic setups (no S3 required)
- **Image**: `python:3.11-slim`
- **Input**: `release-monitor-repo` (source code)
- **Output**: `release-output` (JSON file with new releases)
- **Script**: `task.sh` basic monitoring without S3 dependencies

### download-releases

- **Purpose**: Download GitHub release assets with sophisticated version tracking
- **Image**: `python:3.9-slim`
- **Input**: `release-monitor-repo` (source code), `monitor-output` (release data)
- **Output**: `downloads` (downloaded release assets)
- **Script**: `task.sh` uses `download_releases.py` with S3 version tracking and asset filtering

## Usage

Deploy the pipeline using the fly script from the repository root:

```bash
# Validate pipeline before deployment
./ci/validate.sh

# Deploy to test environment
./ci/fly.sh set -t test -f test

# Deploy to production
./ci/fly.sh set -t prod -f prod

# Destroy pipeline
./ci/fly.sh destroy -t prod
```

## Configuration

Pipeline parameters are managed in the `../params/` directory:

- `global.yml`: Shared parameters across environments
- `test.yml`: Test environment specific parameters
- `prod.yml`: Production environment specific parameters

### Variable Naming Convention

All Concourse variables use underscore notation (snake_case) following best practices:

- `github_token` (not `github-token`)
- `s3_bucket` (not `s3-bucket`)
- `git_repo_uri` (not `git-repo-uri`)

This ensures consistency and compatibility across all Concourse components.

## Pipeline Flow

1. **Trigger**: Time-based (hourly) or manual
2. **check-releases**: Monitor repositories and detect new releases
3. **Store Results**: Save release data to S3
4. **download-tarballs**: Download and store tarballs for new releases
5. **Complete**: Pipeline finishes successfully

Each task is self-contained with its own configuration and execution script, following Concourse best practices for modularity and maintainability.
