# GitHub Release Download Guide

This guide explains how to use the release download functionality of the GitHub Repository Release Monitor.

## Overview

The download feature allows you to automatically download release assets from GitHub repositories when new versions are detected. This is useful for:

- Maintaining local copies of release artifacts
- Building offline deployment packages
- Creating mirror repositories
- Automating dependency updates in air-gapped environments

## Features

- **Automatic Downloads**: Download assets when new releases are detected
- **Version Tracking**: Smart version management prevents re-downloading
- **Asset Filtering**: Download only the files you need using patterns
- **Organized Storage**: Files are organized by repository and version
- **Verification**: Optional checksum verification for downloaded files
- **Retry Logic**: Automatic retry on download failures
- **Concurrent Downloads**: Efficient parallel downloading

## Quick Start

1. **Enable downloads in configuration:**

   ```yaml
   download:
     enabled: true
     directory: ./downloads
   ```

2. **Run monitor with download flag:**

   ```sh
   python3 github_monitor.py --config config.yaml --download
   ```

3. **Check downloaded files:**

   ```sh
   ls -la downloads/
   ```

## Configuration

Add a `download` section to your `config.yaml`:

```yaml
repositories:
  - owner: kubernetes
    repo: kubernetes
    include_prereleases: false
  
  - owner: hashicorp
    repo: terraform
    include_prereleases: false

download:
  # Enable/disable downloads globally
  enabled: true
  
  # Base directory for downloads
  directory: ./downloads
  
  # Version database location
  version_db: ./version_db.json
  
  # Asset patterns (glob patterns supported)
  asset_patterns:
    - "*.tar.gz"
    - "*.zip"
    - "!*-sources.zip"    # Exclude source archives
    - "!*.sig"            # Exclude signatures
  
  # Optional settings
  verify_checksums: true   # Verify SHA256 checksums if provided
  retry_attempts: 3        # Number of retry attempts
  retry_delay: 2          # Seconds between retries
  max_concurrent: 4       # Max concurrent downloads
```

### Asset Pattern Syntax

- `*` matches any characters except `/`
- `**` matches any characters including `/`
- `?` matches any single character
- `[seq]` matches any character in seq
- `[!seq]` matches any character not in seq
- Patterns starting with `!` exclude matching files

Examples:
- `"*.tar.gz"` - All gzipped tar files
- `"kubernetes-*.tar.gz"` - Kubernetes tar files only
- `"!*-arm64.tar.gz"` - Exclude ARM64 builds
- `"binaries/*.exe"` - Windows executables in binaries folder

## Usage

### Basic Download

Run the monitor with download enabled:

```sh
export GITHUB_TOKEN="your_token_here"
python3 github_monitor.py --config config.yaml --download
```

### Pipeline Integration

Use with the monitoring script:

```sh
# Monitor and download in one step
./scripts/monitor.sh --download

# Or use the dedicated download script
./scripts/monitor.sh | ./scripts/download.sh
```

### Standalone Download

Process existing monitor output:

```sh
# Save monitor output first
python3 github_monitor.py --config config.yaml --output releases.json

# Download based on saved output
python3 download_releases.py --config config.yaml --input releases.json
```

### Download Directory Structure

Downloads are organized as follows:

```
downloads/
├── kubernetes/
│   └── kubernetes/
│       ├── v1.29.0/
│       │   ├── kubernetes.tar.gz
│       │   └── kubernetes-client-linux-amd64.tar.gz
│       └── v1.29.1/
│           ├── kubernetes.tar.gz
│           └── kubernetes-client-linux-amd64.tar.gz
└── hashicorp/
    └── terraform/
        └── v1.7.0/
            ├── terraform_1.7.0_linux_amd64.zip
            └── terraform_1.7.0_SHA256SUMS
```

## Version Management

The version database (`version_db.json`) tracks:

- Current version for each repository
- Download history and timestamps
- File metadata (size, checksums)

Example version database entry:

