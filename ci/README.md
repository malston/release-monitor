# Concourse CI Structure

This directory contains the Concourse CI/CD pipeline for GitHub release monitoring.

## Structure

```text
ci/
├── pipeline.yml                      # Main pipeline definition
├── fly.sh                           # Pipeline deployment script
├── validate.sh                      # Pipeline validation script
├── README.md                        # This file
└── tasks/
    ├── check-releases/
    │   ├── task.yml                 # Task configuration
    │   └── task.sh                  # Task execution script
    └── download-tarballs/
        ├── task.yml                 # Task configuration
        └── task.sh                  # Task execution script
```

## Tasks

### check-releases

- **Purpose**: Monitor GitHub repositories for new releases
- **Image**: `python:3.11-slim`
- **Input**: `release-monitoring-repo` (source code)
- **Output**: `release-output` (JSON file with new releases)
- **Script**: `task.sh` installs dependencies and runs `scripts/monitor.sh`

### download-tarballs

- **Purpose**: Download release tarballs and upload to S3
- **Image**: `alpine/curl:latest`
- **Input**: `release-monitoring-repo` (source code), `s3-output` (release data)
- **Output**: `tarballs` (downloaded files)
- **Script**: `task.sh` processes release data and handles S3 uploads

## Usage

Deploy the pipeline using the fly script from the repository root:

```bash
# Validate pipeline before deployment
./ci/validate.sh

# Deploy to lab environment
./ci/fly.sh set -t lab -f lab

# Deploy to production
./ci/fly.sh set -t prod -f prod

# Destroy pipeline
./ci/fly.sh destroy -t prod
```

## Configuration

Pipeline parameters are managed in the `../params/` directory:

- `global.yml`: Shared parameters across environments
- `lab.yml`: Lab environment specific parameters
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
