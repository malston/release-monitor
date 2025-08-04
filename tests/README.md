# Test Organization

This directory contains the test suite for the GitHub Release Monitor.

## Structure

### Unit Tests (tests/)

- `test_github_monitor.py` - Unit tests for GitHubMonitor class and configuration loading
- `test_download_releases.py` - Unit tests for download coordination
- `test_downloader.py` - Unit tests for GitHub downloader
- `test_version_compare.py` - Unit tests for version comparison logic
- `test_version_db.py` - Unit tests for local version database
- `test_version_s3.py` - Unit tests for S3 version storage
- `test_main_loop_error_handling.py` - Unit tests for error handling

### Integration Tests (tests/integration/)

- `test_repositories_override_integration.py` - Integration tests for REPOSITORIES_OVERRIDE functionality
- `test_repositories_override_e2e.py` - End-to-end examples and format validation for repository overrides
- `test_integration_download.py` - Integration tests for download workflows
- `test_monitor_download.py` - Integration tests for monitor + download pipeline
- `test_monitor_self.py` - Self-monitoring integration tests

## Running Tests

### Unit Tests

```bash
# Run all unit tests
python -m unittest discover tests -p "test_*.py"

# Run specific test file
python -m unittest tests.test_github_monitor

# Run specific test method
python -m unittest tests.test_download_releases.TestReleaseDownloadCoordinator.test_target_version_empty_or_none_fallback -v

# Run specific test class
python -m unittest tests.test_target_version_integration.TestTargetVersionLoggingAndDebugging -v

# Run tests matching a pattern
python -m unittest discover tests -k "target_version" -v
```

### Integration Tests

```bash
# Run all integration tests
python -m unittest discover tests/integration -p "test_*.py"

# Run specific integration test file
python -m unittest tests.integration.test_repositories_override_integration

# Run specific integration test method
python -m unittest tests.integration.test_target_version_integration.TestTargetVersionConfigurationParsing.test_repository_overrides_environment_variable_parsing -v

# Run specific integration test class
python -m unittest tests.integration.test_target_version_integration.TestTargetVersionEndToEndIntegration -v

# Run integration tests matching a pattern
python -m unittest discover tests/integration -k "repository_override" -v
```

### All Tests

```bash
# Run everything
python -m unittest discover tests -p "test_*.py"
```
