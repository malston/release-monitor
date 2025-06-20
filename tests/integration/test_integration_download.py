#!/usr/bin/env python3
"""
Integration tests for GitHub Monitor with Download functionality
"""

import unittest
import tempfile
import os
import json
import yaml
from unittest.mock import patch, Mock
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from github_monitor import main as monitor_main


class TestIntegrationDownload(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test configuration with download enabled
        self.config_data = {
            'repositories': [
                {
                    'owner': 'test',
                    'repo': 'repo1',
                    'description': 'Test repository 1'
                }
            ],
            'settings': {
                'rate_limit_delay': 0.1,
                'max_releases_per_repo': 5,
                'include_prereleases': False
            },
            'download': {
                'enabled': True,
                'directory': os.path.join(self.temp_dir, 'downloads'),
                'version_db': os.path.join(self.temp_dir, 'versions.json'),
                'asset_patterns': ['*.tar.gz', '*.zip'],
                'include_prereleases': False,
                'verify_downloads': True,
                'cleanup_old_versions': False,
                'keep_versions': 5,
                'timeout': 30
            }
        }
        
        self.config_file = os.path.join(self.temp_dir, 'config.yaml')
        with open(self.config_file, 'w') as f:
            yaml.dump(self.config_data, f)
        
        self.state_file = os.path.join(self.temp_dir, 'state.json')
        self.output_file = os.path.join(self.temp_dir, 'output.json')
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'})
    @patch('sys.argv', ['github_monitor.py', '--config', 'test_config.yaml', '--download'])
    @patch('github_monitor.GitHubMonitor.get_latest_release')
    @patch('download_releases.GitHubDownloader.download_release_assets')
    def test_monitor_with_download_integration(self, mock_download, mock_get_release):
        """Test complete integration of monitor with download functionality."""
        
        # Mock GitHub API response
        mock_release = {
            'tag_name': 'v1.0.0',
            'name': 'Test Release v1.0.0',
            'published_at': '2024-01-15T10:00:00Z',
            'tarball_url': 'https://github.com/test/repo1/tarball/v1.0.0',
            'zipball_url': 'https://github.com/test/repo1/zipball/v1.0.0',
            'html_url': 'https://github.com/test/repo1/releases/tag/v1.0.0',
            'prerelease': False,
            'draft': False,
            'assets': [
                {
                    'name': 'release.tar.gz',
                    'browser_download_url': 'https://github.com/test/repo1/releases/download/v1.0.0/release.tar.gz',
                    'size': 1024
                }
            ]
        }
        mock_get_release.return_value = mock_release
        
        # Mock successful download
        mock_download.return_value = [
            {
                'success': True,
                'asset_name': 'release.tar.gz',
                'file_path': os.path.join(self.temp_dir, 'downloads', 'test_repo1', 'v1.0.0', 'release.tar.gz'),
                'file_size': 1024,
                'download_time': 1.5,
                'sha256': 'test_checksum'
            }
        ]
        
        # Override sys.argv for the test
        import sys
        original_argv = sys.argv
        sys.argv = [
            'github_monitor.py',
            '--config', self.config_file,
            '--state-file', self.state_file,
            '--output', self.output_file,
            '--download'
        ]
        
        try:
            # Run the monitor
            monitor_main()
            
            # Verify output file was created
            self.assertTrue(os.path.exists(self.output_file))
            
            # Load and verify output
            with open(self.output_file, 'r') as f:
                output = json.load(f)
            
            # Verify basic monitor output
            self.assertIn('timestamp', output)
            self.assertEqual(output['total_repositories_checked'], 1)
            self.assertEqual(output['new_releases_found'], 1)
            self.assertEqual(len(output['releases']), 1)
            
            # Verify release data
            release = output['releases'][0]
            self.assertEqual(release['repository'], 'test/repo1')
            self.assertEqual(release['tag_name'], 'v1.0.0')
            self.assertIn('assets', release)
            
            # Verify download results are included
            self.assertIn('download_results', output)
            download_results = output['download_results']
            self.assertEqual(download_results['total_releases_checked'], 1)
            self.assertEqual(download_results['new_downloads'], 1)
            self.assertEqual(download_results['skipped_releases'], 0)
            self.assertEqual(download_results['failed_downloads'], 0)
            
            # Verify download details
            self.assertEqual(len(download_results['download_results']), 1)
            download_result = download_results['download_results'][0]
            self.assertEqual(download_result['action'], 'downloaded')
            self.assertEqual(download_result['repository'], 'test/repo1')
            self.assertEqual(download_result['tag_name'], 'v1.0.0')
            
        finally:
            # Restore original sys.argv
            sys.argv = original_argv
    
    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'})
    @patch('sys.argv', ['github_monitor.py', '--config', 'test_config.yaml', '--download'])
    @patch('github_monitor.GitHubMonitor.get_latest_release')
    def test_monitor_download_disabled_config(self, mock_get_release):
        """Test monitor with download flag but disabled in config."""
        
        # Create config with download disabled
        config_data = self.config_data.copy()
        config_data['download']['enabled'] = False
        
        config_file = os.path.join(self.temp_dir, 'config_disabled.yaml')
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # Override sys.argv for the test
        import sys
        original_argv = sys.argv
        sys.argv = [
            'github_monitor.py',
            '--config', config_file,
            '--download'
        ]
        
        try:
            # Should exit with error
            with self.assertRaises(SystemExit) as cm:
                monitor_main()
            
            self.assertEqual(cm.exception.code, 1)
            
        finally:
            # Restore original sys.argv
            sys.argv = original_argv
    
    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'})
    @patch('sys.argv', ['github_monitor.py', '--config', 'test_config.yaml', '--download'])
    @patch('github_monitor.GitHubMonitor.get_latest_release')
    def test_monitor_no_new_releases_with_download(self, mock_get_release):
        """Test monitor with download flag but no new releases found."""
        
        # Mock no release found
        mock_get_release.return_value = None
        
        # Override sys.argv for the test
        import sys
        original_argv = sys.argv
        sys.argv = [
            'github_monitor.py',
            '--config', self.config_file,
            '--state-file', self.state_file,
            '--output', self.output_file,
            '--download'
        ]
        
        try:
            # Run the monitor
            monitor_main()
            
            # Verify output file was created
            self.assertTrue(os.path.exists(self.output_file))
            
            # Load and verify output
            with open(self.output_file, 'r') as f:
                output = json.load(f)
            
            # Should have no new releases and no download results
            self.assertEqual(output['new_releases_found'], 0)
            self.assertEqual(len(output['releases']), 0)
            self.assertNotIn('download_results', output)
            
        finally:
            # Restore original sys.argv
            sys.argv = original_argv
    
    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'})
    @patch('sys.argv', ['github_monitor.py', '--config', 'test_config.yaml', '--download'])
    @patch('github_monitor.GitHubMonitor.get_latest_release')
    def test_monitor_download_import_error(self, mock_get_release):
        """Test monitor handling when download modules are not available."""
        
        # Mock GitHub API response
        mock_release = {
            'tag_name': 'v1.0.0',
            'name': 'Test Release v1.0.0',
            'published_at': '2024-01-15T10:00:00Z',
            'tarball_url': 'https://github.com/test/repo1/tarball/v1.0.0',
            'zipball_url': 'https://github.com/test/repo1/zipball/v1.0.0',
            'html_url': 'https://github.com/test/repo1/releases/tag/v1.0.0',
            'prerelease': False,
            'draft': False,
            'assets': []
        }
        mock_get_release.return_value = mock_release
        
        # Override sys.argv for the test
        import sys
        original_argv = sys.argv
        sys.argv = [
            'github_monitor.py',
            '--config', self.config_file,
            '--state-file', self.state_file,
            '--output', self.output_file,
            '--download'
        ]
        
        try:
            # Mock import error for download_releases module specifically
            import builtins
            original_import = builtins.__import__
            
            def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
                if name == 'download_releases':
                    raise ImportError("No module named 'download_releases'")
                return original_import(name, globals, locals, fromlist, level)
            
            with patch.object(builtins, '__import__', side_effect=mock_import):
                # Run the monitor
                monitor_main()
                
                # Verify output file was created
                self.assertTrue(os.path.exists(self.output_file))
                
                # Load and verify output
                with open(self.output_file, 'r') as f:
                    output = json.load(f)
                
                # Should have found release but failed to download
                self.assertEqual(output['new_releases_found'], 1)
                self.assertIn('download_error', output)
                self.assertIn('Download modules not found', output['download_error'])
                
        finally:
            # Restore original sys.argv
            sys.argv = original_argv
    
    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'})
    def test_monitor_without_download_flag(self):
        """Test normal monitor operation without download flag."""
        
        # Override sys.argv for the test
        import sys
        original_argv = sys.argv
        sys.argv = [
            'github_monitor.py',
            '--config', self.config_file,
            '--state-file', self.state_file,
            '--output', self.output_file
        ]
        
        with patch('github_monitor.GitHubMonitor.get_latest_release') as mock_get_release:
            mock_get_release.return_value = None
            
            try:
                # Run the monitor
                monitor_main()
                
                # Verify output file was created
                self.assertTrue(os.path.exists(self.output_file))
                
                # Load and verify output
                with open(self.output_file, 'r') as f:
                    output = json.load(f)
                
                # Should not have download results
                self.assertNotIn('download_results', output)
                self.assertNotIn('download_error', output)
                
            finally:
                # Restore original sys.argv
                sys.argv = original_argv
    
    def test_download_config_validation(self):
        """Test download configuration validation."""
        from github_monitor import load_config
        
        # Test valid config
        config = load_config(self.config_file)
        download_config = config.get('download', {})
        
        self.assertTrue(download_config.get('enabled', False))
        self.assertIn('directory', download_config)
        self.assertIn('asset_patterns', download_config)
        self.assertIsInstance(download_config['asset_patterns'], list)
        
        # Test config structure
        required_fields = ['enabled', 'directory', 'version_db']
        for field in required_fields:
            self.assertIn(field, download_config, f"Missing required download config field: {field}")


if __name__ == '__main__':
    unittest.main()