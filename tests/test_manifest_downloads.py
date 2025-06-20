#!/usr/bin/env python3
"""
Test suite for manifest and source code download functionality.
Tests the enhanced download system with repositories like wavefrontHQ/observability-for-kubernetes.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import tempfile
import shutil
from pathlib import Path
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from download_releases import ReleaseDownloadCoordinator
from github_downloader import GitHubDownloader


class TestManifestDownloads(unittest.TestCase):
    """Test manifest and source code download functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            'download': {
                'enabled': True,
                'directory': self.test_dir,
                'asset_patterns': ['*.yaml', '*.yml', '*.json'],
                'source_archives': {
                    'enabled': True,
                    'prefer': 'tarball',
                    'fallback_only': True
                },
                'repository_overrides': {
                    'wavefrontHQ/observability-for-kubernetes': {
                        'asset_patterns': ['*.yaml', '*.yml'],
                        'source_archives': {
                            'fallback_only': False,
                            'prefer': 'tarball'
                        }
                    }
                }
            }
        }
        
    def tearDown(self):
        """Clean up test directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def create_wavefront_release(self):
        """Create mock wavefront release data."""
        return {
            'repository': 'wavefrontHQ/observability-for-kubernetes',
            'owner': 'wavefrontHQ',
            'repo': 'observability-for-kubernetes',
            'tag_name': 'v2.30.0',
            'name': 'Release v2.30.0',
            'published_at': '2025-06-18T15:11:45Z',
            'tarball_url': 'https://api.github.com/repos/wavefrontHQ/observability-for-kubernetes/tarball/v2.30.0',
            'zipball_url': 'https://api.github.com/repos/wavefrontHQ/observability-for-kubernetes/zipball/v2.30.0',
            'html_url': 'https://github.com/wavefrontHQ/observability-for-kubernetes/releases/tag/v2.30.0',
            'prerelease': False,
            'draft': False,
            'assets': [
                {
                    'id': 265114418,
                    'name': 'wavefront-operator.yaml',
                    'size': 56535,
                    'browser_download_url': 'https://github.com/wavefrontHQ/observability-for-kubernetes/releases/download/v2.30.0/wavefront-operator.yaml',
                    'content_type': 'application/octet-stream'
                }
            ]
        }
    
    def test_repository_config_override(self):
        """Test that repository-specific configuration is properly applied."""
        with patch('download_releases.VersionDatabase'), \
             patch('download_releases.GitHubDownloader'):
            
            coordinator = ReleaseDownloadCoordinator(self.config, 'fake_token')
            
            # Test wavefront repo config
            repo_config = coordinator._get_repository_config('wavefrontHQ/observability-for-kubernetes')
            
            self.assertEqual(repo_config['asset_patterns'], ['*.yaml', '*.yml'])
            self.assertEqual(repo_config['source_archives']['fallback_only'], False)
            self.assertEqual(repo_config['source_archives']['prefer'], 'tarball')
            
            # Test default repo config
            default_config = coordinator._get_repository_config('some/other-repo')
            self.assertEqual(default_config['asset_patterns'], ['*.yaml', '*.yml', '*.json'])
            self.assertEqual(default_config['source_archives']['fallback_only'], True)
    
    def test_download_content_with_assets_and_source(self):
        """Test downloading both assets and source archives."""
        downloader = GitHubDownloader('fake_token', download_dir=self.test_dir)
        
        # Mock the download methods
        mock_asset_results = [
            {
                'asset_name': 'wavefront-operator.yaml',
                'success': True,
                'file_path': f'{self.test_dir}/wavefront-operator.yaml'
            }
        ]
        
        mock_source_results = [
            {
                'asset_name': 'wavefrontHQ_observability-for-kubernetes-v2.30.0.tar.gz',
                'success': True,
                'source_type': 'tarball',
                'file_path': f'{self.test_dir}/source.tar.gz'
            }
        ]
        
        with patch.object(downloader, 'download_release_assets', return_value=mock_asset_results), \
             patch.object(downloader, 'download_source_archives', return_value=mock_source_results), \
             patch.object(downloader, '_should_download_source', return_value=True):
            
            release_data = self.create_wavefront_release()
            results = downloader.download_release_content(
                release_data,
                asset_patterns=['*.yaml', '*.yml'],
                source_config={'enabled': True, 'fallback_only': False}
            )
            
            # Should have both asset and source results
            self.assertEqual(len(results), 2)
            self.assertTrue(any(r['asset_name'] == 'wavefront-operator.yaml' for r in results))
            self.assertTrue(any('source_type' in r for r in results))
    
    def test_should_download_source_logic(self):
        """Test the logic for determining when to download source archives."""
        downloader = GitHubDownloader('fake_token')
        
        # Test 1: fallback_only=False should always return True
        self.assertTrue(
            downloader._should_download_source(
                {}, ['*.yaml'], [], {'fallback_only': False}
            )
        )
        
        # Test 2: No assets downloaded, should download source
        self.assertTrue(
            downloader._should_download_source(
                {}, ['*.yaml'], [], {'fallback_only': True}
            )
        )
        
        # Test 3: Assets downloaded successfully, fallback_only=True, should not download source
        successful_assets = [{'success': True}]
        self.assertFalse(
            downloader._should_download_source(
                {}, ['*.yaml'], successful_assets, {'fallback_only': True}
            )
        )
        
        # Test 4: Looking for manifests but none found
        failed_assets = [{'success': False}]
        self.assertTrue(
            downloader._should_download_source(
                {}, ['*.yaml', '*.yml'], failed_assets, {'fallback_only': True}
            )
        )
    
    def test_process_wavefront_release(self):
        """Test processing a complete wavefront release."""
        release = self.create_wavefront_release()
        monitor_output = {
            'timestamp': '2024-01-01T00:00:00Z',
            'total_repositories_checked': 1,
            'new_releases_found': 1,
            'releases': [release]
        }
        
        # Mock the dependencies
        with patch('download_releases.VersionDatabase') as mock_db_class, \
             patch('download_releases.GitHubDownloader') as mock_downloader_class:
            
            # Mock version database
            mock_db = Mock()
            mock_db.get_current_version.return_value = None  # No previous version
            mock_db_class.return_value = mock_db
            
            # Mock downloader
            mock_downloader = Mock()
            
            # Mock successful download of both asset and source
            def mock_download_content(release_data, asset_patterns, source_config):
                results = []
                
                # Check if we're processing the wavefront repo
                if release_data.get('repository') == 'wavefrontHQ/observability-for-kubernetes':
                    # Should download the YAML asset
                    if release_data.get('assets'):
                        for asset in release_data['assets']:
                            if any(asset['name'].endswith(ext) for ext in ['.yaml', '.yml']):
                                results.append({
                                    'asset_name': asset['name'],
                                    'success': True,
                                    'file_path': f"{self.test_dir}/{asset['name']}",
                                    'file_size': asset.get('size', 1000)
                                })
                    
                    # Should also download source (fallback_only=False for this repo)
                    if not source_config.get('fallback_only', True):
                        results.append({
                            'asset_name': 'wavefrontHQ_observability-for-kubernetes-v2.30.0.tar.gz',
                            'success': True,
                            'source_type': 'tarball',
                            'file_path': f"{self.test_dir}/source.tar.gz",
                            'file_size': 1024000
                        })
                
                return results
            
            mock_downloader.download_release_content = mock_download_content
            mock_downloader_class.return_value = mock_downloader
            
            # Process the release
            coordinator = ReleaseDownloadCoordinator(self.config, 'fake_token')
            results = coordinator.process_monitor_output(monitor_output)
            
            # Verify results
            self.assertEqual(results['new_downloads'], 1)
            self.assertEqual(results['skipped_releases'], 0)
            self.assertEqual(results['failed_downloads'], 0)
            
            # Check download details
            download_result = results['download_results'][0]
            self.assertEqual(download_result['repository'], 'wavefrontHQ/observability-for-kubernetes')
            self.assertEqual(download_result['action'], 'downloaded')
            
            # Should have downloaded 2 files (yaml + source)
            metadata = download_result['metadata']
            self.assertEqual(metadata['download_count'], 2)
            
            # Verify both files in downloaded list
            downloaded_files = metadata['downloaded_files']
            self.assertEqual(len(downloaded_files), 2)
            self.assertTrue(any('wavefront-operator.yaml' in f for f in downloaded_files))
            self.assertTrue(any('.tar.gz' in f for f in downloaded_files))
    
    def test_asset_pattern_matching(self):
        """Test that asset patterns correctly match manifest files."""
        downloader = GitHubDownloader('fake_token')
        
        # Test manifest patterns
        self.assertTrue(downloader._matches_patterns('wavefront-operator.yaml', ['*.yaml']))
        self.assertTrue(downloader._matches_patterns('config.yml', ['*.yml']))
        self.assertTrue(downloader._matches_patterns('values.yaml', ['*.yaml', '*.yml']))
        self.assertTrue(downloader._matches_patterns('manifest.json', ['*.json']))
        
        # Test exclusions
        self.assertFalse(downloader._matches_patterns('binary.exe', ['*.yaml']))
        self.assertFalse(downloader._matches_patterns('README.md', ['*.yaml', '*.yml']))
    
    def test_source_archive_preference(self):
        """Test source archive format preferences."""
        downloader = GitHubDownloader('fake_token', download_dir=self.test_dir)
        
        release_data = {
            'repository': 'test/repo',
            'tag_name': 'v1.0.0',
            'tarball_url': 'https://api.github.com/repos/test/repo/tarball/v1.0.0',
            'zipball_url': 'https://api.github.com/repos/test/repo/zipball/v1.0.0'
        }
        
        # Mock the actual download
        with patch.object(downloader, '_download_single_asset') as mock_download:
            mock_download.return_value = {'success': True, 'asset_name': 'test'}
            
            # Test prefer tarball
            results = downloader.download_source_archives(
                release_data, None, {'prefer': 'tarball'}
            )
            self.assertEqual(len(results), 1)
            self.assertTrue('.tar.gz' in mock_download.call_args[0][0]['name'])
            
            # Test prefer zipball
            mock_download.reset_mock()
            results = downloader.download_source_archives(
                release_data, None, {'prefer': 'zipball'}
            )
            self.assertEqual(len(results), 1)
            self.assertTrue('.zip' in mock_download.call_args[0][0]['name'])
            
            # Test both
            mock_download.reset_mock()
            results = downloader.download_source_archives(
                release_data, None, {'prefer': 'both'}
            )
            self.assertEqual(len(results), 2)


class TestManifestDownloadIntegration(unittest.TestCase):
    """Integration tests for manifest downloads."""
    
    def test_real_wavefront_release_structure(self):
        """Test with actual wavefront release structure."""
        # This test verifies the exact structure we expect from the API
        release_json = '''
        {
            "repository": "wavefrontHQ/observability-for-kubernetes",
            "tag_name": "v2.30.0",
            "assets": [
                {
                    "name": "wavefront-operator.yaml",
                    "size": 56535,
                    "browser_download_url": "https://github.com/wavefrontHQ/observability-for-kubernetes/releases/download/v2.30.0/wavefront-operator.yaml"
                }
            ],
            "tarball_url": "https://api.github.com/repos/wavefrontHQ/observability-for-kubernetes/tarball/v2.30.0",
            "zipball_url": "https://api.github.com/repos/wavefrontHQ/observability-for-kubernetes/zipball/v2.30.0"
        }
        '''
        
        release = json.loads(release_json)
        
        # Verify structure
        self.assertEqual(len(release['assets']), 1)
        self.assertEqual(release['assets'][0]['name'], 'wavefront-operator.yaml')
        self.assertTrue(release['assets'][0]['browser_download_url'].endswith('.yaml'))
        
        # Verify this should match our patterns
        downloader = GitHubDownloader('fake_token')
        self.assertTrue(
            downloader._matches_patterns(
                release['assets'][0]['name'],
                ['*.yaml', '*.yml']
            )
        )


if __name__ == '__main__':
    unittest.main()