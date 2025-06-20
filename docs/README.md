# Documentation Index

This directory contains comprehensive documentation for the GitHub Release Monitor project.

## Setup and Configuration

- **[Download Guide](DOWNLOAD_GUIDE.md)** - Detailed configuration for automatic release downloads
- **[MinIO Setup Guide](MINIO_SETUP.md)** - Setting up MinIO S3-compatible storage
- **[MinIO Credentials Setup](MINIO_CREDENTIALS_SETUP.md)** - Configuring MinIO authentication
- **[SSL Verification Guide](SSL_VERIFICATION_GUIDE.md)** - SSL configuration for corporate environments

## Deployment and Integration

- **[Concourse Deployment Guide](CONCOURSE_DEPLOYMENT.md)** - Complete Concourse CI/CD pipeline setup
- **[Pipeline Comparison](PIPELINE_COMPARISON.md)** - Comparison of different pipeline options
- **[Pipeline Flowchart](pipeline-flowchart.md)** - Visual overview of pipeline workflow
- **[Pipeline ASCII Flow](pipeline-ascii-flow.txt)** - Text-based pipeline diagram

## Troubleshooting and Fixes

- **[Wavefront Download Fix Guide](WAVEFRONT_DOWNLOAD_FIX.md)** - YAML file upload issues and verification
- **[Troubleshooting 401 Errors](TROUBLESHOOTING_401_ERROR.md)** - Authentication and authorization issues
- **[Source Code Downloads](SOURCE_CODE_DOWNLOADS.md)** - Handling repositories with source-only releases

## Quick Navigation

### Common Issues
- **YAML files not uploading?** → [Wavefront Download Fix Guide](WAVEFRONT_DOWNLOAD_FIX.md)
- **SSL certificate errors?** → [SSL Verification Guide](SSL_VERIFICATION_GUIDE.md)
- **401 Unauthorized errors?** → [Troubleshooting 401 Errors](TROUBLESHOOTING_401_ERROR.md)
- **MinIO setup problems?** → [MinIO Setup Guide](MINIO_SETUP.md)
- **Download not working?** → [Download Guide](DOWNLOAD_GUIDE.md)
- **Pipeline deployment issues?** → [Concourse Deployment Guide](CONCOURSE_DEPLOYMENT.md)

### By Use Case
- **First-time setup** → [Download Guide](DOWNLOAD_GUIDE.md) + [Concourse Deployment Guide](CONCOURSE_DEPLOYMENT.md)
- **Corporate environments** → [SSL Verification Guide](SSL_VERIFICATION_GUIDE.md) + [MinIO Setup Guide](MINIO_SETUP.md)
- **Pipeline optimization** → [Pipeline Comparison](PIPELINE_COMPARISON.md) + [Pipeline Flowchart](pipeline-flowchart.md)
- **Debugging issues** → [Wavefront Download Fix Guide](WAVEFRONT_DOWNLOAD_FIX.md) + [Troubleshooting 401 Errors](TROUBLESHOOTING_401_ERROR.md)

## Contributing to Documentation

When adding new documentation:
1. Place files in this `docs/` directory
2. Update this README.md index
3. Add references in the main project README.md troubleshooting section
4. Use clear, descriptive filenames with `.md` extension
5. Include comprehensive examples and troubleshooting steps