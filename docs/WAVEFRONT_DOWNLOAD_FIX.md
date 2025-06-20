# Wavefront Download Fix Guide

## Issue Summary

When downloading releases from `wavefrontHQ/observability-for-kubernetes`, the system should download:

1. `wavefront-operator.yaml` (the YAML manifest asset)
2. Source tarball (because `fallback_only: false` for this repository)

## Configuration

The repository has a specific override in `config.yaml`:

```yaml
repository_overrides:
  wavefrontHQ/observability-for-kubernetes:
    asset_patterns: ["*.yaml", "*.yml"]
    source_archives:
      fallback_only: false  # Always download source
      prefer: "tarball"
```

## How It Should Work

1. **Monitor Phase**: `github_monitor.py` fetches release info including assets
2. **Download Phase**: `download_releases.py` processes the release:
   - Downloads `wavefront-operator.yaml` (matches `*.yaml` pattern)
   - Downloads source tarball (because `fallback_only: false`)

## Common Issues and Solutions

### Issue 1: Downloads Not Enabled

**Symptom**: Nothing downloads even though releases are found

**Check**: In `config.yaml`, ensure:

```yaml
download:
  enabled: true  # Must be true for --download flag to work
```

### Issue 2: Version Already Tracked

**Symptom**: Release is skipped because it's already in version database

**Solution**:

```bash
# Option 1: Force check (ignores version tracking)
python github_monitor.py --config config.yaml --force-check --download

# Option 2: Clear version database
rm version_db.json
python github_monitor.py --config config.yaml --download

# Option 3: For S3 version DB
export DISABLE_S3_VERSION_DB=true
python github_monitor.py --config config.yaml --download
```

### Issue 3: Assets Not Being Downloaded

**Symptom**: Only source code downloads, not the YAML file

**Check**: Ensure the monitor output includes assets:

```bash
# Test monitor output
python github_monitor.py --config config.yaml | jq '.releases[].assets'
```

## Verification and Testing

### Quick Verification Tests

Before running full tests, verify the fix is applied:

```bash
# 1. Test upload script file filtering logic
python -m pytest tests/test_upload_scripts.py::TestUploadScriptFileFiltering -v

# 2. Verify all upload scripts support YAML
python -m pytest tests/test_upload_scripts.py::TestAllUploadScriptsYAMLSupport -v

# 3. Check upload script extensions manually
grep -A 3 "supported_extensions" scripts/upload-to-s3.py
```

Expected: Should see `.yaml` and `.yml` in supported extensions list.

### Testing SSL and Proxy Configuration

If you're in a corporate environment with proxy and SSL issues:

```bash
# Test proxy and SSL configuration
python -m pytest tests/test_upload_scripts.py::TestProxySSLConfiguration -v

# Set environment variables for testing
export GITHUB_SKIP_SSL_VERIFICATION=true
export S3_SKIP_SSL_VERIFICATION=true
export HTTP_PROXY=http://your-proxy:80
export HTTPS_PROXY=http://your-proxy:80
```

### 1. Test Monitor Output

```bash
# Create a test config with just wavefront
cat > test-wavefront.yaml << EOF
repositories:
  - owner: wavefrontHQ
    repo: observability-for-kubernetes
    description: "Wavefront Observability"

download:
  enabled: true
  directory: ./test-downloads
  asset_patterns: ["*.yaml", "*.yml"]
  source_archives:
    enabled: true
    prefer: "tarball"
    fallback_only: true
  repository_overrides:
    wavefrontHQ/observability-for-kubernetes:
      asset_patterns: ["*.yaml", "*.yml"]
      source_archives:
        fallback_only: false
        prefer: "tarball"
EOF

# Test monitoring
python github_monitor.py --config test-wavefront.yaml --force-check
```

### 2. Test Download Separately

```bash
# Save monitor output
python github_monitor.py --config test-wavefront.yaml --force-check > monitor-output.json

# Test download
cat monitor-output.json | python download_releases.py --config test-wavefront.yaml
```

### 3. Test Combined Flow

```bash
# Clean state
rm -f version_db.json
rm -rf test-downloads/

# Run combined
python github_monitor.py --config test-wavefront.yaml --force-check --download
```

## Expected Results

After successful download, you should see:

```
test-downloads/
└── wavefrontHQ_observability-for-kubernetes/
    └── v2.30.0/
        ├── wavefront-operator.yaml              # 56KB YAML manifest
        ├── wavefront-operator.yaml.sha256       # Checksum
        ├── wavefrontHQ_...-v2.30.0.tar.gz      # ~1MB source archive
        └── wavefrontHQ_...-v2.30.0.tar.gz.sha256
```

