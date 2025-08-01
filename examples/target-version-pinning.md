# Target Version Pinning

This feature allows you to pin specific repositories to exact versions, bypassing the normal "latest release" logic.

## Usage

### In Configuration File

```yaml
# config.yaml
repositories:
  - owner: open-policy-agent
    repo: gatekeeper
    description: "Policy Controller for Kubernetes"

download:
  enabled: true
  repository_overrides:
    open-policy-agent/gatekeeper:
      target_version: "v3.19.1"
      asset_patterns: ["*-linux-amd64.tar.gz"]
```

### In Concourse Pipeline Parameters

```yaml
# params/prod.yml
download_repository_overrides: |
  {
    "open-policy-agent/gatekeeper": {
      "target_version": "v3.19.1",
      "asset_patterns": ["*-linux-amd64.tar.gz"],
      "include_prereleases": false
    },
    "kubernetes/kubernetes": {
      "target_version": "1.28.0",
      "asset_patterns": ["kubernetes-server-*.tar.gz", "kubernetes-client-*.tar.gz"]
    }
  }
```

### Via Environment Variable

```bash
# Set specific version for gatekeeper
export REPOSITORY_OVERRIDES='{
  "open-policy-agent/gatekeeper": {
    "target_version": "v3.19.1",
    "asset_patterns": ["*-linux-amd64.tar.gz"]
  }
}'

python github_monitor.py --config config.yaml --download
```

## Version Format

The `target_version` field accepts versions in multiple formats:

- **With 'v' prefix:** `"v3.19.1"`, `"v1.28.0"`
- **Without 'v' prefix:** `"3.19.1"`, `"1.28.0"`

The system automatically normalizes versions to match GitHub's tag format.

## Behavior

1. **Priority:** Target version takes highest priority, overriding:
   - Latest release logic
   - Prerelease filtering (`strict_prerelease_filtering`)
   - Include prereleases setting (`include_prereleases`)

2. **Exact matching:** Only the specified version will be downloaded

3. **Error handling:** If the target version is not found:
   - Logs a warning message
   - Skips the repository (no download occurs)

4. **Monitoring integration:** Works with both monitor and download phases

## Use Cases

### Production Stability

Pin critical components to known-good versions:

```yaml
download_repository_overrides: |
  {
    "kubernetes/kubernetes": {
      "target_version": "v1.28.0",
      "asset_patterns": ["kubernetes-server-*.tar.gz"]
    },
    "etcd-io/etcd": {
      "target_version": "v3.5.9",
      "asset_patterns": ["etcd-*-linux-amd64.tar.gz"]
    }
  }
```

### Testing Specific Versions

Download older versions for testing:

```yaml
download_repository_overrides: |
  {
    "open-policy-agent/gatekeeper": {
      "target_version": "v3.15.0",
      "asset_patterns": ["*-linux-amd64.tar.gz"]
    }
  }
```

### Rollback Scenarios

Quickly revert to previous versions:

```bash
# Rollback gatekeeper from v3.20.0 to v3.19.1
fly set-pipeline -p release-monitor \
  -c ci/pipeline-artifactory.yml \
  -l params/prod.yml \
  -v download_repository_overrides='{
    "open-policy-agent/gatekeeper": {
      "target_version": "v3.19.1",
      "asset_patterns": ["*-linux-amd64.tar.gz"]
    }
  }'
```

## Example Output

When target version is found:

```
2025-08-01 08:55:18,664 - INFO - Checking open-policy-agent/gatekeeper...
2025-08-01 08:55:20,151 - INFO - Found target version: v3.19.1 (requested: v3.19.1)
2025-08-01 08:55:20,152 - INFO - New release found: open-policy-agent/gatekeeper v3.19.1
```

When target version is not found:

```
2025-08-01 08:55:18,664 - INFO - Checking open-policy-agent/gatekeeper...
2025-08-01 08:55:20,151 - INFO - Target version v99.99.99 not found for open-policy-agent/gatekeeper
```
