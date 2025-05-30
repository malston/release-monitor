# GitHub Issues for Download Feature Implementation

Run these commands to create the implementation issues:

## Epic Issue
```bash
gh issue create --title "Epic: Add GitHub Release Download Capability" --body "$(cat <<'EOF'
# Epic: GitHub Release Download Capability

## Overview
Add capability to automatically download newer GitHub releases after they are detected by the monitor.

## Problem
Currently the monitor only detects new releases but doesn't provide a way to automatically download them. Users need to manually download releases after being notified.

## Solution
Implement a download system that:
- Compares release versions against stored current versions
- Downloads only genuinely newer releases
- Maintains a version database
- Integrates with existing Concourse pipelines

## Related Issues
This epic will be broken down into the following phases:
- [ ] Phase 1: Core Infrastructure (Version DB & Comparison)
- [ ] Phase 2: Download Functionality  
- [ ] Phase 3: Integration & Configuration
- [ ] Phase 4: Concourse Pipeline Integration

## Success Criteria
- [ ] Accurate version comparison for SemVer, CalVer, custom formats
- [ ] Reliable download with retry logic and verification
- [ ] Seamless integration with existing monitor
- [ ] Full Concourse pipeline support
- [ ] Comprehensive documentation

See IMPLEMENTATION_PLAN.md for detailed technical approach.
EOF
)" --label "epic,enhancement"
```

## Phase 1: Core Infrastructure
```bash
gh issue create --title "Phase 1: Implement Version Database and Comparison Logic" --body "$(cat <<'EOF'
# Phase 1: Core Infrastructure - Version Database and Comparison

## Overview
Implement the foundational components for version tracking and comparison.

## Tasks

### 1.1 Version Database Module
- [ ] Create `github_version_db.py` with VersionDatabase class
- [ ] Implement JSON-based storage for version tracking
- [ ] Add methods: get_current_version, update_version, get_download_history
- [ ] Handle concurrent access safely
- [ ] Create unit tests

### 1.2 Version Comparison Logic  
- [ ] Create `version_compare.py` with VersionComparator class
- [ ] Support SemVer (1.2.3, 1.2.3-alpha.1)
- [ ] Support CalVer (2024.01.15, 2024.1.0)
- [ ] Support custom formats (v1.0, release-1.0)
- [ ] Implement is_newer() logic with proper precedence
- [ ] Create comprehensive unit tests

## Acceptance Criteria
- [ ] Version database persists across runs
- [ ] Version comparison handles all common formats correctly
- [ ] Pre-releases are handled according to configuration
- [ ] 100% test coverage for core comparison logic
- [ ] Performance: Compare 1000+ versions in <1 second

## Files to Create
- `github_version_db.py`
- `version_compare.py` 
- `tests/test_version_db.py`
- `tests/test_version_compare.py`

## Technical Notes
- Use semver library for SemVer parsing
- Fallback to string comparison for unknown formats
- Store metadata (download date, file paths) with versions
EOF
)" --label "enhancement,phase-1"
```

## Phase 2: Download Functionality
```bash
gh issue create --title "Phase 2: Implement GitHub Release Asset Downloader" --body "$(cat <<'EOF'
# Phase 2: Download Functionality

## Overview
Implement the core download functionality for GitHub release assets.

## Tasks

### 2.1 Asset Downloader
- [ ] Create `github_downloader.py` with GitHubDownloader class
- [ ] Implement authenticated GitHub API calls
- [ ] Support downloading multiple assets per release
- [ ] Add checksum verification when available
- [ ] Implement retry logic with exponential backoff
- [ ] Handle large file downloads with streaming
- [ ] Create unit tests with mocked downloads

### 2.2 Main Download Script
- [ ] Create `download_releases.py` main entry point
- [ ] Parse monitor output JSON format
- [ ] Integrate version comparison logic
- [ ] Coordinate downloads with database updates
- [ ] Add comprehensive logging and error handling
- [ ] Create `scripts/download.sh` wrapper for Concourse

## Acceptance Criteria
- [ ] Successfully downloads assets from public GitHub repos
- [ ] Verifies download integrity with checksums
- [ ] Handles network failures gracefully (3 retries)
- [ ] Downloads large files (>100MB) without memory issues
- [ ] Atomic operations (database updated only after successful download)
- [ ] Clear logging for debugging and auditing

## Files to Create
- `github_downloader.py`
- `download_releases.py`
- `scripts/download.sh`
- `tests/test_downloader.py`
- `tests/test_download_releases.py`

## Technical Notes
- Use requests library with stream=True for large files
- Store downloads in organized directory structure
- Support configurable file patterns (*.tar.gz, *.zip)
EOF
)" --label "enhancement,phase-2"
```

