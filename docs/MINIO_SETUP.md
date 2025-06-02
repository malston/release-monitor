# Minio Setup Guide for Release Monitor

This guide explains how to use Minio (S3-compatible object storage) with the GitHub Release Monitor's Concourse pipeline.

## Overview

Minio is an open-source, S3-compatible object storage server that can be self-hosted. It's perfect for:
- Local development and testing
- On-premises deployments
- Organizations that cannot use AWS S3
- Cost-conscious deployments

## Prerequisites

- Docker and Docker Compose installed
- Concourse CI environment (or use the included docker-compose setup)
- Basic understanding of S3 concepts

## Quick Start

### 1. Start Minio Server

```bash
# Start Minio using docker-compose
docker-compose up -d

# Verify Minio is running
docker-compose ps
```

This will:
- Start Minio server on port 9000 (API) and 9001 (Console)
- Create required buckets: `release-monitor-output` and `release-monitor-artifacts`
- Set up a dedicated user with appropriate permissions
- Enable versioning on the output bucket

### 2. Access Minio Console

Open your browser and navigate to: http://localhost:9001

Default credentials:
- Username: `minioadmin`
- Password: `minioadmin`

Release Monitor user credentials:
- Username: `release-monitor-user`
- Password: `release-monitor-pass`

### 3. Test Connectivity

```bash
# Run the test script
./scripts/test-minio.sh

# Or test manually with AWS CLI
aws s3 ls --endpoint-url http://localhost:9000 \
  --aws-access-key-id release-monitor-user \
  --aws-secret-access-key release-monitor-pass
```

## Pipeline Configuration

### 1. Update Pipeline Resources

The Concourse S3 resource supports custom endpoints. Update your pipeline to include Minio configuration:

```yaml
resources:
  - name: monitor-output
    type: s3
    source:
      endpoint: ((minio_endpoint))
      bucket: ((s3_bucket))
      region_name: ((s3_region))
      access_key_id: ((s3_access_key))
      secret_access_key: ((s3_secret_key))
      disable_ssl: ((minio_disable_ssl))
      skip_ssl_verification: ((minio_skip_ssl_verification))
      versioned_file: release-monitor/latest-releases.json
```

### 2. Parameter Configuration

Use the provided `params/minio-local.yml` file or create your own:

```yaml
# Minio endpoint
minio_endpoint: http://localhost:9000
minio_disable_ssl: true
minio_skip_ssl_verification: true

# Credentials
s3_access_key: release-monitor-user
s3_secret_key: release-monitor-pass

# Buckets
s3_bucket: release-monitor-output
s3_releases_bucket: release-monitor-artifacts

# Region (use us-east-1 for Minio)
s3_region: us-east-1
```

### 3. Deploy Pipeline with Minio

```bash
# Set credentials in Concourse
fly -t your-target set-pipeline \
  -p github-release-monitor \
  -c ci/pipeline.yml \
  -l params/global.yml \
  -l params/minio-local.yml \
  --var github_token="$GITHUB_TOKEN"
```

## Production Deployment

### 1. Secure Minio Setup

For production, use strong credentials and TLS:

```yaml
services:
  minio:
    image: minio/minio:latest
    environment:
      MINIO_ROOT_USER: your-secure-admin-user
      MINIO_ROOT_PASSWORD: your-secure-admin-password
    command: server /data --certs-dir /certs
    volumes:
      - minio-data:/data
      - ./certs:/certs
```

### 2. TLS Configuration

1. Generate or obtain TLS certificates
2. Place them in the certs directory:
   - `certs/public.crt`
   - `certs/private.key`

3. Update pipeline parameters:
```yaml
minio_endpoint: https://minio.yourdomain.com:9000
minio_disable_ssl: false
minio_skip_ssl_verification: false
```

### 3. High Availability

For HA deployments, use Minio in distributed mode:

```bash
# Example 4-node setup
minio server http://minio{1...4}.example.com/data{1...4}
```

## Python Integration

The release monitor's Python code works with Minio through boto3:

```python
import boto3
from botocore.client import Config

s3_client = boto3.client(
    's3',
    endpoint_url='http://localhost:9000',
    aws_access_key_id='release-monitor-user',
    aws_secret_access_key='release-monitor-pass',
    config=Config(signature_version='s3v4'),
    region_name='us-east-1'
)

# Use s3_client as normal
s3_client.list_buckets()
```

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Ensure Minio is running: `docker-compose ps`
   - Check endpoint URL includes protocol: `http://localhost:9000`

2. **Access Denied**
   - Verify credentials are correct
   - Check bucket policies and user permissions

3. **Signature Version Error**
   - Use `signature_version='s3v4'` in boto3

4. **SSL/TLS Issues**
   - For local development, use `minio_skip_ssl_verification: true`
   - For production, ensure certificates are valid

### Debug Commands

```bash
# Check Minio logs
docker-compose logs minio

# List buckets
aws s3 ls --endpoint-url http://localhost:9000

# Check bucket versioning
aws s3api get-bucket-versioning \
  --endpoint-url http://localhost:9000 \
  --bucket release-monitor-output
```

## Migration from AWS S3

To migrate from AWS S3 to Minio:

1. **Export data from S3:**
```bash
aws s3 sync s3://your-aws-bucket ./backup/
```

2. **Import to Minio:**
```bash
aws s3 sync ./backup/ s3://release-monitor-output \
  --endpoint-url http://localhost:9000
```

3. **Update pipeline parameters** to use Minio endpoint

## Best Practices

1. **Security**
   - Use strong passwords in production
   - Enable TLS for production deployments
   - Regularly update Minio to latest version
   - Use dedicated service accounts

2. **Backup**
   - Regular backups of Minio data directory
   - Test restore procedures
   - Consider replication for critical data

3. **Monitoring**
   - Monitor Minio metrics
   - Set up alerts for disk space
   - Track API performance

4. **Performance**
   - Use SSD storage for better performance
   - Configure appropriate memory limits
   - Consider distributed mode for high load

## Resources

- [Minio Documentation](https://docs.min.io/)
- [Minio GitHub Repository](https://github.com/minio/minio)
- [Concourse S3 Resource](https://github.com/concourse/s3-resource)
- [AWS CLI with Minio](https://docs.min.io/docs/aws-cli-with-minio.html)