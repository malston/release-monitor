# JFrog Artifactory Integration Guide

This guide explains how to configure and use the GitHub Release Monitor with JFrog Artifactory for storing release artifacts and version database.

## Overview

The JFrog Artifactory integration provides:

- **Artifact Storage**: Downloaded release files are stored in Artifactory repositories
- **Version Database**: Release version tracking stored in Artifactory as JSON artifacts
- **Enterprise Integration**: Seamless integration with existing JFrog Artifactory infrastructure
- **Authentication**: Support for API keys and username/password authentication
- **SSL Configuration**: Configurable SSL verification for self-signed certificates

## Prerequisites

- JFrog Artifactory instance (Cloud, Pro, or Enterprise)
- Generic repository in Artifactory for storing release artifacts
- Artifactory credentials (API key recommended, or username/password)
- Python `requests` library

## Authentication Methods

### Option 1: API Key (Recommended)

API keys provide better security and can be scoped to specific permissions.

```bash
export ARTIFACTORY_API_KEY="your-api-key-here"
```

### Option 2: Username/Password

```bash
export ARTIFACTORY_USERNAME="your-username"
export ARTIFACTORY_PASSWORD="your-password"
```

## Environment Variables

### Required Variables

```bash
# Artifactory endpoint (without repository path)
export ARTIFACTORY_URL="https://your-company.jfrog.io/artifactory"

# Repository name for storing artifacts
export ARTIFACTORY_REPOSITORY="generic-releases"

# Authentication (use either API key OR username/password)
export ARTIFACTORY_API_KEY="your-api-key"
# OR
export ARTIFACTORY_USERNAME="your-username"
export ARTIFACTORY_PASSWORD="your-password"
```

### Optional Variables

```bash
# Skip SSL verification for self-signed certificates (default: false)
export ARTIFACTORY_SKIP_SSL_VERIFICATION="true"
```

## Configuration

### Pipeline Configuration

Use the Artifactory-specific pipeline configuration:

```bash
# Set pipeline using Artifactory parameters
fly -t your-target set-pipeline \
  -p release-monitor-artifactory \
  -c ci/pipeline-artifactory.yml \
  -l params/global-artifactory.yml
```

### Parameter File Setup

Copy and customize the Artifactory parameter file:

```bash
cp params/global-artifactory.yml params/your-environment-artifactory.yml
```

Edit the parameter file with your Artifactory details:

```yaml
# JFrog Artifactory configuration
artifactory_url: https://your-company.jfrog.io/artifactory
artifactory_repository: generic-releases

# Authentication (set in Concourse secrets)
artifactory_api_key: ((artifactory_api_key))
# OR
artifactory_username: ((artifactory_username))
artifactory_password: ((artifactory_password))

# SSL configuration
artifactory_skip_ssl_verification: false
```

### Application Configuration

For standalone usage, configure the download script with Artifactory settings:

```yaml
# config.yml
download:
  artifactory_storage:
    enabled: true
    base_url: "https://your-company.jfrog.io/artifactory"
    repository: "generic-releases"
    path_prefix: "release-monitor/"
    verify_ssl: true
    # Credentials will be read from environment variables
```

## Repository Structure

The integration creates the following structure in your Artifactory repository:

```sh
/your-artifactory-repository/
├── release-monitor/
│   ├── version_db.json                     # Version database
│   ├── latest-releases.json                # Latest releases metadata
│   └── release-downloads/                  # Downloaded release artifacts
│       ├── kubernetes/
│       │   ├── kubernetes-v1.28.0-linux-amd64.tar.gz
│       │   └── kubernetes-v1.28.1-linux-amd64.tar.gz
│       ├── prometheus/
│       │   ├── prometheus-2.45.0.linux-amd64.tar.gz
│       │   └── prometheus-2.46.0.linux-amd64.tar.gz
│       └── etcd-io/
│           └── etcd-v3.5.9-linux-amd64.tar.gz
```

## Usage Examples

### Standalone Script Usage

```bash
# Set environment variables
export ARTIFACTORY_URL="https://your-company.jfrog.io/artifactory"
export ARTIFACTORY_REPOSITORY="generic-local"
export ARTIFACTORY_API_KEY="your-api-key"
export GITHUB_TOKEN="your-github-token"

# Run monitor with Artifactory backend
python github_monitor.py

# Download releases
python download_releases.py

# Upload to Artifactory
python scripts/upload-to-artifactory.py
```

### Pipeline Usage

```bash
# Deploy pipeline
fly -t your-target set-pipeline \
  -p release-monitor-artifactory \
  -c ci/pipeline-artifactory.yml \
  -l params/global-artifactory.yml

# Unpause pipeline
fly -t your-target unpause-pipeline -p release-monitor-artifactory
```

## Concourse Secrets Setup

Store sensitive Artifactory credentials as Concourse secrets:

### Using Concourse Vault Integration

```bash
# Store API key
vault kv put concourse/main/release-monitor-artifactory \
  artifactory_api_key="your-api-key"

# Or store username/password
vault kv put concourse/main/release-monitor-artifactory \
  artifactory_username="your-username" \
  artifactory_password="your-password"
```

### Using Concourse CredHub Integration

