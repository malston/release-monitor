# Setting up S3 Credentials for Minio in Concourse

This guide explains how to configure S3 credentials for accessing Minio from Concourse pipelines.

## Overview

When using Minio with Concourse pipelines, you need to provide S3-compatible credentials. There are several methods depending on your environment and security requirements.

## Prerequisites

1. **Minio server running**: Start with `docker-compose up -d`
2. **Concourse target configured**: `fly -t test login`
3. **GitHub token available**: For repository access

## Quick Setup Script

Use the automated setup script:

```bash
./scripts/setup-minio-credentials.sh
```

This script provides options for all credential management methods below.

## Method 1: Credhub (Recommended for Production)

### Setup Credhub Credentials

```bash
# Login to Credhub
credhub login -s https://your-credhub-server -u username -p password

# Set Minio credentials
credhub set -n /concourse/main/s3_access_key -t value -v "release-monitor-user"
credhub set -n /concourse/main/s3_secret_key -t value -v "release-monitor-pass"
credhub set -n /concourse/main/s3_endpoint -t value -v "http://localhost:9000"
credhub set -n /concourse/main/s3_region -t value -v "us-east-1"

# Set bucket configuration
credhub set -n /concourse/main/s3_monitor_bucket -t value -v "release-monitor-output"
credhub set -n /concourse/main/s3_releases_bucket -t value -v "release-monitor-artifacts"

# Set S3-compatible options
credhub set -n /concourse/main/s3_disable_ssl -t value -v "true"
credhub set -n /concourse/main/s3_skip_ssl_verification -t value -v "true"
# credhub set -n /concourse/main/s3_use_v4 -t value -v "true"
```

### Deploy Pipeline with Credhub

```bash
export GITHUB_TOKEN="your_github_token"

fly -t test set-pipeline \
  -p github-release-monitor-minio \
  -c ci/pipeline-s3-compatible.yml \
  -l params/global-s3-compatible.yml \
  --var github_token="$GITHUB_TOKEN"
```

## Method 2: Vault

### Setup Vault Credentials

```bash
# Login to Vault
vault login

# Store credentials in Vault
vault kv put concourse/main \
  s3_access_key="release-monitor-user" \
  s3_secret_key="release-monitor-pass" \
  s3_endpoint="http://localhost:9000" \
  s3_region="us-east-1" \
  s3_monitor_bucket="release-monitor-output" \
  s3_releases_bucket="release-monitor-artifacts" \
  s3_disable_ssl="true" \
  # s3_use_v4="true" \
  s3_skip_ssl_verification="true"
```

### Deploy Pipeline with Vault

```bash
export GITHUB_TOKEN="your_github_token"

fly -t test set-pipeline \
  -p github-release-monitor-minio \
  -c ci/pipeline-s3-compatible.yml \
  -l params/global-s3-compatible.yml \
  --var github_token="$GITHUB_TOKEN"
```

## Method 3: Parameter Files (Development)

### Create Credentials File

```bash
# Copy and edit the credentials template
cp params/minio-credentials.yml.example params/minio-credentials.yml
```

Edit `params/minio-credentials.yml`:

```yaml
# Minio credentials (local development only)
s3_endpoint: http://localhost:9000
s3_access_key: release-monitor-user
s3_secret_key: release-monitor-pass
s3_disable_ssl: true
s3_skip_ssl_verification: true
# s3_use_v4: true
s3_region: us-east-1

# Bucket configuration
s3_monitor_bucket: release-monitor-output
s3_releases_bucket: release-monitor-artifacts

# Version database settings
use_s3_version_db: true
version_db_s3_bucket: release-monitor-output
version_db_s3_prefix: version-db/
```

### Deploy Pipeline with Parameter File

```bash
export GITHUB_TOKEN="your_github_token"

fly -t test set-pipeline \
  -p github-release-monitor-minio \
  -c ci/pipeline-s3-compatible.yml \
  -l params/global-s3-compatible.yml \
  -l params/minio-credentials.yml \
  --var github_token="$GITHUB_TOKEN"
```

**⚠️ Security Warning**: Never commit credential files to version control!

## Method 4: Command Line Variables (Quick Testing)

### Direct Variable Passing

```bash
export GITHUB_TOKEN="your_github_token"

fly -t test set-pipeline \
  -p github-release-monitor-minio \
  -c ci/pipeline-s3-compatible.yml \
  -l params/global-s3-compatible.yml \
  --var s3_access_key="release-monitor-user" \
  --var s3_secret_key="release-monitor-pass" \
  --var s3_endpoint="http://localhost:9000" \
  --var s3_region="us-east-1" \
  --var s3_disable_ssl="true" \
  --var s3_skip_ssl_verification="true" \
  # --var s3_use_v4="true" \
  --var s3_monitor_bucket="release-monitor-output" \
  --var s3_releases_bucket="release-monitor-artifacts" \
  --var github_token="$GITHUB_TOKEN"
```

