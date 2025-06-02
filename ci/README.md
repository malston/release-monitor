# Concourse CI Structure

This directory contains multiple Concourse CI/CD pipelines for the GitHub release monitor, each designed for different use cases and environments.

## Pipeline Files

```text
ci/
├── pipeline.yml                      # Full AWS S3 pipeline with downloads
├── pipeline-s3-compatible.yml       # S3-compatible pipeline (MinIO/AWS S3) ⭐ RECOMMENDED
├── pipeline-simple.yml              # Basic monitoring only (no downloads, no S3)
├── pipeline-with-downloads.yml      # Complex multi-job download pipeline  
├── pipeline-downloads-simple.yml    # Simple local downloads (no S3)
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

| Pipeline | Use Case | Storage | Downloads | Complexity | Jobs |
|----------|----------|---------|-----------|------------|------|
| **pipeline-s3-compatible.yml** ⭐ | Production MinIO/AWS | S3-compatible | ✅ Advanced | Medium | 4 |
| **pipeline.yml** | Production AWS only | AWS S3 | ✅ Basic | Medium | 2 |
| **pipeline-simple.yml** | Basic monitoring | None | ❌ | Low | 2 |
| **pipeline-with-downloads.yml** | Complex workflows | S3 | ✅ Advanced | High | 4 |
| **pipeline-downloads-simple.yml** | Local development | Local files | ✅ Basic | Low | 2 |

### pipeline-s3-compatible.yml ⭐ **RECOMMENDED**
- **Purpose**: Production-ready pipeline with MinIO and AWS S3 support
- **Jobs**: `monitor-releases`, `download-new-releases`, `clear-version-database`, `force-download-repo`
- **Features**: S3-compatible storage, version tracking, forced downloads, database management
- **Best for**: Production environments with MinIO or AWS S3

### pipeline.yml 
- **Purpose**: Traditional AWS S3 pipeline  
- **Jobs**: `monitor-releases`, `download-new-releases`
- **Features**: AWS S3 storage, basic downloads, cleanup
- **Best for**: AWS-only environments

### pipeline-simple.yml
- **Purpose**: Basic monitoring without downloads or storage
- **Jobs**: `monitor-releases`, `check-repositories` 
- **Features**: GitHub monitoring only, no downloads, no S3
- **Best for**: Testing, basic monitoring, getting started

### pipeline-with-downloads.yml
- **Purpose**: Complex multi-job workflow with advanced features
- **Jobs**: `monitor-and-download`, `download-specific-release`, `monitoring`, `manual`
- **Features**: Complex workflows, manual triggers, advanced download options
- **Best for**: Advanced users needing complex workflows

### pipeline-downloads-simple.yml
- **Purpose**: Simple local downloads without S3
- **Jobs**: `monitor-downloads`, `download-repository`
- **Features**: Local file storage, basic downloads
- **Best for**: Local development, simple setups

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
- **Image**: `python:3.9-slim` 
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
