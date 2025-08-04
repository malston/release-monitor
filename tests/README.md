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
- `test_version_artifactory.py` - Unit tests for Artifactory version storage
- `test_email_notification.py` - Unit tests for email notification functionality
- `test_manifest_downloads.py` - Unit tests for manifest and source download functionality
- `test_target_version_functionality.py` - Comprehensive unit tests for target_version feature
- `test_target_version_integration.py` - Integration tests for target_version functionality

### Integration Tests (tests/integration/)

- `test_artifactory_integration.py` - Integration tests for Artifactory version storage (requires running Artifactory)
- `test_repositories_override_integration.py` - Integration tests for REPOSITORIES_OVERRIDE functionality
- `test_repositories_override_e2e.py` - End-to-end examples and format validation for repository overrides
- `test_integration_download.py` - Integration tests for download workflows
- `test_monitor_download.py` - Integration tests for monitor + download pipeline
- `test_monitor_self.py` - Self-monitoring integration tests
- `test_email_notification_integration.py` - Integration tests for email notifications
- `test_github_monitor_integration.py` - Integration tests for GitHub monitoring
- `test_main_loop_error_handling.py` - Integration tests for error handling scenarios
- `test_manifest_download_integration.py` - Integration tests for manifest downloads
- `test_s3_integration.py` - Integration tests for S3 storage

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
python -m unittest tests.test_target_version_integration.TestTargetVersionConfigurationParsing.test_repository_overrides_environment_variable_parsing -v

# Run specific integration test class
python -m unittest tests.test_target_version_integration.TestTargetVersionEndToEndIntegration -v

# Run integration tests matching a pattern
python -m unittest discover tests/integration -k "repository_override" -v

# Run Artifactory integration test (requires running Artifactory instance)
python -m unittest tests.integration.test_artifactory_integration -v
```

### All Tests

```bash
# Run everything
python -m unittest discover tests -p "test_*.py"

# Run all tests with verbose output
python -m unittest discover tests -p "test_*.py" -v
```

## Common Test Patterns

### Test Isolation

Many tests need to avoid external dependencies like Artifactory or S3. Common patterns include:

1. **Mock environment variables** to prevent external service usage:

    ```python
    self.env_patcher = patch.dict(os.environ, {
        'ARTIFACTORY_URL': '',
        'ARTIFACTORY_REPOSITORY': '',
        'ARTIFACTORY_API_KEY': ''
    }, clear=False)
    self.env_patcher.start()
    ```

1. **Pre-populate version database** to control version comparison behavior:

    ```python
    # Ensure a specific version comparison result
    self.coordinator.version_db.update_version('owner', 'repo', 'v1.0.0', {})
    ```

1. **Use temporary directories** for test isolation:

    ```python
    self.test_dir = tempfile.mkdtemp()
    # Remember to clean up in tearDown()
    ```

## Troubleshooting

### Common Test Failures

1. **"No such file or directory" errors**: Tests may need to create temporary directories. Ensure proper setup/teardown.

2. **Version comparison failures**: When testing version logic, remember that any version is considered "newer" than no stored version (None).

3. **Mock configuration issues**: Ensure mocks are properly configured before the code under test uses them.

### Identifying Skipped Tests

To see which tests are being skipped:

```bash
# Run tests with verbose output and filter for skipped tests
python -m unittest discover tests -p "test_*.py" -v 2>&1 | grep -A1 -B1 "skipped"

# See just the skipped test summary
python -m unittest discover tests -p "test_*.py" -v 2>&1 | tail -3
```

### Running Failed Tests

When a test fails, you can run it individually for easier debugging:

```bash
# Run with maximum verbosity
python -m unittest tests.test_version_compare.TestVersionComparator.test_is_newer_basic -vv

# Run with Python debugger
python -m pdb -m unittest tests.test_version_compare.TestVersionComparator.test_is_newer_basic
```