### Verify S3 Upload

Check that YAML files are uploaded to S3:

```bash
# Test upload script logic (dry run)
python scripts/upload-to-s3.py

# Check S3 bucket for YAML files
aws s3 ls s3://your-bucket/release-downloads/ --recursive | grep yaml

# For MinIO or corporate S3-compatible storage
mc ls your-alias/your-bucket/release-downloads/ --recursive | grep yaml
```

Expected output should show:
```
Uploading wavefrontHQ_observability-for-kubernetes/v2.30.0/wavefront-operator.yaml to s3://...
Success: Uploaded 56535 bytes
```

### End-to-End Pipeline Test

Test the complete pipeline with YAML downloads:

```bash
# 1. Monitor for new releases
python github_monitor.py --config config.yaml --output releases.json

# 2. Download releases (including YAML files)  
python download_releases.py --config config.yaml --input releases.json

# 3. Verify downloads
find downloads/ -name "*.yaml" -o -name "*.yml"

# 4. Upload to S3
python scripts/upload-to-s3.py

# 5. Verify in S3 storage
aws s3 ls s3://your-bucket/release-downloads/ --recursive | grep -E "\.(yaml|yml)$"
```

### Upload Script Variants

The system includes multiple upload scripts for different environments:

- **`upload-to-s3.py`** - Default boto3 implementation
- **`upload-to-s3-mc.py`** - MinIO client for better S3-compatible service support
- **`upload-to-s3-no-proxy.py`** - Proxy bypass version for corporate environments

All scripts now support YAML files. Test with:

```bash
# Test specific upload script
python scripts/upload-to-s3-mc.py      # For MinIO environments
python scripts/upload-to-s3-no-proxy.py # For proxy bypass
```

### Troubleshooting Upload Issues

If YAML files are still not uploaded:

1. **Check downloads exist**:
   ```bash
   find downloads/ -name "*.yaml" -type f
   ```

2. **Check upload script debug output**:
   ```bash
   python scripts/upload-to-s3.py
   # Look for: "Scanning for files with extensions: ['.yaml', '.yml', ...]"
   # Should show: "Uploading *.yaml" not "Skipping *.yaml"
   ```

3. **Test file filtering logic**:
   ```bash
   python -c "
   supported_extensions = {'.gz', '.zip', '.tar', '.yaml', '.yml', '.json', '.xml', '.toml', '.exe', '.deb', '.rpm', '.dmg', '.msi'}
   filename = 'wavefront-operator.yaml'
   should_upload = filename.endswith('.yaml') and '.yaml' in supported_extensions
   print(f'Should upload {filename}: {should_upload}')
   "
   ```

4. **Verify S3 credentials and permissions**:
   ```bash
   # Test S3 access
   aws s3 ls s3://your-bucket/ --region your-region
   # Or for MinIO
   mc ls your-alias/your-bucket/
   ```

## Code Flow

1. **Monitor** (`github_monitor.py`):

   ```python
   # Includes assets in output (line 302)
   'assets': latest_release.get('assets', [])
   ```

2. **Download Coordinator** (`download_releases.py`):

   ```python
   # Gets repository-specific config (line 257)
   repo_config = self._get_repository_config(repository)
   
   # Downloads content (line 261)
   download_results = self.downloader.download_release_content(
       release, 
       repo_config.get('asset_patterns'),  # ['*.yaml', '*.yml']
       repo_config.get('source_archives')   # {'fallback_only': False, ...}
   )
   ```

3. **Downloader** (`github_downloader.py`):

   ```python
   # Downloads assets first (line 89)
   if release_data.get('assets'):
       asset_results = self.download_release_assets(...)
   
   # Then checks if source should be downloaded (line 93)
   if source_config.get('enabled', True) and self._should_download_source(...):
       source_results = self.download_source_archives(...)
   ```

## Debugging Commands

```bash
# Check what patterns would match
python -c "
from github_downloader import GitHubDownloader
d = GitHubDownloader('fake')
print('wavefront-operator.yaml matches *.yaml:', d._matches_patterns('wavefront-operator.yaml', ['*.yaml']))
"

# Check repository config
python -c "
from download_releases import ReleaseDownloadCoordinator
config = {'download': {'repository_overrides': {'wavefrontHQ/observability-for-kubernetes': {'asset_patterns': ['*.yaml']}}}}
c = ReleaseDownloadCoordinator(config, 'fake')
print(c._get_repository_config('wavefrontHQ/observability-for-kubernetes'))
"
```
