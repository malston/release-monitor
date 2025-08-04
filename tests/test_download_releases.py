#!/usr/bin/env python3
"""
Unit tests for Download Releases Script
"""

import unittest
import tempfile
import os
import json
from unittest.mock import patch, Mock
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from download_releases import ReleaseDownloadCoordinator


class TestReleaseDownloadCoordinator(unittest.TestCase):

    def setUp(self):
        """Set up test environment with proper mocks and fixtures."""
        self.temp_dir = tempfile.mkdtemp()

        # Create test configuration
        self.config = {
            'download': {
                'directory': os.path.join(self.temp_dir, 'downloads'),
                'version_db': os.path.join(self.temp_dir, 'versions.json'),
                'include_prereleases': False,
                'asset_patterns': ['*.tar.gz', '*.zip'],
                'verify_downloads': True,
                'cleanup_old_versions': False,
                'keep_versions': 5
            }
        }

        # Mock environment variables to prevent Artifactory usage
        self.env_patcher = patch.dict(os.environ, {
            'ARTIFACTORY_URL': '',
            'ARTIFACTORY_REPOSITORY': '',
            'ARTIFACTORY_API_KEY': '',
            'ARTIFACTORY_USERNAME': '',
            'ARTIFACTORY_PASSWORD': ''
        }, clear=False)
        self.env_patcher.start()

        # Mock GitHubDownloader to avoid network initialization
        self.downloader_patcher = patch('download_releases.GitHubDownloader')
        mock_downloader_class = self.downloader_patcher.start()
        mock_downloader = Mock()
        mock_downloader_class.return_value = mock_downloader

        self.coordinator = ReleaseDownloadCoordinator(self.config, 'test_token')
        self.mock_downloader = mock_downloader

    def tearDown(self):
        """Clean up test environment."""
        # Stop all patchers
        self.env_patcher.stop()
        self.downloader_patcher.stop()

        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir)

    def _create_release_data(self, repository='test/repo', tag_name='v1.0.0',
                           has_assets=True, has_source=True, prerelease=False, assets=None):
        """Helper method to create properly formatted release data with all required fields."""
        if assets is None:
            assets = [
                {
                    'name': 'release.tar.gz',
                    'browser_download_url': f'https://example.com/{tag_name}/release.tar.gz'
                }
            ] if has_assets else []

        release_data = {
            'repository': repository,
            'tag_name': tag_name,
            'assets': assets,
            'prerelease': prerelease
        }

        # Add source URLs if requested
        if has_source:
            release_data['tarball_url'] = f'https://api.github.com/repos/{repository}/tarball/{tag_name}'
            release_data['zipball_url'] = f'https://api.github.com/repos/{repository}/zipball/{tag_name}'

        return release_data

    def test_initialization(self):
        """Test coordinator initialization."""
        self.assertIsNotNone(self.coordinator.version_db)
        self.assertIsNotNone(self.coordinator.version_comparator)
        # Verify downloader was mocked
        self.assertEqual(self.coordinator.downloader, self.mock_downloader)
        self.assertEqual(self.coordinator.asset_patterns, ['*.tar.gz', '*.zip'])

    def test_process_single_release_new_version(self):
        """Test processing a new release version."""
        # Mock successful download
        self.mock_downloader.download_release_content.return_value = [
            {
                'success': True,
                'asset_name': 'release.tar.gz',
                'file_path': '/path/to/release.tar.gz',
                'file_size': 1024,
                'download_time': 1.5
            }
        ]

        release = self._create_release_data(tag_name='v1.1.0')

        result = self.coordinator._process_single_release(release)

        self.assertEqual(result['action'], 'downloaded')
        self.assertEqual(result['repository'], 'test/repo')
        self.assertEqual(result['tag_name'], 'v1.1.0')
        self.assertIn('download_results', result)
        self.assertIn('metadata', result)

    def test_process_single_release_older_version(self):
        """Test processing an older release version."""
        # First, add a newer version to the database
        self.coordinator.version_db.update_version('test', 'repo', 'v2.0.0')

        release = self._create_release_data(tag_name='v1.0.0')

        result = self.coordinator._process_single_release(release)

        self.assertEqual(result['action'], 'skipped')
        self.assertIn('not newer than', result['reason'])
        self.mock_downloader.download_release_content.assert_not_called()

    def test_process_single_release_no_assets(self):
        """Test processing a release with no assets."""
        release = self._create_release_data(tag_name='v1.0.0', has_assets=False, has_source=False)

        result = self.coordinator._process_single_release(release)

        self.assertEqual(result['action'], 'skipped')
        self.assertEqual(result['reason'], 'No downloadable content (no assets or source archives)')

    def test_process_single_release_invalid_repository(self):
        """Test processing a release with invalid repository format."""
        release = {
            'repository': 'invalid-repo-name',
            'tag_name': 'v1.0.0',
            'assets': []
        }

        result = self.coordinator._process_single_release(release)

        self.assertEqual(result['action'], 'failed')
        self.assertEqual(result['reason'], 'Invalid repository format')

    def test_process_single_release_download_failure(self):
        """Test processing when download fails."""
        # Mock failed download
        self.mock_downloader.download_release_content.return_value = [
            {
                'success': False,
                'asset_name': 'release.tar.gz',
                'error': 'Network error'
            }
        ]

        release = {
            'repository': 'test/repo',
            'tag_name': 'v1.0.0',
            'assets': [
                {
                    'name': 'release.tar.gz',
                    'browser_download_url': 'https://example.com/release.tar.gz'
                }
            ]
        }

        result = self.coordinator._process_single_release(release)

        self.assertEqual(result['action'], 'failed')
        self.assertEqual(result['reason'], 'All asset downloads failed')

    def test_process_monitor_output(self):
        """Test processing complete monitor output."""
        # Mock successful downloads
        self.mock_downloader.download_release_content.return_value = [
            {
                'success': True,
                'asset_name': 'release.tar.gz',
                'file_path': '/path/to/release.tar.gz',
                'file_size': 1024,
                'download_time': 1.5
            }
        ]

        monitor_output = {
            'releases': [
                {
                    'repository': 'test/repo1',
                    'tag_name': 'v1.0.0',
                    'assets': [
                        {
                            'name': 'release.tar.gz',
                            'browser_download_url': 'https://example.com/release.tar.gz'
                        }
                    ]
                },
                {
                    'repository': 'test/repo2',
                    'tag_name': 'v2.0.0',
                    'assets': [
                        {
                            'name': 'app.zip',
                            'browser_download_url': 'https://example.com/app.zip'
                        }
                    ]
                }
            ]
        }

        results = self.coordinator.process_monitor_output(monitor_output)

        self.assertEqual(results['total_releases_checked'], 2)
        self.assertEqual(results['new_downloads'], 2)
        self.assertEqual(results['skipped_releases'], 0)
        self.assertEqual(results['failed_downloads'], 0)
        self.assertEqual(len(results['download_results']), 2)

    def test_process_monitor_output_empty(self):
        """Test processing empty monitor output."""
        monitor_output = {'releases': []}

        results = self.coordinator.process_monitor_output(monitor_output)

        self.assertEqual(results['total_releases_checked'], 0)
        self.assertEqual(results['new_downloads'], 0)
        self.assertEqual(len(results['download_results']), 0)

    def test_process_monitor_output_no_releases_key(self):
        """Test processing monitor output without releases key."""
        monitor_output = {}

        results = self.coordinator.process_monitor_output(monitor_output)

        self.assertEqual(results['total_releases_checked'], 0)
        self.assertEqual(results['new_downloads'], 0)

    def test_process_monitor_output_mixed_results(self):
        """Test processing with mixed success/failure results."""
        # Mock mixed download results
        def mock_download_side_effect(release_data, patterns=None, source_config=None):
            repo = release_data.get('repository', '')
            if 'success' in repo:
                return [{'success': True, 'asset_name': 'file.tar.gz', 'file_path': '/path', 'file_size': 1024, 'download_time': 1.0}]
            else:
                return [{'success': False, 'asset_name': 'file.tar.gz', 'error': 'Download failed'}]

        self.mock_downloader.download_release_content.side_effect = mock_download_side_effect

        monitor_output = {
            'releases': [
                {
                    'repository': 'test/success-repo',
                    'tag_name': 'v1.0.0',
                    'assets': [{'name': 'file.tar.gz', 'browser_download_url': 'https://example.com/file.tar.gz'}]
                },
                {
                    'repository': 'test/fail-repo',
                    'tag_name': 'v1.0.0',
                    'assets': [{'name': 'file.tar.gz', 'browser_download_url': 'https://example.com/file.tar.gz'}]
                },
                {
                    'repository': 'test/no-assets',
                    'tag_name': 'v1.0.0',
                    'assets': []
                }
            ]
        }

        results = self.coordinator.process_monitor_output(monitor_output)

        self.assertEqual(results['total_releases_checked'], 3)
        self.assertEqual(results['new_downloads'], 1)
        self.assertEqual(results['skipped_releases'], 1)  # no assets
        self.assertEqual(results['failed_downloads'], 1)

    def test_get_status_report(self):
        """Test status report generation."""
        # Add some data to the database
        self.coordinator.version_db.update_version('test', 'repo', 'v1.0.0')

        status = self.coordinator.get_status_report()

        self.assertIn('database_stats', status)
        self.assertIn('download_stats', status)
        self.assertIn('config', status)

        # Check config values
        config = status['config']
        self.assertIn('download_directory', config)
        self.assertEqual(config['asset_patterns'], ['*.tar.gz', '*.zip'])
        self.assertFalse(config['include_prereleases'])

    def test_prerelease_handling(self):
        """Test pre-release version handling."""
        # Test with pre-releases disabled (default)
        release = {
            'repository': 'test/repo',
            'tag_name': 'v1.0.0-alpha.1',
            'assets': [
                {
                    'name': 'release.tar.gz',
                    'browser_download_url': 'https://example.com/release.tar.gz'
                }
            ]
        }

        result = self.coordinator._process_single_release(release)

        self.assertEqual(result['action'], 'skipped')
        self.assertIn('not newer than', result['reason'])

    def test_prerelease_handling_enabled(self):
        """Test pre-release handling when enabled."""
        # Create fresh temp directory and config for this test
        import tempfile
        fresh_temp_dir = tempfile.mkdtemp()

        config_with_prereleases = {
            'download': {
                'directory': os.path.join(fresh_temp_dir, 'downloads'),
                'version_db': os.path.join(fresh_temp_dir, 'versions.json'),
                'include_prereleases': True,
                'asset_patterns': ['*.tar.gz', '*.zip'],
                'verify_downloads': True,
                'cleanup_old_versions': False,
                'keep_versions': 5
            }
        }

        with patch('download_releases.GitHubDownloader') as mock_downloader_class, \
             patch.dict(os.environ, {'ARTIFACTORY_URL': '', 'ARTIFACTORY_REPOSITORY': ''}, clear=False):
            mock_downloader = Mock()
            mock_downloader_class.return_value = mock_downloader

            coordinator = ReleaseDownloadCoordinator(config_with_prereleases, 'test_token')

            mock_downloader.download_release_content.return_value = [
                {
                    'success': True,
                    'asset_name': 'release.tar.gz',
                    'file_path': '/path/to/release.tar.gz',
                    'file_size': 1024,
                    'download_time': 1.5
                }
            ]

            release = self._create_release_data(tag_name='v1.0.0-alpha.1', prerelease=True)

            result = coordinator._process_single_release(release)

            self.assertEqual(result['action'], 'downloaded')

        # Clean up fresh temp directory
        import shutil
        shutil.rmtree(fresh_temp_dir)

    def test_target_version_matching(self):
        """Test target version matching logic."""
        # Set up repository override with target version
        self.coordinator.repository_overrides = {
            'test/repo': {
                'target_version': 'v1.5.0',
                'asset_patterns': ['*.tar.gz']
            }
        }

        # Mock successful download
        self.mock_downloader.download_release_content.return_value = [
            {
                'success': True,
                'asset_name': 'release.tar.gz',
                'file_path': '/path/to/release.tar.gz',
                'file_size': 1024,
                'download_time': 1.5
            }
        ]

        # Test 1: Release matches target version (should download)
        matching_release = self._create_release_data(tag_name='v1.5.0')
        result1 = self.coordinator._process_single_release(matching_release)
        self.assertEqual(result1['action'], 'downloaded')

        # Test 2: Release doesn't match target version (should skip)
        non_matching_release = self._create_release_data(tag_name='v1.6.0')
        result2 = self.coordinator._process_single_release(non_matching_release)
        self.assertEqual(result2['action'], 'skipped')
        self.assertIn('does not match target version', result2['reason'])

    def test_target_version_bypass_version_comparison(self):
        """Test that target version bypasses normal version comparison."""
        # Add an existing newer version to database
        self.coordinator.version_db.update_version('test', 'repo', 'v2.0.0')

        # Set up repository override with target version for older version
        self.coordinator.repository_overrides = {
            'test/repo': {
                'target_version': 'v1.5.0',
                'asset_patterns': ['*.tar.gz']
            }
        }

        # Mock successful download
        self.mock_downloader.download_release_content.return_value = [
            {
                'success': True,
                'asset_name': 'release.tar.gz',
                'file_path': '/path/to/release.tar.gz',
                'file_size': 1024,
                'download_time': 1.5
            }
        ]

        # Target version should download even though it's older than stored version
        target_release = self._create_release_data(tag_name='v1.5.0')
        result = self.coordinator._process_single_release(target_release)
        self.assertEqual(result['action'], 'downloaded')


if __name__ == '__main__':
    unittest.main()
