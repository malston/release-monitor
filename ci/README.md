# Concourse CI Structure

This directory contains **3 streamlined Concourse pipelines** for the GitHub release monitor, each optimized for specific use cases.

## Pipeline Files

```text
ci/
├── pipeline-s3-compatible.yml       # S3-compatible pipeline (MinIO/AWS S3) ⭐ PRIMARY
├── pipeline-simple.yml              # Basic monitoring only (getting started) ⭐ STARTER  
├── pipeline.yml                     # Traditional AWS S3 pipeline ⭐ AWS-ONLY
├── fly.sh                           # Pipeline deployment script
├── validate.sh                      # Pipeline validation script  
├── validate-simple.sh              # Validation for simple pipelines
├── README.md                        # This file
└── tasks/
    ├── check-releases/
    │   ├── task.yml                 # Full monitoring task
    │   └── task.sh                  # Task execution script
    ├── check-releases-simple/
    │   ├── task.yml                 # Simplified monitoring task
    │   └── task.sh                  # Task execution script
    └── download-releases/
        ├── task.yml                 # Download task with S3 support
        └── task.sh                  # Task execution script
```

## Pipeline Comparison

| Pipeline | Use Case | Storage | Downloads | Complexity | Jobs | Status |
|----------|----------|---------|-----------|------------|------|--------|
| **pipeline-s3-compatible.yml** ⭐ | Production MinIO/AWS | S3-compatible | ✅ Advanced | Medium | 4 | **PRIMARY** |
| **pipeline-simple.yml** 🏁 | Getting started | None | ❌ | Low | 2 | **STARTER** |
| **pipeline.yml** 🏢 | AWS-only environments | AWS S3 | ✅ Basic | Medium | 2 | **AWS-ONLY** |

## Pipeline Details

### pipeline-s3-compatible.yml ⭐ **PRIMARY PIPELINE**

- **Purpose**: Full-featured production pipeline supporting both MinIO and AWS S3
- **Jobs**: `monitor-releases`, `download-new-releases`, `clear-version-database`, `force-download-repo`
- **Features**:
  - S3-compatible storage (MinIO, AWS S3, etc.)
  - Advanced version tracking and duplicate prevention
  - Automatic cleanup of old versions
  - Force download capability for testing
  - Database management utilities
- **Best for**: Most production environments, local development with MinIO
- **Deploy**: `make pipeline-set-test-minio`

### pipeline-simple.yml 🏁 **STARTER PIPELINE**

- **Purpose**: Basic monitoring without downloads or storage dependencies
- **Jobs**: `monitor-releases`, `check-repositories`
- **Features**:
  - GitHub API monitoring only
  - No storage dependencies
  - Easy setup and testing
  - JSON output for integration
- **Best for**: Getting started, testing, basic monitoring, CI/CD integration
- **Deploy**: `make pipeline-set-test-simple`

### pipeline.yml 🏢 **AWS-ONLY PIPELINE**

- **Purpose**: Traditional AWS S3 pipeline for pure AWS environments
- **Jobs**: `monitor-releases`, `download-new-releases`
- **Features**:
  - Native AWS S3 integration
  - Standard download and storage
  - AWS-optimized configuration
- **Best for**: Enterprise AWS-only environments, existing AWS infrastructure
- **Deploy**: `make pipeline-set-test`

## User Journey

```
🏁 Start Here          ⭐ Upgrade To           🏢 Alternative
pipeline-simple.yml → pipeline-s3-compatible.yml  OR  pipeline.yml
(Learn basics)         (Full production)           (AWS-only)
```

## Tasks

### check-releases

- **Purpose**: Full GitHub monitoring with S3 integration
- **Image**: `python:3.11-slim`
- **Used by**: pipeline.yml, pipeline-s3-compatible.yml

### check-releases-simple  

- **Purpose**: Basic GitHub monitoring without S3
- **Image**: `python:3.11-slim`
- **Used by**: pipeline-simple.yml

### download-releases

- **Purpose**: Advanced downloads with S3 version tracking
- **Image**: `python:3.11-slim`
- **Used by**: pipeline.yml, pipeline-s3-compatible.yml

## Quick Start

### For MinIO/S3-Compatible Storage (Recommended)

```bash
# Deploy S3-compatible pipeline
make pipeline-set-test-minio

# Force download for testing
make force-download REPO=etcd-io/etcd
```

### For Basic Monitoring Only  

```bash
# Deploy simple monitoring pipeline
make pipeline-set-test-simple
```

### For AWS S3 Only

```bash
# Deploy traditional S3 pipeline  
make pipeline-set-test
```

## Advanced Usage

```bash
# Validate pipelines
./ci/validate.sh
./ci/validate-simple.sh

# Manual deployment with fly
fly -t test set-pipeline -p name -c ci/pipeline-s3-compatible.yml -l params/global-s3-compatible.yml

# Force download any repository
fly -t test trigger-job -j pipeline-name/force-download-repo -v force_download_repo="istio/istio"
```

## Configuration

Pipeline parameters are in `../params/`:

- `global-s3-compatible.yml`: S3-compatible pipeline parameters ⭐
- `global.yml`: Traditional S3 pipeline parameters  
- `test.yml`: Test environment overrides
- `prod.yml`: Production environment overrides
- `credentials.yml`: Test or Production pipeline credentials
- `minio-local.yml`: Local MinIO configuration
- `minio-credentials.yml`: MinIO credentials (create from example)

## Pipeline Flows

### S3-Compatible Pipeline (Recommended)

```
Schedule → Monitor Releases → Download New Releases → Upload to S3
    ↓           ↓                      ↓                    ↓
Clear DB ← Force Download ←  Version Tracking ←  Automatic Cleanup
```

### Simple Pipeline  

```
Schedule → Monitor Releases → Output JSON (no downloads)
```

### Traditional S3 Pipeline

```
Schedule → Monitor Releases → Download → Upload to AWS S3
```
