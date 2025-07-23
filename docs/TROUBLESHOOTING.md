# Troubleshooting Guide

Common issues and solutions for the GitHub Release Monitor.

## Downloads Not Working

### Issue: No Downloads Despite New Releases Found

**Symptoms:**
- Script reports new releases found but downloads 0 files
- Debug logs show "Skipping X: Version Y is not newer than Y"
- Downloads worked before but suddenly stopped

**Root Cause:**
The version database already contains these release versions, so the script considers them "already downloaded" and skips them.

**Solution 1 - Reset Version Database (Local Storage):**
```bash
# Remove local version database
rm -f version_db.json release_state.json

# Run again
python github_monitor.py --config ./config.yaml --download
```

**Solution 2 - Reset Version Database (S3 Storage):**
```bash
# Delete version database from S3
aws s3 rm s3://your-bucket/release-monitor/version_db.json

# Run again
python github_monitor.py --config ./config.yaml --download
```

**Solution 3 - Reset Version Database (Artifactory):**
```bash
# Clear Artifactory version database
python -c "
from github_version_artifactory import ArtifactoryVersionDatabase
import os
db = ArtifactoryVersionDatabase(
    base_url=os.environ['ARTIFACTORY_URL'],
    repository=os.environ['ARTIFACTORY_REPOSITORY'],
    username=os.environ.get('ARTIFACTORY_USERNAME'),
    password=os.environ.get('ARTIFACTORY_PASSWORD'),
    api_key=os.environ.get('ARTIFACTORY_API_KEY'),
    verify_ssl=False
)
db.save_versions({'repositories': {}, 'metadata': {'version': '2.0'}})
print('✅ Artifactory version database cleared!')
"

# Run again
python github_monitor.py --config ./config.yaml --download
```

### Issue: Environment Variables Override Config File Settings

**Symptoms:**
- Config has `artifactory_storage.enabled: false` but script uses Artifactory anyway
- Log shows "Auto-detected Artifactory version database from environment variables"
- Expected local storage but got cloud storage instead

**Root Cause:**
Environment variables take precedence over config file settings. The script auto-detects storage backends based on environment variables.

**Configuration Precedence (Highest to Lowest):**
1. **Environment Variables** (auto-detection)
2. **Config File Settings**
3. **Default Values**

**Auto-Detection Rules:**
- **Artifactory**: If `ARTIFACTORY_URL` and `ARTIFACTORY_REPOSITORY` are set
- **S3**: If `AWS_ACCESS_KEY_ID` and S3 bucket is configured
- **Local**: Fallback when no cloud storage is detected

**Solution - Control Auto-Detection:**

**Option 1 - Use Force Download Flag (Recommended):**
```bash
# Bypass auto-detection with --force-download flag
python github_monitor.py --config ./config.yaml --force-download
```

**Option 2 - Disable Environment Variables:**
```bash
# Temporarily unset Artifactory variables
unset ARTIFACTORY_URL
unset ARTIFACTORY_REPOSITORY
unset ARTIFACTORY_USERNAME
unset ARTIFACTORY_PASSWORD
unset ARTIFACTORY_API_KEY

# Run with local storage
python github_monitor.py --config ./config.yaml --download
```

**Option 3 - Use Separate Environment Files:**
```bash
# Create .env.local (no Artifactory variables)
cat > .env.local << 'EOF'
export GITHUB_TOKEN="your-token"
EOF

# Use local environment
source .env.local
python github_monitor.py --config ./config.yaml --download
```

**Option 4 - Explicit Config Override:**
```yaml
# In config.yaml - be very explicit
download:
  enabled: true
  directory: ./downloads
  version_db: ./version_db.json
  
  # Explicitly disable all cloud storage
  s3_storage:
    enabled: false
  
  artifactory_storage:
    enabled: false
```

### Issue: Downloads Fail with Connection Errors

**Symptoms:**
- "Connection refused" or "timeout" errors
- Can't connect to Artifactory/S3
- Downloads work sometimes but not others

**Solutions:**

**For Artifactory:**
```bash
# Check if Artifactory is running
curl -f http://localhost:8081/artifactory/api/system/ping

# Start Artifactory if needed
docker-compose -f docker-compose-artifactory.yml up -d
./scripts/wait-for-artifactory.sh

# Test authentication
curl -H "X-JFrog-Art-Api: $ARTIFACTORY_API_KEY" \
  "$ARTIFACTORY_URL/api/repositories"
```

