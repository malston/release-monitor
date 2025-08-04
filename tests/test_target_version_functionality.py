#!/usr/bin/env python3
"""
Comprehensive test suite for target_version functionality.

This test suite ensures that the target_version feature works consistently
across all scenarios including edge cases and error conditions.
"""

import unittest
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from download_releases import ReleaseDownloadCoordinator
from github_version_db import VersionDatabase


class TestTargetVersionFunctionality(unittest.TestCase):
    """Comprehensive tests for target_version functionality."""

    def setUp(self):
        """Set up test environment with mocks and fixtures."""
        self.test_dir = tempfile.mkdtemp()

        # Mock environment variables to prevent Artifactory usage during tests
        self.env_patcher = patch.dict(os.environ, {
            'ARTIFACTORY_URL': '',
            'ARTIFACTORY_REPOSITORY': '',
            'ARTIFACTORY_API_KEY': '',
            'ARTIFACTORY_USERNAME': '',
            'ARTIFACTORY_PASSWORD': ''
        }, clear=False)
        self.env_patcher.start()

        # Create test configuration with target_version repository overrides
        self.config = {
            'download': {
                'enabled': True,
                'directory': self.test_dir,
                'version_db': os.path.join(self.test_dir, 'version_db.json'),
                'asset_patterns': ['*.tar.gz', '*.zip'],
                'repository_overrides': {
                    'target/repo-v1': {
                        'target_version': 'v1.5.0',
                        'asset_patterns': ['*.tar.gz']
                    },
                    'target/repo-v2': {
                        'target_version': 'v2.0.0-beta.1',
                        'asset_patterns': ['*.zip']
                    },
                    'normal/repo': {
                        'asset_patterns': ['*.tar.gz']
                        # No target_version - should use normal version comparison
                    }
                }
            }
        }

        # Initialize coordinator with mocked components
        with patch('download_releases.GitHubDownloader') as mock_downloader_class:
            self.coordinator = ReleaseDownloadCoordinator(self.config, 'fake_token', force_local=True)
            self.mock_downloader = mock_downloader_class.return_value

    def tearDown(self):
        """Clean up test environment."""
        self.env_patcher.stop()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_release_data(self, repository='target/repo-v1', tag_name='v1.5.0',
                           assets=None, prerelease=False):
        """Create mock release data for testing."""
        if assets is None:
            assets = [
                {
                    'name': 'release.tar.gz',
                    'size': 1024,
                    'browser_download_url': f'https://github.com/{repository}/releases/download/{tag_name}/release.tar.gz'
                }
            ]

        return {
            'repository': repository,
            'tag_name': tag_name,
            'name': f'Release {tag_name}',
            'published_at': '2024-01-01T00:00:00Z',
            'prerelease': prerelease,
            'draft': False,
            'assets': assets,
            'tarball_url': f'https://api.github.com/repos/{repository}/tarball/{tag_name}',
            'zipball_url': f'https://api.github.com/repos/{repository}/zipball/{tag_name}'
        }