```json
{
  "kubernetes/kubernetes": {
    "current_version": "v1.29.1",
    "last_checked": "2024-01-15T10:30:00Z",
    "downloads": {
      "v1.29.1": {
        "downloaded_at": "2024-01-15T10:31:00Z",
        "assets": [
          {
            "name": "kubernetes.tar.gz",
            "size": 524288000,
            "path": "downloads/kubernetes/kubernetes/v1.29.1/kubernetes.tar.gz",
            "checksum": "sha256:abc123..."
          }
        ]
      }
    }
  }
}
```

## Advanced Usage

### Filtering by Repository

Create separate configs for different repository groups:

```yaml
# infrastructure-tools.yaml
repositories:
  - owner: hashicorp
    repo: terraform
  - owner: hashicorp
    repo: vault
  - owner: kubernetes
    repo: kubectl

download:
  directory: ./infrastructure-downloads
  asset_patterns:
    - "*linux_amd64*"
```

### Custom Download Scripts

Process downloads after completion:

```bash
#!/bin/bash
# post-download.sh

# Monitor and download
./scripts/monitor.sh --download --output results.json

# Process downloads
if [ $(jq '.downloads.successful_count' results.json) -gt 0 ]; then
  # Extract all tar.gz files
  find ./downloads -name "*.tar.gz" -exec tar -xzf {} \;
  
  # Copy binaries to local bin
  find ./downloads -name "kubectl" -o -name "terraform" | \
    xargs -I {} cp {} /usr/local/bin/
fi
```

### Integration with CI/CD

Example GitHub Actions workflow:

```yaml
name: Download Latest Releases

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:

jobs:
  download:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Download new releases
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          python3 github_monitor.py --config config.yaml --download
      
      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: release-downloads
          path: downloads/
```

## Troubleshooting

### Common Issues

1. **Rate Limiting**
   ```yaml
   download:
     retry_delay: 5  # Increase delay between retries
   ```

2. **Large Files**
   - Downloads are streamed to disk to handle large files
   - Ensure sufficient disk space
   - Consider using `max_concurrent: 1` for very large files

3. **Partial Downloads**
   - Failed downloads are automatically cleaned up
   - Use `--force-download` to re-download existing versions

4. **Permission Errors**
   ```bash
   # Ensure download directory is writable
   chmod -R u+w ./downloads
   ```

### Debug Mode

Enable detailed logging:

```bash
# Set log level
export LOG_LEVEL=DEBUG
python3 github_monitor.py --config config.yaml --download

# Or use the script
./scripts/download.sh --debug
```

## Security Considerations

1. **Token Permissions**: Use read-only tokens
2. **Checksum Verification**: Enable `verify_checksums` for security
3. **HTTPS Only**: All downloads use HTTPS
4. **Path Validation**: Downloads are restricted to configured directory

## Performance Tips

1. **Concurrent Downloads**: Adjust `max_concurrent` based on bandwidth
2. **Asset Patterns**: Be specific to avoid unnecessary downloads
3. **Version Database**: Regularly backup `version_db.json`
4. **Disk Space**: Monitor available space, especially for large repositories

## Examples

### Download Only Stable Releases

```yaml
repositories:
  - owner: kubernetes
    repo: kubernetes
    include_prereleases: false  # Skip alpha/beta/rc releases

download:
  enabled: true
  asset_patterns:
    - "*client*linux*amd64*.tar.gz"  # Client tools only
```

### Mirror Multiple Tools

```yaml
repositories:
  - owner: kubernetes-sigs
    repo: kind
  - owner: kubernetes
    repo: minikube
  - owner: helm
    repo: helm

download:
  directory: ./k8s-tools-mirror
  asset_patterns:
    - "*linux-amd64*"
    - "!*.sha256"  # Skip checksum files
```

### Continuous Mirroring Script

```bash
#!/bin/bash
# continuous-mirror.sh

while true; do
  echo "Checking for new releases..."
  
  # Run monitor with download
  if python3 github_monitor.py --config mirror.yaml --download; then
    # Sync to S3 or other storage
    aws s3 sync ./downloads s3://my-mirror-bucket/ --delete
  fi
  
  # Wait 1 hour
  sleep 3600
done
```

## Integration with Concourse

See the main documentation for Concourse pipeline integration examples.
