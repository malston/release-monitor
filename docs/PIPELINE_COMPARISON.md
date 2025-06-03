# Pipeline Comparison Guide

This repository includes three different Concourse pipeline configurations, each designed for specific use cases:

## 1. pipeline.yml (AWS S3 - Full Featured)

**Purpose**: Production-ready pipeline with full AWS S3 integration for storing releases and downloading assets.

**Key Features**:
- ✅ Monitors GitHub repositories for new releases
- ✅ Stores release information in AWS S3
- ✅ Downloads release assets to S3 bucket
- ✅ Maintains version history
- ✅ Supports cleanup of old releases

**Requirements**:
- AWS S3 buckets (2 buckets: one for metadata, one for downloads)
- AWS credentials with S3 read/write access
- GitHub token

**Use When**:
- Running in production with AWS infrastructure
- Need to download and store release assets
- Want full tracking and history of releases

**Resources Used**:
```yaml
- monitor-output (S3)     # Stores release metadata
- release-storage (S3)    # Stores downloaded assets
```

## 2. pipeline-simple.yml (No S3 - Starter)

**Purpose**: Simplified pipeline for testing or environments without S3 access.

**Key Features**:
- ✅ Monitors GitHub repositories for new releases
- ✅ Displays results in Concourse UI logs
- ❌ No persistent storage
- ❌ No asset downloads
- ❌ No version history

**Requirements**:
- GitHub token only
- No S3 or external storage needed

**Use When**:
- Getting started with the release monitor
- Testing pipeline configuration
- Running in environments without S3 access
- Only need notifications (no downloads)

**Example Output**:
```
=== GitHub Release Monitor Results ===
New releases found:
  - kubernetes/kubernetes: v1.29.0
  - prometheus/prometheus: v2.48.0
```

## 3. pipeline-s3-compatible.yml (MinIO/S3-Compatible - Flexible)

**Purpose**: Supports both AWS S3 and S3-compatible storage (MinIO, Ceph, etc.).

**Key Features**:
- ✅ All features of pipeline.yml
- ✅ Works with MinIO, Ceph, or other S3-compatible storage
- ✅ Configurable endpoint URL
- ✅ SSL verification options
- ✅ Ideal for on-premises deployments

**Requirements**:
- S3-compatible storage (MinIO, Ceph, etc.)
- S3-compatible credentials
- GitHub token

**Use When**:
- Running on-premises with MinIO
- Using alternative S3-compatible storage
- Need full features without AWS dependency

**Additional Configuration**:
```yaml
s3_endpoint: http://minio.local:9000  # Custom endpoint
s3_skip_ssl_verification: true         # For self-signed certs
```

## Quick Decision Guide

| Need | Recommended Pipeline |
|------|---------------------|
| Just testing the monitor | pipeline-simple.yml |
| Production with AWS | pipeline.yml |
| On-premises with MinIO | pipeline-s3-compatible.yml |
| No storage infrastructure | pipeline-simple.yml |
| Need to download releases | pipeline.yml or pipeline-s3-compatible.yml |
| Corporate environment | pipeline-s3-compatible.yml (with proxy support) |

## Feature Comparison

| Feature | pipeline.yml | pipeline-simple.yml | pipeline-s3-compatible.yml |
|---------|--------------|--------------------|-----------------------------|
| Monitor releases | ✅ | ✅ | ✅ |
| Store metadata | ✅ AWS S3 | ❌ Logs only | ✅ S3-compatible |
| Download assets | ✅ | ❌ | ✅ |
| Version tracking | ✅ | ❌ | ✅ |
| Cleanup old versions | ✅ | ❌ | ✅ |
| Works offline | ❌ | ✅ | ✅ (with local MinIO) |
| Complexity | Medium | Low | Medium |

## Migration Path

1. **Start with**: `pipeline-simple.yml` to test configuration
2. **Move to**: `pipeline.yml` for AWS production
3. **Or use**: `pipeline-s3-compatible.yml` for on-premises

## Example Commands

```bash
# Deploy simple pipeline (no S3)
fly -t dev set-pipeline \
  -p github-monitor-simple \
  -c ci/pipeline-simple.yml \
  -v github_token=$GITHUB_TOKEN

# Deploy AWS S3 pipeline
fly -t prod set-pipeline \
  -p github-monitor \
  -c ci/pipeline.yml \
  -l params/prod.yml

# Deploy MinIO pipeline
fly -t dev set-pipeline \
  -p github-monitor-minio \
  -c ci/pipeline-s3-compatible.yml \
  -l params/minio-local.yml
```
