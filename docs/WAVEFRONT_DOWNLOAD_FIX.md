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

## Testing the Fix

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