## Method 5: Using Makefile Targets

### Add Makefile Target for Minio

Add this to your Makefile:

```makefile
.PHONY: pipeline-set-test-minio
pipeline-set-test-minio: ## Deploy pipeline with Minio support (local development)
	@echo "$(GREEN)Deploying pipeline with Minio support...$(NC)"
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "$(RED)Error: GITHUB_TOKEN environment variable not set$(NC)"; \
		echo "$(YELLOW)Please set: export GITHUB_TOKEN=\"your_github_token\"$(NC)"; \
		exit 1; \
	fi
	@if [ ! -f "params/minio-credentials.yml" ]; then \
		echo "$(RED)Error: params/minio-credentials.yml not found$(NC)"; \
		echo "$(YELLOW)Copy from: cp params/minio-credentials.yml.example params/minio-credentials.yml$(NC)"; \
		exit 1; \
	fi
	@fly -t test set-pipeline \
		-p github-release-monitor-minio \
		-c ci/pipeline-s3-compatible.yml \
		-l params/global-s3-compatible.yml \
		-l params/minio-credentials.yml \
		--var github_token="$$GITHUB_TOKEN" \
		--non-interactive
```

### Use Makefile Target

```bash
export GITHUB_TOKEN="your_github_token"
make pipeline-set-test-minio
```

## Credential Security Best Practices

### For Development
- Use parameter files (method 3) with proper `.gitignore`
- Use command line variables (method 4) for quick testing
- Never commit credentials to version control

### For Production
- Use Credhub (method 1) or Vault (method 2)
- Rotate credentials regularly
- Use least-privilege access policies
- Monitor credential usage

### Access Control

Create dedicated Minio users with minimal permissions:

```bash
# Using Minio client (mc)
mc admin user add local pipeline-user secure-password

# Create policy for pipeline access
cat > pipeline-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::release-monitor-output/*",
        "arn:aws:s3:::release-monitor-output",
        "arn:aws:s3:::release-monitor-artifacts/*",
        "arn:aws:s3:::release-monitor-artifacts"
      ]
    }
  ]
}
EOF

mc admin policy create local pipeline-policy pipeline-policy.json
mc admin policy attach local pipeline-policy --user pipeline-user
```

## Testing Credentials

### Test Minio Connectivity

```bash
# Test with the provided script
./scripts/test-minio.sh

# Or test manually
aws s3 ls --endpoint-url http://localhost:9000 \
  --aws-access-key-id release-monitor-user \
  --aws-secret-access-key release-monitor-pass
```

### Test Pipeline Access

```bash
# Check resource accessibility
fly -t test check-resource -r github-release-monitor-minio/monitor-output

# Watch pipeline execution
fly -t test watch -j github-release-monitor-minio/monitor-releases
```

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Ensure Minio is running: `docker-compose ps`
   - Check endpoint URL: `http://localhost:9000`

2. **Access Denied**
   - Verify credentials are correct
   - Check bucket permissions
   - Ensure buckets exist

3. **SSL/TLS Errors**
   - For local Minio: set `s3_disable_ssl: true`
   - For HTTPS Minio: ensure valid certificates

4. **Region Errors**
   - Minio doesn't use regions, but set to `us-east-1`
   <!-- - Ensure `s3_use_v4: true` for signature compatibility -->

### Debug Commands

```bash
# Check Concourse variables
fly -t test get-pipeline -p github-release-monitor-minio

# Test S3 operations
aws s3 cp test.txt s3://release-monitor-output/ \
  --endpoint-url http://localhost:9000

# View pipeline logs
fly -t test builds -j github-release-monitor-minio/monitor-releases
```

## Production Deployment

### Network Configuration

For production Minio deployment:

```yaml
# Update endpoint in credentials
s3_endpoint: https://minio.yourdomain.com
s3_disable_ssl: false
s3_skip_ssl_verification: false
```

### High Availability

Use distributed Minio setup:

```bash
# Example 4-node cluster
minio server http://minio{1...4}.example.com/data{1...4}
```

### Monitoring

Monitor Minio metrics and Concourse pipeline health:

- Minio Console: http://localhost:9001
- Concourse UI: Monitor pipeline execution
- Log aggregation: Collect Minio and Concourse logs

## Next Steps

1. Choose appropriate credential method for your environment
2. Configure credentials using one of the methods above
3. Test connectivity with `./scripts/test-minio.sh`
4. Deploy pipeline with Minio support
5. Monitor pipeline execution and Minio storage
