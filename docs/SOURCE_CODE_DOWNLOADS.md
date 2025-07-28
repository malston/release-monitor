# Source Code and Manifest Downloads

This guide explains how to configure the GitHub Release Monitor to download repositories that primarily release Kubernetes manifests, configuration files, or only provide source code archives instead of binary releases.

## Overview

Many repositories don't release traditional binary artifacts. Instead, they provide:

- **Kubernetes manifests** (`.yaml`, `.yml` files)
- **Configuration files** (`.json`, `.toml`, `.xml` files)  
- **Source code archives** (tarball/zipball from GitHub)

The enhanced download system automatically handles these scenarios.

## Configuration

### Basic Manifest Download

```yaml
download:
  enabled: true
  asset_patterns:
    - "*.yaml"      # Kubernetes manifests
    - "*.yml"       # YAML configuration
    - "*.json"      # JSON configuration
    - "*.xml"       # XML configuration
    - "*.toml"      # TOML configuration
```

### Source Code Archive Settings

```yaml
download:
  source_archives:
    # Enable downloading source code when no matching assets found
    enabled: true
    
    # Archive preference: "tarball", "zipball", or "both"
    prefer: "tarball"
    
    # Only download source if no assets match patterns (true)
    # or always download source in addition to assets (false)
    fallback_only: true
```

### Repository-Specific Overrides

For repositories that only provide manifests or source code:

```yaml
download:
  repository_overrides:
    # Example: Wavefront Observability for Kubernetes
    wavefrontHQ/observability-for-kubernetes:
      asset_patterns:
        - "*.yaml"
        - "*.yml"
      source_archives:
        fallback_only: false  # Always download source
        prefer: "tarball"
    
    # Example: Configuration-only repository
    your-org/k8s-configs:
      asset_patterns:
        - "*.yaml"
        - "*.json"
      source_archives:
        enabled: false  # Don't download source for config repos
```

## Example Repositories

### Kubernetes Manifest Repositories

These repositories typically provide YAML manifest files:

```yaml
repositories:
  - owner: wavefrontHQ
    repo: observability-for-kubernetes
    description: "Provides wavefront-operator.yaml manifest"
  
  - owner: kubernetes-sigs
    repo: metrics-server
    description: "Provides components.yaml manifest"
  
  - owner: cert-manager
    repo: cert-manager
    description: "Provides cert-manager.yaml manifest"

download:
  asset_patterns:
    - "*.yaml"
    - "*.yml"
  source_archives:
    enabled: true
    prefer: "tarball"
    fallback_only: true  # Download source if no YAML found
```

### Source-Only Repositories

For repositories that only provide source code:

```yaml
repositories:
  - owner: your-org
    repo: internal-scripts
    description: "Internal automation scripts"

download:
  asset_patterns: []  # No asset patterns
  source_archives:
    enabled: true
    prefer: "tarball"
    fallback_only: false  # Always download source
```

## Download Behavior

### With Assets Present

When a release has matching assets:

1. Downloads matching assets (e.g., `*.yaml` files)
2. Downloads source archives only if `fallback_only: false`

### Without Matching Assets

When no assets match the patterns:

1. Downloads source archives (tarball/zipball) if `source_archives.enabled: true`
2. Respects `prefer` setting for archive type

### Example: Wavefront Repository

For `wavefrontHQ/observability-for-kubernetes`:

- **Assets found**: `wavefront-operator.yaml` (56KB)
- **Configuration**: `fallback_only: false`
- **Downloads**:
  - ✅ `wavefront-operator.yaml` (matches `*.yaml` pattern)
  - ✅ `wavefrontHQ_observability-for-kubernetes-v2.30.0.tar.gz` (source archive)

## File Organization

Downloads are organized by repository and version:

```
downloads/
├── wavefrontHQ_observability-for-kubernetes/
│   └── v2.30.0/
│       ├── wavefront-operator.yaml              # Asset file
│       ├── wavefront-operator.yaml.sha256       # Checksum
│       ├── wavefrontHQ_...-v2.30.0.tar.gz      # Source archive
│       └── wavefrontHQ_...-v2.30.0.tar.gz.sha256
└── cert-manager_cert-manager/
    └── v1.15.0/
        ├── cert-manager.yaml
        └── cert-manager.yaml.sha256
```

## Configuration Reference

### Source Archive Options

| Option | Values | Description |
|--------|--------|-------------|
| `enabled` | `true`/`false` | Enable source code downloads |
| `prefer` | `tarball`/`zipball`/`both` | Archive format preference |
| `fallback_only` | `true`/`false` | Download source only when no assets match |

### Common Asset Patterns

| Pattern | Matches | Use Case |
|---------|---------|----------|
| `*.yaml` | YAML files | Kubernetes manifests |
| `*.yml` | YML files | Configuration files |
| `*.json` | JSON files | Configuration/data |
| `*.xml` | XML files | Configuration files |
| `*.toml` | TOML files | Configuration files |
| `*.tar.gz` | Gzipped tarballs | Source archives |
| `*.zip` | ZIP files | Source archives |

## Testing

Use the provided test script to validate configuration:

```bash
# Test with mock data (no GitHub token needed)
python test_wavefront_mock.py

# Test with real API calls (requires GITHUB_TOKEN)
export GITHUB_TOKEN="your_token_here"
python test_wavefront.py
```

## Pipeline Integration

### Concourse Example

```yaml
jobs:
- name: download-manifests
  plan:
  - get: release-monitor-repo
  - get: monitor-output
    trigger: true
  - task: download-releases
    config:
      platform: linux
      image_resource:
        type: registry-image
        source: {repository: python, tag: "3.11"}
      inputs:
      - name: release-monitor-repo
      - name: monitor-output
      outputs:
      - name: downloads
      params:
        GITHUB_TOKEN: ((github-token))
        ASSET_PATTERNS: '["*.yaml", "*.yml", "*.json"]'
      run:
        path: release-monitor-repo/scripts/download.sh
```

## Troubleshooting

### No Downloads Despite New Releases

Check if:

1. Asset patterns match the available files
2. Source archives are enabled if no assets match
3. Repository-specific overrides are configured correctly

### Large Source Downloads

Source archives can be large. Consider:

1. Setting `fallback_only: true` to avoid unnecessary downloads
2. Adjusting timeout settings for large repositories
3. Using cleanup settings to manage disk space

### Missing Manifests

Some repositories put manifests in assets, others in source code:

1. Enable source downloads as fallback
2. Use both asset patterns and source downloads
3. Check the actual release structure on GitHub

## Best Practices

1. **Start with fallback_only: true** to avoid unnecessary source downloads
2. **Use specific patterns** like `*.yaml` instead of broad patterns
3. **Configure per-repository** for different types of releases
4. **Monitor disk usage** when downloading source archives
5. **Test configurations** with the provided test scripts