## Phase 3: Integration & Configuration
```bash
gh issue create --title "Phase 3: Integration with Existing Monitor and Configuration" --body "$(cat <<'EOF'
# Phase 3: Integration & Configuration

## Overview
Integrate download functionality with existing monitor and add configuration options.

## Tasks

### 3.1 Configuration Schema
- [ ] Extend config.yaml with download section
- [ ] Add per-repository download settings
- [ ] Support file pattern filters (include/exclude)
- [ ] Add verification and retry configuration
- [ ] Update configuration validation

### 3.2 Monitor Integration
- [ ] Add optional --download flag to github_monitor.py
- [ ] Modify monitor to trigger downloads when enabled
- [ ] Update output format to include download status
- [ ] Ensure backward compatibility with existing configs
- [ ] Add integration tests

### 3.3 Documentation
- [ ] Update README.md with download feature
- [ ] Add examples/ with download configurations
- [ ] Create DOWNLOAD_GUIDE.md with detailed usage
- [ ] Update CONTRIBUTING.md with download testing info

## Acceptance Criteria
- [ ] Monitor can optionally download releases in single run
- [ ] Configuration is intuitive and well-documented
- [ ] Existing monitor functionality unchanged when download disabled
- [ ] Clear separation between monitoring and downloading logic
- [ ] Examples cover common use cases

## Files to Modify
- `github_monitor.py` (add download integration)
- `config.yaml` (add download schema)
- `README.md` (document download feature)

## Files to Create
- `examples/download-config.yaml`
- `DOWNLOAD_GUIDE.md`
- `tests/integration/test_monitor_download.py`

## Technical Notes
- Use feature flags for gradual rollout
- Maintain separate logs for monitoring vs downloading
- Consider download performance impact on monitoring speed
EOF
)" --label "enhancement,phase-3"
```

## Phase 4: Concourse Pipeline Integration
```bash
gh issue create --title "Phase 4: Concourse Pipeline Integration and Production Readiness" --body "$(cat <<'EOF'
# Phase 4: Concourse Pipeline Integration

## Overview
Complete Concourse pipeline integration and prepare for production deployment.

## Tasks

### 4.1 Concourse Task Creation
- [ ] Create `ci/tasks/download-releases/` directory
- [ ] Implement `task.yml` with proper inputs/outputs
- [ ] Create `task.sh` script for download execution
- [ ] Add parameter documentation
- [ ] Test task in isolation

### 4.2 Pipeline Integration
- [ ] Update `pipeline.yml` with download job
- [ ] Add resource for downloaded artifacts storage
- [ ] Implement proper job dependencies (monitor -> download)
- [ ] Add pipeline parameters for download configuration
- [ ] Test full pipeline flow

### 4.3 Production Readiness
- [ ] Add comprehensive error handling
- [ ] Implement monitoring and alerting
- [ ] Create deployment guide
- [ ] Add operational runbooks
- [ ] Performance testing with large repositories

## Acceptance Criteria
- [ ] Download task runs successfully in Concourse
- [ ] Pipeline properly chains monitor -> download jobs
- [ ] Downloaded artifacts are stored in configured location
- [ ] Failed downloads don't block subsequent runs
- [ ] Pipeline parameters are well-documented
- [ ] Operations team can deploy and maintain

## Files to Create
- `ci/tasks/download-releases/task.yml`
- `ci/tasks/download-releases/task.sh`
- `docs/DEPLOYMENT.md`
- `docs/OPERATIONS.md`

## Files to Modify
- `ci/pipeline.yml` (add download job)
- `params/global.yml` (add download parameters)

## Technical Notes
- Use Concourse resource types for artifact storage
- Consider using S3 or similar for large artifact storage
- Implement health checks for download service
- Plan for scaling with high repository counts
EOF
)" --label "enhancement,phase-4"
```

## Labels to Create First
```bash
# Create the epic label
gh label create "epic" --description "Large feature spanning multiple issues" --color "B60205"

# Create phase labels  
gh label create "phase-1" --description "Phase 1: Core Infrastructure" --color "0E8A16"
gh label create "phase-2" --description "Phase 2: Download Functionality" --color "0E8A16" 
gh label create "phase-3" --description "Phase 3: Integration & Configuration" --color "0E8A16"
gh label create "phase-4" --description "Phase 4: Concourse Pipeline Integration" --color "0E8A16"
```