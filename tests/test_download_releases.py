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
        """Set up test environment."""
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
        
        self.coordinator = ReleaseDownloadCoordinator(self.config, 'test_token')
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test coordinator initialization."""
        self.assertIsNotNone(self.coordinator.version_db)
        self.assertIsNotNone(self.coordinator.version_comparator)
        self.assertIsNotNone(self.coordinator.downloader)
        self.assertEqual(self.coordinator.asset_patterns, ['*.tar.gz', '*.zip'])
    
    @patch('download_releases.GitHubDownloader.download_release_assets')
    def test_process_single_release_new_version(self, mock_download):
        """Test processing a new release version."""
        # Mock successful download
        mock_download.return_value = [
            {
                'success': True,
                'asset_name': 'release.tar.gz',
                'file_path': '/path/to/release.tar.gz',
                'file_size': 1024,
                'download_time': 1.5
            }
        ]
        
        release = {
            'repository': 'test/repo',
            'tag_name': 'v1.1.0',
            'assets': [
                {
                    'name': 'release.tar.gz',
                    'browser_download_url': 'https://example.com/release.tar.gz'
                }
            ]
        }
        
        result = self.coordinator._process_single_release(release)
        
        self.assertEqual(result['action'], 'downloaded')
        self.assertEqual(result['repository'], 'test/repo')
        self.assertEqual(result['tag_name'], 'v1.1.0')
        self.assertIn('download_results', result)
        self.assertIn('metadata', result)
    
    @patch('download_releases.GitHubDownloader.download_release_assets')
    def test_process_single_release_older_version(self, mock_download):
        """Test processing an older release version."""
        # First, add a newer version to the database
        self.coordinator.version_db.update_version('test', 'repo', 'v2.0.0')
        
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
        
        self.assertEqual(result['action'], 'skipped')
        self.assertIn('not newer than', result['reason'])
        mock_download.assert_not_called()
    
    def test_process_single_release_no_assets(self):
        """Test processing a release with no assets."""
        release = {
            'repository': 'test/repo',
            'tag_name': 'v1.0.0',
            'assets': []
        }
        
        result = self.coordinator._process_single_release(release)
        
        self.assertEqual(result['action'], 'skipped')
        self.assertEqual(result['reason'], 'No downloadable assets')
    
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
    
    @patch('download_releases.GitHubDownloader.download_release_assets')
    def test_process_single_release_download_failure(self, mock_download):
        """Test processing when download fails."""
        # Mock failed download
        mock_download.return_value = [
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
    
    @patch('download_releases.GitHubDownloader.download_release_assets')
    def test_process_monitor_output(self, mock_download):
        """Test processing complete monitor output."""
        # Mock successful downloads
        mock_download.return_value = [
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
    
    @patch('download_releases.GitHubDownloader.download_release_assets')
    def test_process_monitor_output_mixed_results(self, mock_download):
        """Test processing with mixed success/failure results."""
        # Mock mixed download results
        def mock_download_side_effect(release_data, patterns=None):
            repo = release_data.get('repository', '')
            if 'success' in repo:
                return [{'success': True, 'asset_name': 'file.tar.gz', 'file_path': '/path', 'file_size': 1024, 'download_time': 1.0}]
            else:
                return [{'success': False, 'asset_name': 'file.tar.gz', 'error': 'Download failed'}]
        
        mock_download.side_effect = mock_download_side_effect
        
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
        # Create coordinator with pre-releases enabled
        config_with_prereleases = self.config.copy()
        config_with_prereleases['download']['include_prereleases'] = True
        
        coordinator = ReleaseDownloadCoordinator(config_with_prereleases, 'test_token')
        
        with patch('download_releases.GitHubDownloader.download_release_assets') as mock_download:
            mock_download.return_value = [
                {
                    'success': True,
                    'asset_name': 'release.tar.gz',
                    'file_path': '/path/to/release.tar.gz',
                    'file_size': 1024,
                    'download_time': 1.5
                }
            ]
            
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
            
            result = coordinator._process_single_release(release)
            
            self.assertEqual(result['action'], 'downloaded')


if __name__ == '__main__':
    unittest.main()