```bash
# Store API key
credhub set -n /concourse/main/release-monitor-artifactory/artifactory_api_key \
  -t value -v "your-api-key"

# Or store username/password
credhub set -n /concourse/main/release-monitor-artifactory/artifactory_username \
  -t value -v "your-username"
credhub set -n /concourse/main/release-monitor-artifactory/artifactory_password \
  -t password -v "your-password"
```

## Testing the Integration

### Test Artifactory Connection

```python
#!/usr/bin/env python3
import os
from github_version_artifactory import ArtifactoryVersionDatabase

# Test connection
db = ArtifactoryVersionDatabase(
    base_url=os.environ['ARTIFACTORY_URL'],
    repository=os.environ['ARTIFACTORY_REPOSITORY']
)

try:
    # Test loading (will create empty database if not exists)
    data = db.load_versions()
    print("✅ Successfully connected to Artifactory")
    print(f"Version database contains {len(data.get('repositories', {}))} repositories")
except Exception as e:
    print(f"❌ Failed to connect to Artifactory: {e}")
```

### Test Upload Script

```bash
# Create test file
mkdir -p /tmp/downloads/test
echo "test content" > /tmp/downloads/test/test-file.tar.gz

# Test upload
python scripts/upload-to-artifactory.py
```

### Manual Pipeline Jobs

The Artifactory pipeline includes utility jobs for testing:

```bash
# Check version database contents
fly -t your-target trigger-job -j release-monitor-artifactory/check-version-database -w

# Reset version database (forces re-download of all releases)
fly -t your-target trigger-job -j release-monitor-artifactory/reset-version-database -w
```

## Troubleshooting

### Common Issues

#### 1. Authentication Errors (401 Unauthorized)

**Problem**: HTTP 401 errors when accessing Artifactory

**Solutions**:

- Verify API key or username/password are correct
- Check that credentials have proper permissions for the repository
- Ensure the API key hasn't expired

```bash
# Test credentials manually
curl -H "X-JFrog-Art-Api: your-api-key" \
  "https://your-company.jfrog.io/artifactory/api/repositories"
```

#### 2. SSL Certificate Issues

**Problem**: SSL verification failures with self-signed certificates

**Solutions**:

- Set `ARTIFACTORY_SKIP_SSL_VERIFICATION=true` for testing
- For production, add your CA certificate to the system trust store
- Use proper SSL certificates

#### 3. Repository Permission Issues (403 Forbidden)

**Problem**: HTTP 403 errors when uploading or downloading

**Solutions**:

- Verify the user/API key has deploy permissions on the repository
- Check repository exists and is accessible
- Ensure repository is of type "Generic"

#### 4. Version Database Not Found

**Problem**: Pipeline fails to load version database

**Solutions**:

- The database is created automatically on first run
- Check Artifactory repository permissions
- Verify repository name and path prefix configuration

### Debug Mode

Enable debug logging for troubleshooting:

```bash
export LOG_LEVEL="DEBUG"
python download_releases.py
```

### Manual Version Database Operations

```python
# Clear version database
from github_version_artifactory import ArtifactoryVersionDatabase
import os

db = ArtifactoryVersionDatabase(
    base_url=os.environ['ARTIFACTORY_URL'],
    repository=os.environ['ARTIFACTORY_REPOSITORY']
)

# Reset database
empty_data = {'repositories': {}, 'metadata': {'version': '2.0'}}
db.save_versions(empty_data)
```

## Performance Considerations

### Caching

- The Artifactory integration uses ETags for efficient caching
- Version database is cached locally during script execution
- Minimize API calls through smart caching

### Large Files

- Artifactory handles large release files efficiently
- Files are uploaded with checksums (SHA1 and MD5)
- Consider repository storage quotas for large numbers of releases

### Network

- Use Artifactory instances geographically close to your Concourse workers
- Consider proxy settings if running behind corporate firewalls
- Monitor network bandwidth for large file uploads

## Migration from S3

To migrate from S3 to Artifactory:

1. Export existing version database from S3:

   ```python
   from github_version_s3 import S3VersionDatabase
   s3_db = S3VersionDatabase('your-s3-bucket')
   data = s3_db.load_versions()
   ```

2. Import to Artifactory:

   ```python
   from github_version_artifactory import ArtifactoryVersionDatabase
   art_db = ArtifactoryVersionDatabase('https://artifactory.example.com/artifactory', 'repo')
   art_db.save_versions(data)
   ```

3. Update pipeline configuration to use Artifactory parameters

4. Optionally migrate existing release artifacts from S3 to Artifactory

## Security Best Practices

1. **Use API Keys**: Prefer API keys over username/password
2. **Scope Permissions**: Create dedicated users/API keys with minimal required permissions
3. **Enable SSL**: Always use HTTPS endpoints in production
4. **Rotate Credentials**: Regularly rotate API keys and passwords
5. **Audit Access**: Monitor Artifactory access logs for the release monitor user
6. **Network Security**: Use private networks or VPNs where possible

## Support

For issues specific to the Artifactory integration:

1. Check the troubleshooting section above
2. Enable debug logging to see detailed error messages
3. Test Artifactory connectivity manually using curl
4. Verify repository permissions and configuration
5. Check Artifactory server logs if you have administrator access

For JFrog Artifactory-specific issues, consult the [JFrog Documentation](https://www.jfrog.com/confluence/display/JFROG/JFrog+Artifactory) or contact JFrog support.