class TestTargetVersionMatching(TestTargetVersionFunctionality):
    """Test target version exact matching functionality."""

    def test_exact_target_version_match_downloads(self):
        """Test that exact target version match results in download."""
        # Mock successful download
        self.mock_downloader.download_release_content.return_value = [
            {
                'success': True,
                'asset_name': 'release.tar.gz',
                'file_path': f'{self.test_dir}/release.tar.gz',
                'file_size': 1024,
                'download_time': 1.5
            }
        ]

        # Test exact match
        release = self._create_release_data(
            repository='target/repo-v1',
            tag_name='v1.5.0'
        )
        result = self.coordinator._process_single_release(release)

        self.assertEqual(result['action'], 'downloaded')
        self.assertEqual(result['tag_name'], 'v1.5.0')
        self.assertEqual(result['repository'], 'target/repo-v1')

    def test_target_version_mismatch_skips(self):
        """Test that non-matching versions are skipped."""
        # Test cases for different mismatches
        test_cases = [
            ('v1.5.1', 'patch version difference'),
            ('v1.4.0', 'lower version'),
            ('v2.0.0', 'higher version'),
            ('v1.5.0-beta.1', 'prerelease suffix'),
            ('1.5.0', 'missing v prefix'),
            ('v1.5.0-rc1', 'different suffix')
        ]

        for tag_name, description in test_cases:
            with self.subTest(tag_name=tag_name, description=description):
                release = self._create_release_data(
                    repository='target/repo-v1',
                    tag_name=tag_name
                )
                result = self.coordinator._process_single_release(release)

                self.assertEqual(result['action'], 'skipped')
                self.assertIn('does not match target version', result['reason'])
                self.assertIn('v1.5.0', result['reason'])

    def test_prerelease_target_version_matching(self):
        """Test target version matching with prerelease versions."""
        # Mock successful download
        self.mock_downloader.download_release_content.return_value = [
            {
                'success': True,
                'asset_name': 'release.zip',
                'file_path': f'{self.test_dir}/release.zip',
                'file_size': 2048,
                'download_time': 2.0
            }
        ]

        # Test exact prerelease match
        release = self._create_release_data(
            repository='target/repo-v2',
            tag_name='v2.0.0-beta.1',
            assets=[{
                'name': 'release.zip',
                'size': 2048,
                'browser_download_url': 'https://github.com/target/repo-v2/releases/download/v2.0.0-beta.1/release.zip'
            }],
            prerelease=True
        )
        result = self.coordinator._process_single_release(release)

        self.assertEqual(result['action'], 'downloaded')
        self.assertEqual(result['tag_name'], 'v2.0.0-beta.1')

    def test_case_sensitive_matching(self):
        """Test that target version matching is case sensitive."""
        # Different case variations should not match
        test_cases = [
            'V1.5.0',
            'v1.5.0-BETA',
            'v1.5.0-Beta'
        ]

        for tag_name in test_cases:
            with self.subTest(tag_name=tag_name):
                release = self._create_release_data(
                    repository='target/repo-v1',
                    tag_name=tag_name
                )
                result = self.coordinator._process_single_release(release)

                self.assertEqual(result['action'], 'skipped')
                self.assertIn('does not match target version', result['reason'])


class TestTargetVersionBypassesVersionComparison(TestTargetVersionFunctionality):
    """Test that target version bypasses normal version comparison logic."""

    def test_target_version_downloads_older_version(self):
        """Test target version downloads older version than stored."""
        # Store a newer version in database
        self.coordinator.version_db.update_version('target', 'repo-v1', 'v2.0.0')

        # Mock successful download
        self.mock_downloader.download_release_content.return_value = [
            {
                'success': True,
                'asset_name': 'release.tar.gz',
                'file_path': f'{self.test_dir}/release.tar.gz',
                'file_size': 1024,
                'download_time': 1.5
            }
        ]

        # Target version v1.5.0 should download despite v2.0.0 being stored
        release = self._create_release_data(
            repository='target/repo-v1',
            tag_name='v1.5.0'
        )
        result = self.coordinator._process_single_release(release)

        self.assertEqual(result['action'], 'downloaded')
        self.assertEqual(result['previous_version'], 'v2.0.0')
        self.assertEqual(result['tag_name'], 'v1.5.0')

    def test_target_version_downloads_same_version(self):
        """Test target version downloads same version as stored."""
        # Store the same version in database
        self.coordinator.version_db.update_version('target', 'repo-v1', 'v1.5.0')

        # Mock successful download
        self.mock_downloader.download_release_content.return_value = [
            {
                'success': True,
                'asset_name': 'release.tar.gz',
                'file_path': f'{self.test_dir}/release.tar.gz',
                'file_size': 1024,
                'download_time': 1.5
            }
        ]

        # Target version should still download even if it's the same as stored
        release = self._create_release_data(
            repository='target/repo-v1',
            tag_name='v1.5.0'
        )
        result = self.coordinator._process_single_release(release)

        self.assertEqual(result['action'], 'downloaded')
        self.assertEqual(result['previous_version'], 'v1.5.0')

    def test_normal_repo_uses_version_comparison(self):
        """Test that repos without target_version use normal version comparison."""
        # Store a version in database for normal repo
        self.coordinator.version_db.update_version('normal', 'repo', 'v2.0.0')

        # Try to download an older version - should be skipped
        release = self._create_release_data(
            repository='normal/repo',
            tag_name='v1.5.0'
        )
        result = self.coordinator._process_single_release(release)

        self.assertEqual(result['action'], 'skipped')
        self.assertIn('is not newer than', result['reason'])
        self.assertIn('v2.0.0', result['reason'])

    def test_prerelease_filtering_bypassed_with_target_version(self):
        """Test that prerelease filtering is bypassed when target version is set."""
        # Configure coordinator to exclude prereleases normally
        self.coordinator.version_comparator.include_prereleases = False

        # Mock successful download
        self.mock_downloader.download_release_content.return_value = [
            {
                'success': True,
                'asset_name': 'release.zip',
                'file_path': f'{self.test_dir}/release.zip',
                'file_size': 2048,
                'download_time': 2.0
            }
        ]

        # Target version that is a prerelease should still download
        release = self._create_release_data(
            repository='target/repo-v2',
            tag_name='v2.0.0-beta.1',
            assets=[{
                'name': 'release.zip',
                'size': 2048,
                'browser_download_url': 'https://github.com/target/repo-v2/releases/download/v2.0.0-beta.1/release.zip'
            }],
            prerelease=True
        )
        result = self.coordinator._process_single_release(release)

        self.assertEqual(result['action'], 'downloaded')