**For S3:**
```bash
# Test S3 connection
aws s3 ls s3://your-bucket/

# For MinIO
export AWS_ENDPOINT_URL=http://localhost:9000
aws s3 ls s3://your-bucket/
```

## Configuration Issues

### Issue: "No module named 'yaml'" Error

**Symptoms:**
```
ModuleNotFoundError: No module named 'yaml'
```

**Solution:**
```bash
# Install dependencies
pip install PyYAML requests

# Or use virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Issue: "GITHUB_TOKEN environment variable is required"

**Solution:**
```bash
# Set GitHub token
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"

# Or use .env file
echo 'export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"' > .env
source .env
```

### Issue: Config File Not Found

**Symptoms:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'config.yaml'
```

**Solution:**
```bash
# Check current directory
ls -la config.yaml

# Use absolute path
python github_monitor.py --config /full/path/to/config.yaml

# Or copy example config
cp config-example.yaml config.yaml
```

## Debug Mode

Enable detailed logging to see what's happening:

```bash
# Enable debug logging
LOG_LEVEL=DEBUG python github_monitor.py --config ./config.yaml --download

# Key debug information to look for:
# - Storage backend detection
# - Version comparisons
# - API calls and responses
# - Download decisions
```

## Understanding Log Messages

### Version Comparison Logs
```
DEBUG - Version comparison: v1.33.3 vs v1.33.3 = 0 (newer: False)
DEBUG - Skipping kubernetes/kubernetes: Version v1.33.3 is not newer than v1.33.3
```
**Meaning:** The release version (v1.33.3) is not newer than what's in the version database (v1.33.3), so it's skipped.

### Storage Detection Logs
```
INFO - Auto-detected Artifactory version database from ARTIFACTORY_URL and ARTIFACTORY_REPOSITORY environment variables
```
**Meaning:** Environment variables overrode config file settings.

### Download Decision Logs
```
DEBUG - Skipping pre-release: v3.20.0-rc.1
```
**Meaning:** Pre-releases are excluded (check `include_prereleases` setting).

## Quick Diagnostic Commands

### Check Environment Variables
```bash
env | grep -E "(GITHUB_TOKEN|ARTIFACTORY|AWS)" | sort
```

### Check Config Parsing
```bash
python -c "
import yaml
with open('config.yaml') as f:
    config = yaml.safe_load(f)
    print('Download enabled:', config.get('download', {}).get('enabled'))
    print('Artifactory enabled:', config.get('download', {}).get('artifactory_storage', {}).get('enabled'))
"
```

### Check Version Database Content
```bash
# Local
cat version_db.json | python -m json.tool

# S3
aws s3 cp s3://your-bucket/release-monitor/version_db.json - | python -m json.tool

# Artifactory
curl -s -u admin:password \
  "http://localhost:8081/artifactory/generic-releases/release-monitor/version_db.json" \
  | python -m json.tool
```

### Test GitHub API Access
```bash
curl -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/kubernetes/kubernetes/releases/latest"
```

## Common Patterns

### Fresh Start (Complete Reset)
```bash
# Remove all local state
rm -f release_state.json version_db.json

# Clear environment
unset ARTIFACTORY_URL ARTIFACTORY_REPOSITORY
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY

# Run with clean config
python github_monitor.py --config ./config.yaml --download
```

### Testing New Repository
```bash
# Add to config.yaml
repositories:
  - owner: test-org
    repo: test-repo
    description: "Test repository"

# Force check to see recent releases
python github_monitor.py --config ./config.yaml --force-check --download
```

### Pipeline Testing
```bash
# Test monitoring only
python github_monitor.py --config ./config.yaml --output test-releases.json

# Check output
cat test-releases.json | python -m json.tool

# Test downloads with specific input
python download_releases.py --input test-releases.json --output ./test-downloads
```

## Getting Help

1. **Enable Debug Mode**: Use `LOG_LEVEL=DEBUG` to see detailed execution
2. **Check Configuration Precedence**: Environment variables override config files
3. **Verify Connectivity**: Test GitHub API, Artifactory, and S3 connections manually
4. **Reset State**: Clear version databases when testing or troubleshooting
5. **Use Force Check**: `--force-check` ignores timestamps for testing

For additional help, check the main documentation or create an issue with:
- Full debug logs (`LOG_LEVEL=DEBUG`)
- Configuration file (redact sensitive tokens)
- Environment variables (redact sensitive values)
- Expected vs actual behavior