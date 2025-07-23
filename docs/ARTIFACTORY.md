# JFrog Artifactory Integration Guide

Complete guide for setting up and using GitHub Release Monitor with JFrog Artifactory.

## Table of Contents

1. [Quick Start](#quick-start) - Get running in 5 minutes
2. [Docker Setup](#docker-setup) - Local development with Docker
3. [Configuration](#configuration) - Production and pipeline setup
4. [Downloading Releases](#downloading-releases) - Using the download scripts
5. [Pipeline Integration](#pipeline-integration) - Concourse CI/CD setup
6. [Troubleshooting](#troubleshooting) - Common issues and solutions

---

## Quick Start

### Prerequisites

- Docker and Docker Compose (for local setup)
- Python 3 with `requests` library
- GitHub token for API access

### 1. Start Artifactory (Local Development)

```bash
# Start Artifactory with PostgreSQL
docker-compose -f docker-compose-artifactory.yml up -d

# Wait for it to be ready (5-10 minutes on first start)
./scripts/wait-for-artifactory.sh
```

### 2. Complete Setup Wizard

1. **Open Artifactory**: http://localhost:8081
2. **Login**: `admin` / `password`  
3. **Set New Password**: Choose a secure password
4. **Base URL**: Set to `http://localhost:8081/artifactory`
5. **Proxy**: Skip proxy configuration
6. **Create Repository**:
   - Go to Administration → Repositories → Repositories
   - New Repository → Generic → Repository Key: `generic-releases`
   - Save & Finish

### 3. Generate API Key

1. **User Menu** → Generate API Key
2. **Copy** the generated key
3. **Save** it securely

### 4. Configure Environment Variables

```bash
# Artifactory configuration
export ARTIFACTORY_URL="http://localhost:8081/artifactory"
export ARTIFACTORY_REPOSITORY="generic-releases"  
export ARTIFACTORY_API_KEY="your-generated-api-key"

# GitHub token (required)
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"
```

### 5. Test the Integration

```bash
# Install dependencies
source venv/bin/activate
pip install requests

# Test connection
python -c "
from github_version_artifactory import ArtifactoryVersionDatabase
import os
db = ArtifactoryVersionDatabase(
    base_url=os.environ['ARTIFACTORY_URL'],
    repository=os.environ['ARTIFACTORY_REPOSITORY'],
    api_key=os.environ['ARTIFACTORY_API_KEY']
)
print('✅ Connection successful!')
print('Version database:', db.load_versions())
"

# Run release monitor
python github_monitor.py --config ./config.yaml --download

# Download releases from Artifactory
./scripts/download-from-artifactory.sh --list
```

---

## Docker Setup

### Local Development Setup

For local development and testing, use the provided Docker Compose setup:

```bash
# Start all services
docker-compose -f docker-compose-artifactory.yml up -d

# Check status
docker-compose -f docker-compose-artifactory.yml ps

# View logs
docker-compose -f docker-compose-artifactory.yml logs -f artifactory

# Stop services
docker-compose -f docker-compose-artifactory.yml down
```

### Docker Compose Services

- **Artifactory**: JFrog Artifactory OSS with PostgreSQL backend
- **PostgreSQL**: Database for Artifactory
- **Setup Helper**: Automated setup and status checking

### Useful Commands

```bash
# Restart just Artifactory
docker-compose -f docker-compose-artifactory.yml restart artifactory

# Reset everything (⚠️ Destructive!)
docker-compose -f docker-compose-artifactory.yml down -v

# Shell into container
docker exec -it release-monitor-artifactory bash
```

---

## Configuration

### ⚠️ Important: Configuration Precedence

**Environment variables override config file settings!** The script auto-detects storage backends:

**Configuration Precedence (Highest to Lowest):**
1. **Environment Variables** (auto-detection) 🥇
2. **Config File Settings**
3. **Default Values**

**Auto-Detection Behavior:**
- If `ARTIFACTORY_URL` and `ARTIFACTORY_REPOSITORY` are set → **Artifactory storage is used**
- Even if `config.yaml` has `artifactory_storage.enabled: false`

**Avoid Confusion:**
- Unset Artifactory environment variables to use local storage
- Or use separate `.env` files for different scenarios
- See [Troubleshooting Guide](TROUBLESHOOTING.md#environment-variables-override-config-file-settings) for details

### Environment Variables

#### Required

```bash
# Artifactory endpoint (without repository path)
export ARTIFACTORY_URL="https://your-company.jfrog.io/artifactory"
export ARTIFACTORY_REPOSITORY="generic-releases"

# Authentication (choose one method)
export ARTIFACTORY_API_KEY="your-api-key"
# OR
export ARTIFACTORY_USERNAME="your-username"
export ARTIFACTORY_PASSWORD="your-password"
```

#### Optional

```bash
# SSL verification (default: true)
export ARTIFACTORY_SKIP_SSL_VERIFICATION="false"

# Path prefix in repository (default: release-monitor/)
export ARTIFACTORY_PATH_PREFIX="release-monitor/"
```

### Application Configuration

Edit `config.yaml`:

```yaml
download:
  enabled: true
  directory: ./downloads
  
  # Use Artifactory for version database and storage
  artifactory_storage:
    enabled: true
    base_url: "https://your-company.jfrog.io/artifactory"
    repository: "generic-releases"
    path_prefix: "release-monitor/"
    verify_ssl: true
    # Credentials read from environment variables
```

### Repository Structure

Artifacts are stored in this structure:

```
<repository>/
├── release-monitor/
│   ├── version_db.json                    # Version tracking database
│   ├── latest-releases.json               # Latest release metadata
│   └── release-downloads/                 # Downloaded artifacts
│       ├── kubernetes_kubernetes/         # Owner_repo format
│       │   ├── v1.28.0/
│       │   │   └── kubernetes-v1.28.0-linux-amd64.tar.gz
│       │   └── v1.28.1/
│       │       └── kubernetes-v1.28.1-linux-amd64.tar.gz
│       └── prometheus_prometheus/
│           └── v2.45.0/
│               └── prometheus-2.45.0.linux-amd64.tar.gz
```

---

## Downloading Releases

Once releases are uploaded to Artifactory, use the download scripts to retrieve them locally.

### Quick Download

```bash
# Download all releases
./scripts/download-from-artifactory.sh

# Download specific repository
./scripts/download-from-artifactory.sh --repo kubernetes/kubernetes

# List available repositories
./scripts/download-from-artifactory.sh --list
```

### Advanced Usage

```bash
# Download with pattern matching
./scripts/download-from-artifactory.sh --pattern "*.tar.gz"
./scripts/download-from-artifactory.sh --pattern "*linux-amd64*"

# Specify output directory
./scripts/download-from-artifactory.sh --output-dir ~/my-releases

# Combine options
./scripts/download-from-artifactory.sh \
  --repo kubernetes/kubernetes \
  --pattern "kubernetes-server-*.tar.gz" \
  --output-dir ./k8s-releases
```

### Python Script Direct Usage

For more control, use the Python script directly:

```bash
python3 scripts/download-from-artifactory.py \
  --url http://localhost:8081/artifactory \
  --repository generic-releases \
  --api-key "your-api-key" \
  --repo istio/istio \
  --pattern "istio-*-linux-amd64.tar.gz" \
  --output-dir ./istio-releases
```

### Script Options

```
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

---

## Pipeline Integration

### Concourse Pipeline Setup

Use the Artifactory-specific pipeline configuration:

```bash
# Deploy pipeline
fly -t your-target set-pipeline \
  -p release-monitor-artifactory \
  -c ci/pipeline-artifactory.yml \
  -l params/global-artifactory.yml

# Unpause pipeline
fly -t your-target unpause-pipeline -p release-monitor-artifactory
```

### Parameter File

Copy and customize the parameter file:

```bash
cp params/global-artifactory.yml params/your-environment.yml
```

Edit with your settings:

```yaml
# GitHub configuration
github_token: ((github_token))

# JFrog Artifactory configuration
artifactory_url: https://your-company.jfrog.io/artifactory
artifactory_repository: generic-releases

# Authentication (store in Concourse secrets)
artifactory_api_key: ((artifactory_api_key))
# OR
artifactory_username: ((artifactory_username))
artifactory_password: ((artifactory_password))

# SSL configuration
artifactory_skip_ssl_verification: false
```

### Concourse Secrets

Store credentials securely:

#### Using Vault
```bash
vault kv put concourse/main/release-monitor-artifactory \
  artifactory_api_key="your-api-key"
```

#### Using CredHub
```bash
credhub set -n /concourse/main/release-monitor-artifactory/artifactory_api_key \
  -t value -v "your-api-key"
```

### Pipeline Jobs

The pipeline includes these jobs:

- **monitor-releases**: Check GitHub for new releases
- **download-releases**: Download and upload to Artifactory
- **check-version-database**: Inspect version database
- **reset-version-database**: Clear database (forces re-download)

---

## Troubleshooting

### Downloads Not Working Despite New Releases

**Issue:** Script finds new releases but downloads 0 files, shows "Skipping X: Version Y is not newer than Y"

**Root Cause:** Version database already contains these versions from previous runs.

**Quick Fix:**
```bash
# Clear Artifactory version database
python -c "
from github_version_artifactory import ArtifactoryVersionDatabase
import os
db = ArtifactoryVersionDatabase(
    base_url=os.environ['ARTIFACTORY_URL'],
    repository=os.environ['ARTIFACTORY_REPOSITORY'],
    api_key=os.environ.get('ARTIFACTORY_API_KEY'),
    verify_ssl=False
)
db.save_versions({'repositories': {}, 'metadata': {'version': '2.0'}})
print('✅ Version database cleared!')
"

# Then run downloads
rm -f release_state.json
python github_monitor.py --config ./config.yaml --download
```

### Artifactory Not Starting

**Symptoms**: Container fails to start or setup wizard doesn't load

**Solutions**:
- Check logs: `docker-compose -f docker-compose-artifactory.yml logs -f artifactory`
- Wait longer: First startup takes 5-10 minutes
- Check memory: Artifactory needs at least 2GB RAM
- Clear browser cache and try http://localhost:8081/ui/

### Authentication Errors (401/403)

**Symptoms**: HTTP 401 Unauthorized or 403 Forbidden errors

**Solutions**:
- Verify API key or username/password are correct
- Check user has proper permissions for the repository
- Test manually: `curl -H "X-JFrog-Art-Api: your-key" "http://localhost:8081/artifactory/api/repositories"`

### SSL Certificate Issues

**Symptoms**: SSL verification failures

**Solutions**:
- For testing: Set `ARTIFACTORY_SKIP_SSL_VERIFICATION=true`
- For production: Add CA certificate to system trust store
- Use `--no-verify-ssl` flag with download scripts

### Connection Errors

**Symptoms**: Cannot connect to Artifactory

**Solutions**:
- Check URL format: should end with `/artifactory` (no trailing slash)
- For Docker: Ensure port 8081 is accessible
- Check firewall and proxy settings
- Verify Artifactory is running: `curl http://localhost:8081/artifactory/api/system/ping`

### No Artifacts Found

**Symptoms**: Download scripts find no repositories or files

**Solutions**:
- Verify releases have been uploaded by the pipeline
- Check repository name matches pipeline configuration
- Use `--list` to see what's available
- Check path prefix setting (default: `release-monitor/release-downloads/`)

### Repository Not Found (404)

**Symptoms**: Repository doesn't exist errors

**Solutions**:
- Create the repository in Artifactory UI:
  - Administration → Repositories → Repositories
  - New Repository → Generic → Repository Key: `generic-releases`
- Check repository name in configuration matches exactly
- Verify user has access to the repository

### Performance Issues

**Symptoms**: Slow uploads/downloads or timeouts

**Solutions**:
- Use Artifactory instances close to your network
- Check available bandwidth and storage space
- Monitor repository size and consider cleanup policies
- Use connection pooling for multiple operations

### Debug Mode

Enable detailed logging:

```bash
export LOG_LEVEL="DEBUG"
python download_releases.py
```

### Manual Database Operations

```python
# Reset version database
from github_version_artifactory import ArtifactoryVersionDatabase
import os

db = ArtifactoryVersionDatabase(
    base_url=os.environ['ARTIFACTORY_URL'],
    repository=os.environ['ARTIFACTORY_REPOSITORY'],
    api_key=os.environ['ARTIFACTORY_API_KEY']
)

# Clear database (forces re-download)
empty_data = {'repositories': {}, 'metadata': {'version': '2.0'}}
db.save_versions(empty_data)
```

---

## Security Best Practices

1. **Use API Keys**: Prefer API keys over username/password
2. **Scope Permissions**: Create dedicated users with minimal required permissions
3. **Enable SSL**: Always use HTTPS in production
4. **Rotate Credentials**: Regularly update API keys and passwords
5. **Monitor Access**: Review Artifactory access logs
6. **Network Security**: Use private networks or VPNs where possible

---

## Migration from S3

To migrate from S3 to Artifactory:

1. **Export S3 version database**:
   ```python
   from github_version_s3 import S3VersionDatabase
   s3_db = S3VersionDatabase('your-s3-bucket')
   data = s3_db.load_versions()
   ```

2. **Import to Artifactory**:
   ```python
   from github_version_artifactory import ArtifactoryVersionDatabase
   art_db = ArtifactoryVersionDatabase('https://artifactory.example.com/artifactory', 'repo')
   art_db.save_versions(data)
   ```

3. **Update pipeline configuration** to use Artifactory parameters

4. **Optionally migrate artifacts** from S3 to Artifactory

---

## Support

For issues:

1. **📖 [Complete Troubleshooting Guide](TROUBLESHOOTING.md)** - Detailed solutions for common issues
2. Check this troubleshooting section above
3. Enable debug logging: `export LOG_LEVEL="DEBUG"`
4. Test Artifactory connectivity manually with curl
5. Verify repository permissions and configuration
6. Check Artifactory server logs (if you have admin access)

**Common Issues:**
- [Downloads not working despite new releases found](TROUBLESHOOTING.md#downloads-not-working)
- [Environment variables overriding config settings](TROUBLESHOOTING.md#environment-variables-override-config-file-settings)
- [Connection and authentication errors](TROUBLESHOOTING.md#downloads-fail-with-connection-errors)

For JFrog Artifactory-specific issues, consult the [JFrog Documentation](https://www.jfrog.com/confluence/display/JFROG/JFrog+Artifactory).