class TestTargetVersionAssetHandling(TestTargetVersionFunctionality):
    """Test asset patterns and download behavior with target versions."""

    def test_target_version_respects_asset_patterns(self):
        """Test that target version still respects repository-specific asset patterns."""
        # Mock downloader to return empty results (no matching assets)
        self.mock_downloader.download_release_content.return_value = []

        # Release with assets that don't match the pattern for target/repo-v1 (which expects *.tar.gz)
        release = self._create_release_data(
            repository='target/repo-v1',
            tag_name='v1.5.0',
            assets=[{
                'name': 'release.zip',  # This doesn't match *.tar.gz pattern
                'size': 1024,
                'browser_download_url': 'https://github.com/target/repo-v1/releases/download/v1.5.0/release.zip'
            }]
        )
        result = self.coordinator._process_single_release(release)

        # Should attempt download but fail due to no matching assets
        self.assertEqual(result['action'], 'failed')
        self.assertIn('All asset downloads failed', result['reason'])

    def test_target_version_with_source_archives(self):
        """Test target version downloads source archives when no assets match."""
        # Mock downloader to return source archive download
        self.mock_downloader.download_release_content.return_value = [
            {
                'success': True,
                'asset_name': 'target_repo-v1-v1.5.0.tar.gz',
                'file_path': f'{self.test_dir}/source.tar.gz',
                'file_size': 5000,
                'download_time': 3.0,
                'source_type': 'tarball'
            }
        ]

        # Release with no assets - should fall back to source archive
        release = self._create_release_data(
            repository='target/repo-v1',
            tag_name='v1.5.0',
            assets=[]
        )
        result = self.coordinator._process_single_release(release)

        self.assertEqual(result['action'], 'downloaded')
        self.assertEqual(len(result['download_results']), 1)
        self.assertIn('source_type', result['download_results'][0])

    def test_target_version_with_multiple_assets(self):
        """Test target version with multiple matching assets."""
        # Mock downloader to return multiple successful downloads
        self.mock_downloader.download_release_content.return_value = [
            {
                'success': True,
                'asset_name': 'linux.tar.gz',
                'file_path': f'{self.test_dir}/linux.tar.gz',
                'file_size': 1024,
                'download_time': 1.0
            },
            {
                'success': True,
                'asset_name': 'darwin.tar.gz',
                'file_path': f'{self.test_dir}/darwin.tar.gz',
                'file_size': 1024,
                'download_time': 1.0
            }
        ]

        # Release with multiple assets that match pattern
        release = self._create_release_data(
            repository='target/repo-v1',
            tag_name='v1.5.0',
            assets=[
                {'name': 'linux.tar.gz', 'size': 1024, 'browser_download_url': 'http://example.com/linux.tar.gz'},
                {'name': 'darwin.tar.gz', 'size': 1024, 'browser_download_url': 'http://example.com/darwin.tar.gz'},
                {'name': 'windows.zip', 'size': 1024, 'browser_download_url': 'http://example.com/windows.zip'}  # Should be filtered out
            ]
        )
        result = self.coordinator._process_single_release(release)

        self.assertEqual(result['action'], 'downloaded')
        self.assertEqual(result['metadata']['download_count'], 2)


