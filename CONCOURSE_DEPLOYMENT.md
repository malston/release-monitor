# Concourse Pipeline Deployment Guide

This guide covers deploying the GitHub Release Monitor with download functionality to Concourse CI/CD.

## Overview

The pipeline consists of three main jobs:

1. **monitor-releases**: Check repositories for new releases
2. **download-new-releases**: Download assets from new releases  
3. **cleanup-old-releases**: Clean up old downloads periodically

## Prerequisites

### Required Resources

- **Concourse CI**: Version 6.0+ recommended
- **S3 Storage**: Two buckets for monitor data and release artifacts
- **GitHub Token**: Personal access token with repository read access

### Required Concourse Secrets

Store these secrets in your Concourse credential manager:

```yaml
# GitHub API access
github_api_token: "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Git repository access (if private)
lab_git_private_key: |
  -----BEGIN OPENSSH PRIVATE KEY-----
  ...
  -----END OPENSSH PRIVATE KEY-----

prod_git_private_key: |
  -----BEGIN OPENSSH PRIVATE KEY-----
  ...
  -----END OPENSSH PRIVATE KEY-----

# S3 credentials
s3_access_key_id: "AKIAIOSFODNN7EXAMPLE"
s3_secret_access_key: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

# S3 bucket names
s3_monitor_bucket: "my-org-release-monitor"
s3_releases_bucket: "my-org-release-artifacts"
```

## Deployment Steps

### 1. Configure Parameters

Edit the parameter files in `params/` directory:

**Global Configuration (`params/global.yml`)**:
```yaml
# Update repository URI
git_repo_uri: git@github.com:your-org/release-monitor.git

# Configure asset patterns
download_asset_patterns: '["*.tar.gz", "*.zip", "!*-sources.zip"]'

# Set repository-specific overrides
download_repository_overrides: |
  {
    "kubernetes/kubernetes": {
      "asset_patterns": ["kubernetes-client-*.tar.gz", "kubernetes-server-*.tar.gz"]
    }
  }
```

**Environment-Specific Configuration**:
- `params/lab.yml`: Development/testing settings
- `params/prod.yml`: Production settings

### 2. Deploy to Lab Environment

```bash
# Navigate to project directory
cd /path/to/release-monitor

# Validate pipeline configuration
./ci/validate.sh

# Deploy to lab environment
./ci/fly.sh set -t lab -f lab

# Verify deployment
fly -t lab pipelines
```

### 3. Test in Lab

```bash
# Trigger the pipeline manually
fly -t lab trigger-job -j github-release-monitor/monitor-releases

# Monitor job execution
fly -t lab watch -j github-release-monitor/monitor-releases

# Check download job
fly -t lab watch -j github-release-monitor/download-new-releases
```

### 4. Deploy to Production

```bash
# Deploy to production environment
./ci/fly.sh set -t prod -f prod

# Unpause the pipeline
fly -t prod unpause-pipeline -p github-release-monitor
```

## Pipeline Configuration

### Job Flow

```mermaid
graph TD
    A[Schedule Trigger] --> B[monitor-releases]
    B --> C[download-new-releases]
    C --> D[Update S3 Storage]
    E[Schedule Trigger] --> F[cleanup-old-releases]
```

### Resource Mappings

| Resource | Purpose | Example Location |
|----------|---------|------------------|
| `monitor-output` | Release monitoring results | `s3://monitor-bucket/release-monitor/latest-releases.json` |
| `release-storage` | Downloaded release artifacts | `s3://releases-bucket/release-downloads/` |
| `version-db-storage` | Version tracking database | `s3://monitor-bucket/release-monitor/version_db.json` |

### Task Parameters

#### Download Task Parameters

| Parameter | Description | Default | Example |
|-----------|-------------|---------|---------|
| `GITHUB_TOKEN` | GitHub API token | Required | `((github_api_token))` |
| `ASSET_PATTERNS` | File patterns to download | `["*.tar.gz", "*.zip"]` | `["*.tar.gz", "!*-sources.zip"]` |
| `INCLUDE_PRERELEASES` | Include pre-release versions | `false` | `true` |
| `VERIFY_DOWNLOADS` | Verify file checksums | `true` | `false` |
| `KEEP_VERSIONS` | Number of versions to retain | `5` | `10` |

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
├── kubernetes_kubernetes/
│   ├── v1.29.0/
│   │   ├── kubernetes-client-linux-amd64.tar.gz
│   │   ├── kubernetes-client-linux-amd64.tar.gz.sha256
│   │   └── download_metadata.json
│   └── v1.29.1/
├── prometheus_prometheus/
└── download_status.json         # Overall download status
```

## Monitoring and Troubleshooting

### Job Monitoring

**Check Pipeline Status**:
```bash
fly -t prod pipelines
fly -t prod jobs -p github-release-monitor
```

**View Job Logs**:
```bash
# Monitor releases job
fly -t prod watch -j github-release-monitor/monitor-releases

# Download job
fly -t prod watch -j github-release-monitor/download-new-releases

