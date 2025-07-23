# Downloading Releases from Artifactory

This guide explains how to download GitHub releases that have been uploaded to your JFrog Artifactory instance by the release-monitor pipeline.

## Prerequisites

1. **Artifactory Access**: Ensure you have access to your Artifactory instance
2. **Authentication**: You'll need one of the following:
   - API Key (recommended)
   - Username and Password
3. **Python 3**: The download script requires Python 3 with the `requests` library

## Quick Start

### 1. Set Environment Variables

```bash
# Required
export ARTIFACTORY_URL="http://localhost:8081/artifactory"
export ARTIFACTORY_REPOSITORY="generic-releases"

# Authentication (choose one)
export ARTIFACTORY_API_KEY="your-api-key"
# OR
export ARTIFACTORY_USERNAME="your-username"
export ARTIFACTORY_PASSWORD="your-password"
```

### 2. Download All Releases

```bash
# Using the convenience script
./scripts/download-releases-local.sh

# Or using Python directly
python3 scripts/download-from-artifactory.py
```

### 3. Download Specific Repository

```bash
# Download only Kubernetes releases
./scripts/download-releases-local.sh --repo kubernetes/kubernetes

# Download only Prometheus releases
./scripts/download-releases-local.sh --repo prometheus/prometheus
```

## Usage Examples

### List Available Repositories

See what repositories have releases available in Artifactory:

```bash
./scripts/download-releases-local.sh --list
```

### Download with Pattern Matching

Download only specific file types:

```bash
# Download only tar.gz files
./scripts/download-releases-local.sh --pattern "*.tar.gz"

# Download only Linux AMD64 binaries
./scripts/download-releases-local.sh --pattern "*linux-amd64*"
```

### Specify Output Directory

```bash
./scripts/download-releases-local.sh --output-dir ~/my-releases
```

### Download Specific Repository with Pattern

```bash
# Download only Kubernetes server binaries
./scripts/download-releases-local.sh \
  --repo kubernetes/kubernetes \
  --pattern "kubernetes-server-*.tar.gz"
```

## Advanced Usage

### Using Python Script Directly

The Python script provides more control:

```bash
python3 scripts/download-from-artifactory.py \
  --url http://localhost:8081/artifactory \
  --repository generic-releases \
  --api-key "your-api-key" \
  --repo istio/istio \
  --pattern "istio-*-linux-amd64.tar.gz" \
  --output-dir ./istio-releases \
  --verbose
```

### Skip SSL Verification

For self-signed certificates:

```bash
./scripts/download-releases-local.sh --no-verify-ssl
```

## Directory Structure

Downloaded files will be organized as follows:

```
downloaded-releases/
└── release-monitor/
    └── release-downloads/
        ├── kubernetes/
        │   └── kubernetes/
        │       ├── kubernetes-v1.28.0-linux-amd64.tar.gz
        │       └── kubernetes-v1.28.1-linux-amd64.tar.gz
        ├── prometheus/
        │   └── prometheus/
        │       └── prometheus-2.45.0.linux-amd64.tar.gz
        └── etcd-io/
            └── etcd/
                └── etcd-v3.5.9-linux-amd64.tar.gz
```

## Troubleshooting

### Authentication Errors

If you get 401 or 403 errors:

1. Verify your API key or credentials are correct
2. Check that your user has read permissions on the repository
3. Ensure the repository name is correct

### Connection Errors

If you can't connect to Artifactory:

1. Check the URL is correct (including the `/artifactory` suffix)
2. For local Docker setups, ensure port 8081 is accessible
3. Try with `--no-verify-ssl` if using self-signed certificates

### No Artifacts Found

If no artifacts are found:

1. Verify releases have been uploaded by the pipeline
2. Check the repository name matches what's configured in the pipeline
3. Use `--list` to see available repositories
4. Check the path prefix in Artifactory (default: `release-monitor/release-downloads/`)

## Script Options

### download-from-artifactory.py

```
Options:
  --url URL                 Artifactory base URL
  --repository REPO         Repository name (default: generic-releases)
  --username USER          Username for authentication
  --password PASS          Password for authentication
  --api-key KEY            API key for authentication
  --repo OWNER/REPO        Download specific repository
  --pattern PATTERN        File pattern to match (e.g., "*.tar.gz")
  --output-dir DIR         Output directory (default: ./artifactory-downloads)
  --list                   List available repositories without downloading
  --no-verify-ssl          Skip SSL certificate verification
```

## Integration with CI/CD

You can use these scripts in your CI/CD pipelines to fetch specific releases:

```yaml
# Example GitLab CI job
download-releases:
  script:
    - export ARTIFACTORY_URL="${ARTIFACTORY_URL}"
    - export ARTIFACTORY_API_KEY="${ARTIFACTORY_API_KEY}"
    - python3 scripts/download-from-artifactory.py --repo kubernetes/kubernetes --pattern "*server*.tar.gz" --output-dir ./artifactory-downloads
  artifacts:
    paths:
      - artifactory-downloads/
```

## Security Notes

1. **Never commit credentials**: Always use environment variables or secret management
2. **Use API Keys**: Prefer API keys over username/password authentication
3. **Verify SSL**: Only disable SSL verification for development/testing
4. **Limit Permissions**: Use read-only credentials for download operations

## Artifactory Repository Structure

The release-monitor pipeline stores artifacts in the following structure:

```
<repository>/
├── release-monitor/
│   ├── version_db.json                    # Version tracking database
│   ├── latest-releases.json               # Latest release metadata
│   └── release-downloads/                 # Downloaded artifacts
│       └── <owner>/
│           └── <repo>/
│               └── <release-files>
```

This structure allows for easy browsing in the Artifactory UI and programmatic access via the API.