class TestTargetVersionErrorConditions(TestTargetVersionFunctionality):
    """Test error conditions and edge cases for target version functionality."""

    def test_target_version_empty_string(self):
        """Test behavior with empty string target version."""
        # Pre-populate version database so v1.5.0 won't be considered newer
        self.coordinator.version_db.update_version('target', 'repo-v1', 'v1.5.0', {})

        # Modify configuration to have empty target version
        self.coordinator.repository_overrides['target/repo-v1']['target_version'] = ''

        release = self._create_release_data(
            repository='target/repo-v1',
            tag_name='v1.5.0'
        )
        result = self.coordinator._process_single_release(release)

        # Empty target version should be treated as no target version
        # Should fall back to normal version comparison
        self.assertEqual(result['action'], 'skipped')
        self.assertIn('is not newer than', result['reason'])

    def test_target_version_none_value(self):
        """Test behavior with None target version."""
        # Pre-populate version database so v1.5.0 won't be considered newer
        self.coordinator.version_db.update_version('target', 'repo-v1', 'v1.5.0', {})

        # Modify configuration to have None target version
        self.coordinator.repository_overrides['target/repo-v1']['target_version'] = None

        release = self._create_release_data(
            repository='target/repo-v1',
            tag_name='v1.5.0'
        )
        result = self.coordinator._process_single_release(release)

        # None target version should be treated as no target version
        self.assertEqual(result['action'], 'skipped')
        self.assertIn('is not newer than', result['reason'])

    def test_target_version_with_invalid_repository_format(self):
        """Test target version with invalid repository format."""
        release = {
            'repository': 'invalid-format',  # Missing owner/repo format
            'tag_name': 'v1.5.0',
            'assets': []
        }
        result = self.coordinator._process_single_release(release)

        self.assertEqual(result['action'], 'failed')
        self.assertIn('Invalid repository format', result['reason'])

    def test_target_version_download_failure(self):
        """Test target version when download fails."""
        # Mock downloader to return failed download
        self.mock_downloader.download_release_content.return_value = [
            {
                'success': False,
                'asset_name': 'release.tar.gz',
                'error': 'Network timeout'
            }
        ]

        release = self._create_release_data(
            repository='target/repo-v1',
            tag_name='v1.5.0'
        )
        result = self.coordinator._process_single_release(release)

        self.assertEqual(result['action'], 'failed')
        self.assertIn('All asset downloads failed', result['reason'])

    def test_target_version_with_no_downloadable_content(self):
        """Test target version when release has no downloadable content."""
        release = self._create_release_data(
            repository='target/repo-v1',
            tag_name='v1.5.0',
            assets=[]
        )
        # Remove source archive URLs
        release['tarball_url'] = None
        release['zipball_url'] = None

        result = self.coordinator._process_single_release(release)

        self.assertEqual(result['action'], 'skipped')
        self.assertIn('No downloadable content', result['reason'])


class TestTargetVersionIntegration(TestTargetVersionFunctionality):
    """Integration tests for target version functionality."""

    def test_process_monitor_output_with_target_versions(self):
        """Test processing monitor output with mixed target version and normal repos."""
        # Mock successful downloads for target version repos
        def mock_download_side_effect(release, asset_patterns, source_config):
            if release['repository'] in ['target/repo-v1', 'target/repo-v2']:
                return [
                    {
                        'success': True,
                        'asset_name': f"{release['repository'].replace('/', '_')}-{release['tag_name']}.tar.gz",
                        'file_path': f"{self.test_dir}/{release['tag_name']}.tar.gz",
                        'file_size': 1024,
                        'download_time': 1.5
                    }
                ]
            return []  # No downloads for other repos

        self.mock_downloader.download_release_content.side_effect = mock_download_side_effect

        # Create monitor output with mixed repositories
        monitor_output = {
            'timestamp': '2024-01-01T00:00:00Z',
            'new_releases_found': 4,
            'releases': [
                self._create_release_data('target/repo-v1', 'v1.5.0'),      # Should download (matches target)
                self._create_release_data('target/repo-v1', 'v1.6.0'),      # Should skip (doesn't match target)
                self._create_release_data('target/repo-v2', 'v2.0.0-beta.1'),  # Should download (matches target)
                self._create_release_data('normal/repo', 'v1.0.0')          # Should download (no stored version)
            ]
        }

        results = self.coordinator.process_monitor_output(monitor_output)

        # Verify results
        self.assertEqual(results['total_releases_checked'], 4)
        self.assertEqual(results['new_downloads'], 2)  # target/repo-v1 v1.5.0 and target/repo-v2 v2.0.0-beta.1
        self.assertEqual(results['skipped_releases'], 1)  # target/repo-v1 v1.6.0 (doesn't match target)
        self.assertEqual(results['failed_downloads'], 1)  # normal/repo v1.0.0 (no successful downloads)

        # Verify specific results
        download_results = results['download_results']
        downloaded_repos = [r for r in download_results if r['action'] == 'downloaded']
        skipped_repos = [r for r in download_results if r['action'] == 'skipped']
        failed_repos = [r for r in download_results if r['action'] == 'failed']

        self.assertEqual(len(downloaded_repos), 2)
        self.assertEqual(len(skipped_repos), 1)
        self.assertEqual(len(failed_repos), 1)

        # Check that target versions were downloaded
        target_v1_result = next(r for r in downloaded_repos if r['repository'] == 'target/repo-v1')
        self.assertEqual(target_v1_result['tag_name'], 'v1.5.0')

        target_v2_result = next(r for r in downloaded_repos if r['repository'] == 'target/repo-v2')
        self.assertEqual(target_v2_result['tag_name'], 'v2.0.0-beta.1')

    def test_version_database_update_with_target_version(self):
        """Test that version database is updated correctly when using target versions."""
        # Mock successful download
        self.mock_downloader.download_release_content.return_value = [
            {
                'success': True,
                'asset_name': 'release.tar.gz',
                'file_path': f'{self.test_dir}/release.tar.gz',
                'file_size': 1024,
                'download_time': 1.5
            }
        ]

        # Store newer version first
        self.coordinator.version_db.update_version('target', 'repo-v1', 'v2.0.0')

        # Verify initial state
        current_version = self.coordinator.version_db.get_current_version('target', 'repo-v1')
        self.assertEqual(current_version, 'v2.0.0')

        # Process target version (older)
        release = self._create_release_data('target/repo-v1', 'v1.5.0')
        result = self.coordinator._process_single_release(release)

        self.assertEqual(result['action'], 'downloaded')

        # Verify version database was updated to target version
        updated_version = self.coordinator.version_db.get_current_version('target', 'repo-v1')
        self.assertEqual(updated_version, 'v1.5.0')

        # Verify download history contains both versions
        history = self.coordinator.version_db.get_download_history('target', 'repo-v1')
        self.assertGreaterEqual(len(history), 2)
        self.assertEqual(history[0]['version'], 'v1.5.0')  # Most recent first