# Get build history
fly -t prod builds -j github-release-monitor/download-new-releases
```

### Common Issues

#### 1. Authentication Failures

**Problem**: `403 Forbidden` errors from GitHub API
**Solution**: 
- Verify `GITHUB_TOKEN` is valid
- Check token permissions (needs repository read access)
- Rotate token if expired

#### 2. S3 Access Issues

**Problem**: S3 upload/download failures
**Solution**:
- Verify S3 credentials are correct
- Check bucket policies allow read/write access
- Ensure buckets exist in specified regions

#### 3. Download Failures

**Problem**: Asset downloads timing out or failing
**Solution**:
- Increase `DOWNLOAD_TIMEOUT` parameter
- Check network connectivity from Concourse workers
- Review asset patterns for correctness

#### 4. Version Database Corruption

**Problem**: Version comparison errors
**Solution**:
```bash
# Reset version database
fly -t prod execute --config ci/tasks/reset-version-db.yml
```

### Performance Monitoring

**Check Download Metrics**:
```bash
# Download the status file
aws s3 cp s3://releases-bucket/download_status.json status.json
jq . status.json
```

**Monitor Storage Usage**:
```bash
# Check bucket sizes
aws s3 ls s3://releases-bucket/release-downloads/ --recursive --summarize
```

## Scaling and Optimization

### Performance Tuning

1. **Parallel Downloads**: Configure worker count for concurrent downloads
2. **Asset Filtering**: Use specific patterns to reduce download volume
3. **Cleanup Strategy**: Adjust retention policies based on usage

### Resource Scaling

```yaml
# In pipeline.yml - increase worker resources
download-releases:
  task: download-releases
  config:
    limits:
      cpu: 2
      memory: 4GB
```

### Regional Deployment

Deploy to multiple regions for redundancy:

```bash
# Deploy to US regions
./ci/fly.sh set -t prod-us-west -f prod-us-west
./ci/fly.sh set -t prod-us-east -f prod-us-east

# Deploy to EU regions  
./ci/fly.sh set -t prod-eu-west -f prod-eu-west
```

## Security Considerations

### Access Control

1. **Least Privilege**: GitHub tokens with minimal required permissions
2. **Bucket Policies**: Restrict S3 access to Concourse workers only
3. **Network Security**: Use VPC endpoints for S3 access when possible

### Secret Management

```yaml
# Use Concourse credential management
credentials:
  github_api_token:
    type: vault
    path: /concourse/main/github_api_token
  
  s3_access_key_id:
    type: credhub
    name: /concourse/s3_access_key_id
```

### Audit and Compliance

- Monitor pipeline execution logs
- Track downloaded assets and versions
- Implement retention policies for compliance
- Regular security reviews of credentials

## Maintenance

### Regular Tasks

1. **Weekly**: Review failed downloads and pipeline health
2. **Monthly**: Update GitHub tokens before expiration
3. **Quarterly**: Review and update repository configurations
4. **Annually**: Security audit of credentials and access patterns

### Backup Strategy

```bash
# Backup version database
aws s3 sync s3://monitor-bucket/release-monitor/ ./backups/

# Backup critical releases
aws s3 sync s3://releases-bucket/release-downloads/ ./release-backups/
```

### Updates and Upgrades

```bash
# Update pipeline with new version
git pull origin main
./ci/fly.sh set -t prod -f prod

# Test in lab first
./ci/fly.sh set -t lab -f lab
```

## Integration Examples

### Downstream Pipelines

**Trigger on New Kubernetes Release**:
```yaml
# In dependent pipeline
resources:
  - name: kubernetes-releases
    type: s3
    source:
      bucket: releases-bucket
      regexp: release-downloads/kubernetes_kubernetes/(.*)/.*

jobs:
  - name: update-kubernetes
    plan:
      - get: kubernetes-releases
        trigger: true
      - task: update-cluster
        # ... update logic
```

**Notification Integration**:

*Slack Notification:*
```yaml
# Add notification on download completion
- put: slack-notification
  params:
    text: |
      New releases downloaded:
      $BUILD_PIPELINE_NAME/$BUILD_JOB_NAME #$BUILD_NAME
```

*Microsoft Teams Notification:*
```yaml
# Add Teams notification on download completion
- put: teams-notification
  params:
    webhook_url: ((teams_webhook_url))
    message: |
      {
        "type": "message",
        "attachments": [{
          "contentType": "application/vnd.microsoft.card.adaptive",
          "content": {
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [{
              "type": "TextBlock",
              "text": "🚀 New Releases Downloaded",
              "size": "Large",
              "weight": "Bolder"
            }, {
              "type": "FactSet",
              "facts": [{
                "title": "Pipeline:",
                "value": "$BUILD_PIPELINE_NAME"
              }, {
                "title": "Job:",
                "value": "$BUILD_JOB_NAME"
              }, {
                "title": "Build:",
                "value": "#$BUILD_NAME"
              }]
            }],
            "actions": [{
              "type": "Action.OpenUrl",
              "title": "View Build",
              "url": "$ATC_EXTERNAL_URL/teams/$BUILD_TEAM_NAME/pipelines/$BUILD_PIPELINE_NAME/jobs/$BUILD_JOB_NAME/builds/$BUILD_NAME"
            }]
          }
        }]
      }
```

This completes the Concourse deployment guide for the GitHub Release Monitor with download functionality.