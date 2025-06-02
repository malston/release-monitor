#!/usr/bin/env python3
"""Integration tests for monitor with download functionality."""

import os
import sys
import json
import tempfile
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from github_monitor import main as monitor_main
from download_releases import ReleaseDownloadCoordinator
from github_version_db import VersionDatabase


class TestMonitorDownloadIntegration:
    """Test integration between monitor and download functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def test_config(self, temp_dir):
        """Create a test configuration file."""
        config = {
            "repositories": [
                {
                    "owner": "kubernetes",
                    "repo": "kubernetes",
                    "include_prereleases": False
                }
            ],
            "download": {
                "enabled": True,
                "directory": str(Path(temp_dir) / "downloads"),
                "version_db": str(Path(temp_dir) / "version_db.json"),
                "asset_patterns": ["*.tar.gz"],
                "verify_checksums": True,
                "retry_attempts": 2,
                "retry_delay": 1
            }
        }
        
        config_path = Path(temp_dir) / "config.yaml"
        with open(config_path, 'w') as f:
            import yaml
            yaml.dump(config, f)
        
        return config_path
    
    @pytest.fixture
    def mock_github_response(self):
        """Mock GitHub API response for testing."""
        return {
            "tag_name": "v1.25.0",
            "name": "v1.25.0",
            "html_url": "https://github.com/kubernetes/kubernetes/releases/tag/v1.25.0",
            "prerelease": False,
            "created_at": "2022-08-23T17:00:00Z",
            "published_at": "2022-08-23T17:00:00Z",
            "assets": [
                {
                    "name": "kubernetes.tar.gz",
                    "browser_download_url": "https://github.com/kubernetes/kubernetes/releases/download/v1.25.0/kubernetes.tar.gz",
                    "size": 1024000,
                    "content_type": "application/gzip"
                },
                {
                    "name": "kubernetes-src.tar.gz",
                    "browser_download_url": "https://github.com/kubernetes/kubernetes/releases/download/v1.25.0/kubernetes-src.tar.gz",
                    "size": 2048000,
                    "content_type": "application/gzip"
                }
            ]
        }
    
    @patch('requests.get')
    def test_monitor_with_download_flag(self, mock_get, test_config, temp_dir, mock_github_response):
        """Test monitor with --download flag processes new releases."""
        # Mock GitHub API response
        mock_response = MagicMock()
        mock_response.json.return_value = [mock_github_response]
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/json'}
        
        # Mock asset download
        mock_asset_response = MagicMock()
        mock_asset_response.iter_content = MagicMock(return_value=[b'test content'])
        mock_asset_response.status_code = 200
        mock_asset_response.headers = {'content-length': '12'}
        
        def mock_get_side_effect(url, **kwargs):
            if 'api.github.com' in url:
                return mock_response
            else:
                return mock_asset_response
        
        mock_get.side_effect = mock_get_side_effect
        
        # Run monitor with download flag
        sys.argv = ['github_monitor.py', '--config', str(test_config), '--download']
        
        with patch('sys.stdout') as mock_stdout:
            monitor_main()
        
        # Verify download directory was created
        download_dir = Path(temp_dir) / "downloads" / "kubernetes" / "kubernetes" / "v1.25.0"
        assert download_dir.exists()
        
        # Verify asset was downloaded
        downloaded_file = download_dir / "kubernetes.tar.gz"
        assert downloaded_file.exists()
        
        # Verify version database was updated
        version_db = VersionDatabase(str(Path(temp_dir) / "version_db.json"))
        current_version = version_db.get_current_version("kubernetes", "kubernetes")
        assert current_version == "v1.25.0"
    
    @patch('requests.get')
    def test_monitor_without_download_flag(self, mock_get, test_config, temp_dir, mock_github_response):
        """Test monitor without --download flag doesn't download."""
        # Mock GitHub API response
        mock_response = MagicMock()
        mock_response.json.return_value = [mock_github_response]
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/json'}
        mock_get.return_value = mock_response
        
        # Run monitor without download flag
        sys.argv = ['github_monitor.py', '--config', str(test_config)]
        
        with patch('sys.stdout') as mock_stdout:
            monitor_main()
        
        # Verify no download directory was created
        download_dir = Path(temp_dir) / "downloads"
        assert not download_dir.exists()
        
        # Verify version database was not created
        version_db_path = Path(temp_dir) / "version_db.json"
        assert not version_db_path.exists()
    
    @patch('requests.get')
    def test_monitor_download_only_new_versions(self, mock_get, test_config, temp_dir):
        """Test that monitor only downloads truly new versions."""
        # Initialize version database with existing version
        version_db = VersionDatabase(str(Path(temp_dir) / "version_db.json"))
        version_db.update_version("kubernetes", "kubernetes", "v1.24.0")
        
        # Mock responses for two releases
        mock_releases = [
            {
                "tag_name": "v1.25.0",
                "name": "v1.25.0",
                "html_url": "https://github.com/kubernetes/kubernetes/releases/tag/v1.25.0",
                "prerelease": False,
                "created_at": "2022-08-23T17:00:00Z",
                "published_at": "2022-08-23T17:00:00Z",
                "assets": [{
                    "name": "kubernetes.tar.gz",
                    "browser_download_url": "https://github.com/kubernetes/kubernetes/releases/download/v1.25.0/kubernetes.tar.gz",
                    "size": 1024000,
                    "content_type": "application/gzip"
                }]
            },
            {
                "tag_name": "v1.24.0",  # This is already in DB
                "name": "v1.24.0",
                "html_url": "https://github.com/kubernetes/kubernetes/releases/tag/v1.24.0",
                "prerelease": False,
                "created_at": "2022-07-23T17:00:00Z",
                "published_at": "2022-07-23T17:00:00Z",
                "assets": [{
                    "name": "kubernetes.tar.gz",
                    "browser_download_url": "https://github.com/kubernetes/kubernetes/releases/download/v1.24.0/kubernetes.tar.gz",
                    "size": 1024000,
                    "content_type": "application/gzip"
                }]
            }
        ]
        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_releases
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/json'}
        
        mock_asset_response = MagicMock()
        mock_asset_response.iter_content = MagicMock(return_value=[b'test content'])
        mock_asset_response.status_code = 200
        mock_asset_response.headers = {'content-length': '12'}
        
        def mock_get_side_effect(url, **kwargs):
            if 'api.github.com' in url:
                return mock_response
            else:
                return mock_asset_response
        
        mock_get.side_effect = mock_get_side_effect
        
        # Run monitor with download flag
        sys.argv = ['github_monitor.py', '--config', str(test_config), '--download']
        
        with patch('sys.stdout') as mock_stdout:
            monitor_main()
        
        # Verify only v1.25.0 was downloaded (not v1.24.0)
        v125_dir = Path(temp_dir) / "downloads" / "kubernetes" / "kubernetes" / "v1.25.0"
        v124_dir = Path(temp_dir) / "downloads" / "kubernetes" / "kubernetes" / "v1.24.0"
        
        assert v125_dir.exists()
        assert not v124_dir.exists()
        
        # Verify version database was updated to v1.25.0
        current_version = version_db.get_current_version("kubernetes", "kubernetes")
        assert current_version == "v1.25.0"
    
    def test_monitor_download_with_asset_patterns(self, test_config, temp_dir):
        """Test asset pattern filtering during download."""
        from download_releases import ReleaseDownloadCoordinator
        
        # Create coordinator with specific patterns
        with open(test_config, 'r') as f:
            import yaml
            config = yaml.safe_load(f)
        
        config['download']['asset_patterns'] = ['*.tar.gz', '!*-src.tar.gz']
        
        coordinator = ReleaseDownloadCoordinator(config, "fake_token")
        
        # Test asset filtering
        assets = [
            {"name": "kubernetes.tar.gz"},
            {"name": "kubernetes-src.tar.gz"},
            {"name": "kubernetes.zip"},
            {"name": "README.md"}
        ]
        
        filtered = coordinator._filter_assets(assets, config['download']['asset_patterns'])
        filtered_names = [a['name'] for a in filtered]
        
        assert "kubernetes.tar.gz" in filtered_names
        assert "kubernetes-src.tar.gz" not in filtered_names
        assert "kubernetes.zip" not in filtered_names
        assert "README.md" not in filtered_names
    
    @patch('requests.get')
    def test_monitor_download_error_handling(self, mock_get, test_config, temp_dir, mock_github_response):
        """Test error handling during download process."""
        # Mock GitHub API success but download failure
        mock_api_response = MagicMock()
        mock_api_response.json.return_value = [mock_github_response]
        mock_api_response.status_code = 200
        mock_api_response.headers = {'content-type': 'application/json'}
        
        mock_download_response = MagicMock()
        mock_download_response.status_code = 404
        mock_download_response.raise_for_status.side_effect = Exception("404 Not Found")
        
        def mock_get_side_effect(url, **kwargs):
            if 'api.github.com' in url:
                return mock_api_response
            else:
                return mock_download_response
        
        mock_get.side_effect = mock_get_side_effect
        
        # Run monitor with download flag
        sys.argv = ['github_monitor.py', '--config', str(test_config), '--download']
        
        # Should not raise exception, but should log error
        with patch('sys.stdout') as mock_stdout:
            monitor_main()
        
        # Verify download directory was created but no files downloaded
        download_dir = Path(temp_dir) / "downloads" / "kubernetes" / "kubernetes" / "v1.25.0"
        assert download_dir.exists()
        
        downloaded_file = download_dir / "kubernetes.tar.gz"
        assert not downloaded_file.exists()
    
    def test_concurrent_monitor_downloads(self, test_config, temp_dir):
        """Test concurrent monitor processes with downloads."""
        import threading
        import time
        
        version_db_path = str(Path(temp_dir) / "version_db.json")
        version_db = VersionDatabase(version_db_path)
        
        results = []
        
        def update_version(version):
            try:
                version_db.update_version("test", "repo", version)
                results.append((version, "success"))
            except Exception as e:
                results.append((version, str(e)))
        
        # Create multiple threads trying to update versions
        threads = []
        for i in range(5):
            t = threading.Thread(target=update_version, args=(f"v1.{i}.0",))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # All updates should succeed
        assert len(results) == 5
        assert all(r[1] == "success" for r in results)
        
        # Verify database has one of the versions
        current = version_db.get_current_version("test", "repo")
        assert current in [f"v1.{i}.0" for i in range(5)]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])