class TestRepositoryOverridesConfigurationHandling(TestTargetVersionFunctionality):
    """Test configuration handling and parsing of repository overrides."""

    def test_repository_overrides_loading(self):
        """Test that repository overrides are loaded correctly."""
        # Verify repository overrides were loaded
        self.assertIn('target/repo-v1', self.coordinator.repository_overrides)
        self.assertIn('target/repo-v2', self.coordinator.repository_overrides)
        self.assertIn('normal/repo', self.coordinator.repository_overrides)

        # Verify target versions
        self.assertEqual(
            self.coordinator.repository_overrides['target/repo-v1']['target_version'],
            'v1.5.0'
        )
        self.assertEqual(
            self.coordinator.repository_overrides['target/repo-v2']['target_version'],
            'v2.0.0-beta.1'
        )
        self.assertNotIn(
            'target_version',
            self.coordinator.repository_overrides['normal/repo']
        )

    def test_get_repository_config_with_target_version(self):
        """Test _get_repository_config method with target versions."""
        # Test repository with target version
        config = self.coordinator._get_repository_config('target/repo-v1')
        self.assertEqual(config['asset_patterns'], ['*.tar.gz'])

        # Test repository without target version
        config = self.coordinator._get_repository_config('normal/repo')
        self.assertEqual(config['asset_patterns'], ['*.tar.gz'])

        # Test non-existent repository (should return defaults)
        config = self.coordinator._get_repository_config('nonexistent/repo')
        self.assertEqual(config['asset_patterns'], ['*.tar.gz', '*.zip'])  # Global default

    def test_empty_repository_overrides(self):
        """Test behavior with empty repository overrides."""
        # Create coordinator with no repository overrides
        config_no_overrides = {
            'download': {
                'enabled': True,
                'directory': self.test_dir,
                'version_db': os.path.join(self.test_dir, 'version_db.json'),
                'asset_patterns': ['*.tar.gz'],
                'repository_overrides': {}
            }
        }

        with patch('download_releases.GitHubDownloader') as mock_downloader_class:
            coordinator = ReleaseDownloadCoordinator(config_no_overrides, 'fake_token', force_local=True)
            mock_downloader = mock_downloader_class.return_value

            # Pre-populate version database so v1.0.0 won't be considered newer
            coordinator.version_db.update_version('any', 'repo', 'v1.0.0', {})

        # Should work normally without target versions
        release = self._create_release_data('any/repo', 'v1.0.0')
        result = coordinator._process_single_release(release)

        # Should skip because v1.0.0 is not newer than stored v1.0.0
        self.assertEqual(result['action'], 'skipped')
        self.assertIn('is not newer than', result['reason'])


if __name__ == '__main__':
    # Run with verbose output to see all test details
    unittest.main(verbosity=2)
