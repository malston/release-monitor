# Concourse Deployment Guide

This guide provides detailed instructions for deploying the GitHub Release Monitor to Concourse CI/CD pipelines with various configuration options.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Pipeline Options](#pipeline-options)
- [Basic Deployment](#basic-deployment)
- [Advanced Configuration](#advanced-configuration)
- [Download Feature Setup](#download-feature-setup)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Overview

The GitHub Release Monitor provides multiple Concourse pipeline configurations to suit different deployment scenarios:

1. **Standard Pipeline**: Full-featured with S3 backend
2. **Simple Pipeline**: Local state, no external dependencies
3. **Download Pipeline**: Includes asset download capabilities
4. **Simple Download Pipeline**: Downloads without S3 requirements

## Prerequisites

### Required

- Concourse CI instance (v5.0+)
- GitHub personal access token
- `fly` CLI tool installed and configured

### Optional

- AWS S3 bucket (for standard pipelines)
- AWS credentials with S3 access

## Pipeline Options

### 1. Standard Pipeline (pipeline.yml)

Best for production environments with S3 storage.

**Features:**
- S3-based state management
- Scheduled monitoring
- Release tarball downloads
- Multi-repository support

**Requirements:**
- S3 bucket for state storage
- AWS credentials

### 2. Simple Pipeline (pipeline-simple.yml)

Good for testing or environments without S3.

**Features:**
- Local state management
- Basic monitoring
- Simple configuration
- No external dependencies

### 3. S3-Compatible Pipeline (pipeline-s3-compatible.yml) ⭐ **RECOMMENDED**

Production-ready pipeline with MinIO and AWS S3 support.

**Features:**
- S3-compatible storage (MinIO, AWS S3, etc.)
- Advanced version tracking and downloads
- Force download utilities for testing
- Automatic cleanup and database management

## Basic Deployment

### Step 1: Clone the Repository

```bash
git clone https://github.com/malston/release-monitor.git
cd release-monitor
```

### Step 2: Configure Parameters

Create parameter files in the `params/` directory:

```bash
# Copy example parameters
cp params/global.yml.example params/global.yml
cp params/test.yml.example params/test.yml
```

Edit `params/global.yml`:

```yaml
# GitHub API access
github_token: ((github_token))  # Will be provided via Credhub/Vault

# Git repository access (if private)
# Note: For public repositories, you can use empty values or skip this entirely
# When using the Makefile targets, this will be passed as --var git_private_key="$(cat ~/.ssh/id_rsa)"
git_private_key: ((git_private_key))  # Will be provided via Credhub/Vault

# S3 credentials
s3_access_key_id: ((s3_access_key_id)) # Will be provided via Credhub/Vault
s3_secret_access_key: ((s3_secret_access_key)) # Will be provided via Credhub/Vault

# S3 bucket names
s3_monitor_bucket: "my-org-release-monitor"
s3_releases_bucket: "my-org-release-artifacts"

# Repository Configuration
release_monitor_git_uri: https://github.com/malston/release-monitor.git
release_monitor_branch: main

# Monitoring Configuration
monitor_interval: 1h  # Check every hour
```

Edit `params/test.yml`:

```yaml
# Environment-specific settings
environment: test

# S3 Configuration (if using S3)
s3_bucket: my-release-monitor-test
s3_region: us-west-2
aws_access_key_id: ((aws_access_key_id))
aws_secret_access_key: ((aws_secret_access_key))
```

### Step 3: Set Credentials

Using Credhub:

```bash
# Navigate to project directory
cd /path/to/release-monitor

# Validate pipeline configuration
./ci/validate.sh

# Deploy to test environment (public repos)
./ci/fly.sh set -t test -f test

# OR deploy with SSH key for private repositories
export GITHUB_TOKEN="your_github_token_here"
fly -t test set-pipeline \
  -p github-release-monitor \
  -c ci/pipeline.yml \
  -l params/global.yml \
  -l params/test.yml \
  --var git_private_key="$(cat ~/.ssh/id_ed25519)" \
  --var github_token="$GITHUB_TOKEN"

# Verify deployment
fly -t test pipelines
```

Using Vault:

```bash
vault write concourse/main/github_token value="ghp_xxxxxxxxxxxx"
vault write concourse/main/aws_access_key_id value="AKIAXXXXXXXX"
vault write concourse/main/aws_secret_access_key value="secret"
```

### Step 4: Deploy Pipeline

For simple pipeline (no S3):

```bash
fly -t dev set-pipeline \
  -p release-monitor \
  -c ci/pipeline-simple.yml \
  -l params/global.yml \
  -l params/test.yml
```

For standard pipeline (with S3):

```bash
fly -t dev set-pipeline \
  -p release-monitor \
  -c ci/pipeline.yml \
  -l params/global.yml \
  -l params/test.yml
```

### Step 5: Unpause Pipeline

```bash
fly -t dev unpause-pipeline -p release-monitor
```

## Advanced Configuration

### Custom Repository Configuration

Create a configuration repository with your monitoring settings:

`config-repo/monitor-config.yaml`:

```yaml
repositories:
  - owner: kubernetes
    repo: kubernetes
    include_prereleases: false
    
  - owner: istio
    repo: istio
    include_prereleases: false
    
  - owner: open-policy-agent
    repo: gatekeeper
    include_prereleases: true

settings:
  rate_limit_delay: 1.5
  max_releases_per_repo: 5
```

Update pipeline to use config repo:

```yaml
resources:
  - name: config-repo
    type: git
    source:
      uri: https://github.com/myorg/release-monitor-config.git
      branch: main
```

### Multi-Environment Setup

Deploy different pipelines for each environment:

```bash
# Development
fly -t dev set-pipeline -p release-monitor-dev \
  -c ci/pipeline-simple.yml \
  -l params/global.yml -l params/dev.yml

# Staging  
fly -t staging set-pipeline -p release-monitor-staging \
  -c ci/pipeline.yml \
  -l params/global.yml -l params/staging.yml

# Production
fly -t prod set-pipeline -p release-monitor-prod \
  -c ci/pipeline.yml \
  -l params/global.yml -l params/prod.yml
```

## Download Feature Setup

### Basic Download Configuration

Add download configuration to your `monitor-config.yaml`:

```yaml
download:
  enabled: true
  directory: ./downloads
  version_db: ./version_db.json
  asset_patterns:
    - "*.tar.gz"
    - "*.zip"
    - "!*-sources.zip"
  verify_checksums: true
  retry_attempts: 3
```

### Deploy S3-Compatible Pipeline (Recommended)

```bash
fly -t dev set-pipeline \
  -p release-monitor-minio \
  -c ci/pipeline-s3-compatible.yml \
  -l params/global-s3-compatible.yml \
  -l params/minio-local.yml \
  -v "github_token=${GITHUB_TOKEN}"
```

### Repository-Specific Downloads

Configure different download patterns per repository:

```yaml
download:
  enabled: true
  asset_patterns:
    - "*.tar.gz"
  repository_overrides:
    kubernetes/kubernetes:
      asset_patterns:
        - "kubernetes-client-*.tar.gz"
        - "kubernetes-server-*.tar.gz"
    istio/istio:
      asset_patterns:
        - "istio-*.linux-amd64.tar.gz"
    open-policy-agent/gatekeeper:
      asset_patterns:
        - "gatekeeper-*.linux-amd64.tar.gz"
```

### S3 Download Storage

Configure S3 backend for downloads:

```yaml
# In params file
downloads_s3_bucket: my-release-downloads
downloads_s3_prefix: github-releases/
version_db_s3_bucket: my-release-state
version_db_s3_prefix: version-db/
```

## Troubleshooting

### Common Issues

1. **Pipeline Validation Errors**

   ```bash
   # Validate pipeline locally
   fly validate-pipeline -c ci/pipeline.yml
   ```

2. **GitHub Rate Limiting**

   Add rate limit configuration:
   ```yaml
   settings:
     rate_limit_delay: 2.0  # Seconds between API calls
   ```

3. **S3 Access Issues**

   Test S3 access:
   ```bash
   aws s3 ls s3://my-bucket/ --region us-west-2
   ```

4. **Resource Not Found**

   Check resource definitions match exactly:
   ```bash
   fly -t dev check-resource -r release-monitor/release-monitor
   ```

### Debug Mode

Enable verbose logging in tasks:

```yaml
params:
  VERBOSE: "true"
  DEBUG: "true"
```

### Manual Task Execution

Test tasks locally:

```bash
fly -t dev execute \
  -c ci/tasks/check-releases/task.yml \
  -i release-monitor=. \
  -v github_token=ghp_xxxx
```

## Best Practices

### 1. Security

- Store tokens in Credhub/Vault, never in pipeline files
- Use least-privilege AWS IAM policies
- Rotate tokens regularly
- Use private S3 buckets

### 2. Performance

- Adjust `monitor_interval` based on needs
- Use `rate_limit_delay` to avoid GitHub limits
- Configure `max_releases_per_repo` appropriately
- Use asset patterns to limit downloads

### 3. Reliability

- Set up alerts for pipeline failures
- Monitor S3 storage usage
- Implement cleanup policies
- Use version pinning for stability

### 4. Organization

- Separate configuration from pipeline code
- Use meaningful pipeline groups
- Document custom configurations
- Version control everything

### Example Production Setup

```yaml
# params/prod.yml
environment: production
monitor_interval: 30m
max_retries: 5

# S3 Configuration
s3_bucket: prod-release-monitor
s3_lifecycle_days: 90

# Download Configuration  
download_enabled: true
verify_downloads: true
cleanup_old_versions: true
keep_versions: 10

# Alerting
slack_webhook: ((slack_webhook))
email_recipients: devops@company.com
```

### Monitoring Dashboard

Create a simple dashboard using Concourse's API:

```bash
# Get pipeline status
fly -t prod pipelines --json | jq '.[] | select(.name=="release-monitor")'

# Get recent builds
fly -t prod builds -j release-monitor/monitor-releases -c 10
```

## Storage Structure

### S3 Organization

**Monitor Bucket** (`s3://monitor-bucket/`):

```
release-monitor/
├── latest-releases.json          # Current monitor output
├── version_db.json              # Version tracking database
└── history/
    ├── 2024-01-15-releases.json
    └── 2024-01-16-releases.json
```

**Releases Bucket** (`s3://releases-bucket/`):

```
release-downloads/
├── kubernetes/
│   └── kubernetes/
│       ├── v1.29.0/
│       │   ├── kubernetes-client-linux-amd64.tar.gz
│       │   └── kubernetes-server-linux-amd64.tar.gz
│       └── v1.29.1/
├── istio/
│   └── istio/
│       └── 1.22.4/
│           └── istio-1.22.4-linux-amd64.tar.gz
└── open-policy-agent/
    └── gatekeeper/
        └── v3.18.2/
            └── gatekeeper-v3.18.2-linux-amd64.tar.gz
```

## Integration Examples

### Trigger Downstream Pipeline

```yaml
resources:
  - name: kubernetes-releases
    type: s3
    source:
      bucket: releases-bucket
      regexp: release-downloads/kubernetes/kubernetes/(.*)/.*

  - name: istio-releases
    type: s3
    source:
      bucket: releases-bucket
      regexp: release-downloads/istio/istio/(.*)/.*

  - name: gatekeeper-releases
    type: s3
    source:
      bucket: releases-bucket
      regexp: release-downloads/open-policy-agent/gatekeeper/(.*)/.*

jobs:
  - name: update-kubernetes
    plan:
      - get: kubernetes-releases
        trigger: true
      - task: deploy-kubernetes
        # ... deployment logic

  - name: update-service-mesh
    plan:
      - get: istio-releases
        trigger: true
      - task: deploy-istio
        # ... Istio deployment logic

  - name: update-policy-engine
    plan:
      - get: gatekeeper-releases
        trigger: true
      - task: deploy-gatekeeper
        # ... Gatekeeper deployment logic
```

### Slack Notifications

```yaml
resources:
  - name: slack-alert
    type: slack-notification
    source:
      url: ((slack_webhook))

jobs:
  - name: monitor-and-download
    on_success:
      put: slack-alert
      params:
        text: |
          ✅ New releases downloaded successfully
          Pipeline: $BUILD_PIPELINE_NAME
          Build: #$BUILD_NAME
```

## Next Steps

1. Review the [main documentation](README.md)
2. Check [download guide](DOWNLOAD_GUIDE.md) for download features
3. Customize for your repositories
4. Set up monitoring and alerts
5. Contribute improvements back!