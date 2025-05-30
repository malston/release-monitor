# Download Guide

This guide covers how to use the GitHub release download functionality.

## Overview

The release monitor can automatically download GitHub release assets based on configurable patterns and version comparison. This feature is designed for:

- Automated artifact collection for CI/CD pipelines
- Version-aware downloads (only download newer releases)
- Asset filtering and verification
- Integration with existing monitoring workflows

## Quick Start

1. **Enable downloads in configuration:**
   ```yaml
   download:
     enabled: true
     directory: ./downloads
   ```

2. **Run monitor with download flag:**
   ```bash
   python3 github_monitor.py --config config.yaml --download
   ```

3. **Check downloaded files:**
   ```bash
   ls -la downloads/
   ```

## Configuration

### Basic Settings

```yaml
download:
  # Enable download functionality
  enabled: true
  
  # Directory to store downloaded files
  directory: ./downloads
  
  # Version database file for tracking downloads
  version_db: ./version_db.json
```

### Asset Filtering

Control which assets to download using patterns:

```yaml
download:
  asset_patterns:
    - "*.tar.gz"       # Include .tar.gz files
    - "*.zip"          # Include .zip files
    - "!*-sources.zip" # Exclude source archives
    - "!*.sig"         # Exclude signature files
```

Pattern syntax:
- `*` matches any characters within a filename
- `!` excludes files matching the pattern
- Patterns are case-insensitive

### Repository Overrides

Configure different settings per repository:

```yaml
download:
  repository_overrides:
    kubernetes/kubernetes:
      asset_patterns:
        - "kubernetes-client-*.tar.gz"
        - "kubernetes-server-*.tar.gz"
      include_prereleases: false
    
    # Disable downloads for specific repos
    some/docs-repo:
      enabled: false
```

### Advanced Settings

```yaml
download:
  # Include pre-releases in downloads
  include_prereleases: false
  
  # Verify downloads with checksums
  verify_downloads: true
  
  # Cleanup old versions automatically
  cleanup_old_versions: true
  keep_versions: 5  # Keep last 5 versions per repository
  
  # Download timeout in seconds
  timeout: 300
```

## Usage

### Basic Download

Run the monitor with download enabled:

```bash
export GITHUB_TOKEN="your_token_here"
python3 github_monitor.py --config config.yaml --download
```

### Pipeline Integration

Use with the monitoring script:

```bash
# Monitor and download in one step
./scripts/monitor.sh --download

# Or use the dedicated download script
./scripts/monitor.sh | ./scripts/download.sh
```

### Standalone Download

Process existing monitor output:

```bash
# Save monitor output first
python3 github_monitor.py --config config.yaml --output releases.json

# Download based on saved output
python3 download_releases.py --config config.yaml --input releases.json
```

## Directory Structure

Downloads are organized by repository and version:

```
downloads/
├── kubernetes_kubernetes/
│   ├── v1.29.0/
│   │   ├── kubernetes-client-linux-amd64.tar.gz
│   │   ├── kubernetes-client-linux-amd64.tar.gz.sha256
│   │   └── kubernetes-server-linux-amd64.tar.gz
│   └── v1.29.1/
│       └── ...
└── prometheus_prometheus/
    ├── v2.48.0/
    └── v2.48.1/
```

## Version Management

The download system uses intelligent version comparison:

- **SemVer**: v1.2.3, v2.0.0-alpha.1
- **CalVer**: 2023.12.1, 23.12
- **Numeric**: 1.0, 1.1.2
- **Custom**: release-20231201

Only newer versions are downloaded based on the stored version database.

## Verification

Downloaded files are verified using:

1. **Size verification**: Compare downloaded size with asset metadata
2. **Checksum generation**: SHA256 checksums are created for all files
3. **Integrity checks**: Verify file integrity during download

Checksum files (`.sha256`) are created alongside each downloaded asset.

## Status and Monitoring

Check download status:

```bash
# Get download statistics
python3 download_releases.py --status

# Include in monitor output
python3 github_monitor.py --config config.yaml --download --output results.json
```

Status information includes:
- Total downloads and sizes
- Version database statistics
- Recent download activity
- Error summaries

## Troubleshooting

### Common Issues

1. **Downloads disabled error:**
   ```
   Download requested but not enabled in configuration
   ```
   - Solution: Set `download.enabled: true` in config.yaml

2. **Permission errors:**
   ```
   Permission denied: ./downloads
   ```
   - Solution: Ensure download directory is writable

3. **Token permissions:**
   ```
   403 Forbidden: Insufficient permissions
   ```
   - Solution: Ensure GITHUB_TOKEN has repository read access

4. **Version comparison issues:**
   - Check version_db.json for stored versions
   - Use `--force-check` to ignore version history

### Debug Mode

Enable verbose logging:

```bash
python3 github_monitor.py --config config.yaml --download --verbose
```

### Clean Start

Reset version database:

```bash
rm version_db.json
```

Reset downloads:

```bash
rm -rf downloads/
```

## Examples

### Example 1: Basic Setup

```yaml
# config.yaml
repositories:
  - owner: prometheus
    repo: prometheus

download:
  enabled: true
  directory: ./artifacts
  asset_patterns:
    - "*.tar.gz"
  verify_downloads: true
```

```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
python3 github_monitor.py --config config.yaml --download
```

### Example 2: Kubernetes Releases

```yaml
# config.yaml
repositories:
  - owner: kubernetes
    repo: kubernetes

download:
  enabled: true
  directory: ./k8s-releases
  repository_overrides:
    kubernetes/kubernetes:
      asset_patterns:
        - "kubernetes-client-linux-amd64.tar.gz"
        - "kubernetes-server-linux-amd64.tar.gz"
      include_prereleases: false
  cleanup_old_versions: true
  keep_versions: 3
```

### Example 3: CI/CD Integration

```bash
#!/bin/bash
# ci-download.sh

set -euo pipefail

echo "Checking for new releases..."
NEW_RELEASES=$(python3 github_monitor.py --config ci-config.yaml --download --format json)

if [[ $(echo "$NEW_RELEASES" | jq '.new_releases_found') -gt 0 ]]; then
    echo "New releases found! Processing downloads..."
    echo "$NEW_RELEASES" | jq '.download_results'
    
    # Trigger downstream pipeline
    ./trigger-deployment.sh
else
    echo "No new releases."
fi
```

## Integration with Concourse

See the main documentation for Concourse pipeline integration examples.