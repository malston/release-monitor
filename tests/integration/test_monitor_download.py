#!/usr/bin/env python3
"""Integration tests for monitor with download functionality."""

import os
import sys
import json
import tempfile
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from github_monitor import main as monitor_main
from download_releases import ReleaseDownloadCoordinator
from github_version_db import VersionDatabase


class TestMonitorDownloadIntegration(unittest.TestCase):
    """Test integration between monitor and download functionality."""

    def setUp(self):
        """Create a temporary directory for test files."""
        self.temp_dir = tempfile.mkdtemp()

        # Create test configuration
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
                "directory": str(Path(self.temp_dir) / "downloads"),
                "version_db": str(Path(self.temp_dir) / "version_db.json"),
                "asset_patterns": ["*.tar.gz"],
                "verify_checksums": True,
                "retry_attempts": 2,
                "retry_delay": 1
            }
        }

        self.test_config = Path(self.temp_dir) / "config.yaml"
        with open(self.test_config, 'w') as f:
            import yaml
            yaml.dump(config, f)

        # Mock GitHub API response
        self.mock_github_response = {
            "tag_name": "v1.25.0",
            "name": "v1.25.0",
            "html_url": "https://github.com/kubernetes/kubernetes/releases/tag/v1.25.0",
            "prerelease": False,
            "draft": False,
            "created_at": "2022-08-23T17:00:00Z",
            "published_at": "2022-08-23T17:00:00Z",
            "tarball_url": "https://api.github.com/repos/kubernetes/kubernetes/tarball/v1.25.0",
            "zipball_url": "https://api.github.com/repos/kubernetes/kubernetes/zipball/v1.25.0",
            "assets": [
                {
                    "name": "kubernetes.tar.gz",
                    "browser_download_url": "https://github.com/kubernetes/kubernetes/releases/download/v1.25.0/kubernetes.tar.gz",
                    "size": 12,  # Match mock content length
                    "content_type": "application/gzip"
                },
                {
                    "name": "kubernetes-src.tar.gz",
                    "browser_download_url": "https://github.com/kubernetes/kubernetes/releases/download/v1.25.0/kubernetes-src.tar.gz",
                    "size": 12,  # Match mock content length
                    "content_type": "application/gzip"
                }
            ]
        }

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'}, clear=True)
    @patch('requests.Session.get')
    def test_monitor_with_download_flag(self, mock_get):
        """Test monitor with --download flag processes new releases."""
        # Mock GitHub API response
        mock_response = MagicMock()
        mock_response.json.return_value = self.mock_github_response  # Single release, not a list
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/json'}

        # Mock asset download
        mock_asset_response = MagicMock()
        mock_asset_response.iter_content = MagicMock(return_value=[b'test content'])
        mock_asset_response.status_code = 200
        mock_asset_response.headers = {'content-length': '12'}
        mock_asset_response.raise_for_status = MagicMock()

        def mock_get_side_effect(url, **kwargs):
            if 'api.github.com' in url:
                return mock_response
            else:
                return mock_asset_response

        mock_get.side_effect = mock_get_side_effect

        # Run monitor with download flag and force-check to ensure release is treated as new
        sys.argv = ['github_monitor.py', '--config', str(self.test_config), '--download', '--force-check']

        with patch('sys.stdout') as mock_stdout:
            monitor_main()

        # Verify download directory was created (uses underscore format: owner_repo)
        download_dir = Path(self.temp_dir) / "downloads" / "kubernetes_kubernetes" / "v1.25.0"
        self.assertTrue(download_dir.exists())

        # Verify asset was downloaded
        downloaded_file = download_dir / "kubernetes.tar.gz"
        self.assertTrue(downloaded_file.exists())

        # Verify version database was updated
        version_db = VersionDatabase(str(Path(self.temp_dir) / "version_db.json"))
        current_version = version_db.get_current_version("kubernetes", "kubernetes")
        self.assertEqual(current_version, "v1.25.0")

    @patch('requests.get')
    def test_monitor_without_download_flag(self, mock_get):
        """Test monitor without --download flag doesn't download."""
        # Mock GitHub API response
        mock_response = MagicMock()
        mock_response.json.return_value = [self.mock_github_response]
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/json'}
        mock_get.return_value = mock_response

        # Run monitor without download flag
        sys.argv = ['github_monitor.py', '--config', str(self.test_config)]

        with patch('sys.stdout') as mock_stdout:
            monitor_main()

        # Verify no download directory was created
        download_dir = Path(self.temp_dir) / "downloads"
        self.assertFalse(download_dir.exists())

        # Verify version database was not created
        version_db_path = Path(self.temp_dir) / "version_db.json"
        self.assertFalse(version_db_path.exists())

    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'}, clear=True)
    @patch('requests.Session.get')
    def test_monitor_download_only_new_versions(self, mock_get):
        """Test that monitor only downloads truly new versions."""
        # Initialize version database with existing version
        version_db = VersionDatabase(str(Path(self.temp_dir) / "version_db.json"))
        version_db.update_version("kubernetes", "kubernetes", "v1.24.0")

        # Mock the latest release response (v1.25.0) since get_latest_release uses /releases/latest
        latest_release = {
            "tag_name": "v1.25.0",
            "name": "v1.25.0",
            "html_url": "https://github.com/kubernetes/kubernetes/releases/tag/v1.25.0",
            "prerelease": False,
            "draft": False,
            "created_at": "2022-08-23T17:00:00Z",
            "published_at": "2022-08-23T17:00:00Z",
            "tarball_url": "https://api.github.com/repos/kubernetes/kubernetes/tarball/v1.25.0",
            "zipball_url": "https://api.github.com/repos/kubernetes/kubernetes/zipball/v1.25.0",
            "assets": [{
                "name": "kubernetes.tar.gz",
                "browser_download_url": "https://github.com/kubernetes/kubernetes/releases/download/v1.25.0/kubernetes.tar.gz",
                "size": 12,  # Match mock content length
                "content_type": "application/gzip"
            }]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = latest_release  # Single latest release
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

        # Run monitor with download flag and force-check to ensure release is treated as new
        sys.argv = ['github_monitor.py', '--config', str(self.test_config), '--download', '--force-check']

        with patch('sys.stdout') as mock_stdout:
            monitor_main()

        # Verify only v1.25.0 was downloaded (not v1.24.0) (uses underscore format: owner_repo)
        v125_dir = Path(self.temp_dir) / "downloads" / "kubernetes_kubernetes" / "v1.25.0"
        v124_dir = Path(self.temp_dir) / "downloads" / "kubernetes_kubernetes" / "v1.24.0"

        self.assertTrue(v125_dir.exists())
        self.assertFalse(v124_dir.exists())

        # Verify version database was updated to v1.25.0
        current_version = version_db.get_current_version("kubernetes", "kubernetes")
        self.assertEqual(current_version, "v1.25.0")

    def test_monitor_download_with_asset_patterns(self):
        """Test asset pattern filtering during download."""
        from github_downloader import GitHubDownloader

        # Create downloader to test pattern matching directly
        with patch('requests.Session'):
            downloader = GitHubDownloader('fake_token')

        # Test asset pattern matching with exclusions
        patterns = ['*.tar.gz', '!*-src.tar.gz']

        # Test assets that should match
        self.assertTrue(downloader._matches_patterns("kubernetes.tar.gz", patterns))
        self.assertTrue(downloader._matches_patterns("release.tar.gz", patterns))

        # Test assets that should be excluded by the exclusion pattern
        self.assertFalse(downloader._matches_patterns("kubernetes-src.tar.gz", patterns))
        self.assertFalse(downloader._matches_patterns("release-src.tar.gz", patterns))

        # Test assets that match the inclusion but not the exclusion pattern
        # (source-code.tar.gz doesn't match *-src.tar.gz pattern, so it should be included)
        self.assertTrue(downloader._matches_patterns("source-code.tar.gz", patterns))

        # Test assets that don't match the patterns
        self.assertFalse(downloader._matches_patterns("kubernetes.zip", patterns))
        self.assertFalse(downloader._matches_patterns("README.md", patterns))

        # Test case insensitive matching
        patterns_upper = ['*.TAR.GZ']
        self.assertTrue(downloader._matches_patterns("kubernetes.tar.gz", patterns_upper))
        self.assertTrue(downloader._matches_patterns("KUBERNETES.TAR.GZ", patterns_upper))

    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'}, clear=True)
    @patch('requests.Session.get')
    def test_monitor_download_error_handling(self, mock_get):
        """Test error handling during download process."""
        # Mock GitHub API success but download failure
        mock_api_response = MagicMock()
        mock_api_response.json.return_value = self.mock_github_response  # Single release, not a list
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

        # Run monitor with download flag and force-check to ensure release is treated as new
        sys.argv = ['github_monitor.py', '--config', str(self.test_config), '--download', '--force-check']

        # Should not raise exception, but should log error
        with patch('sys.stdout') as mock_stdout:
            monitor_main()

        # Verify download directory was created but no files downloaded
        download_dir = Path(self.temp_dir) / "downloads"
        self.assertTrue(download_dir.exists())

        downloaded_file = download_dir / "kubernetes_kubernetes" / "v1.25.0" / "kubernetes.tar.gz"
        self.assertFalse(downloaded_file.exists())

    def test_concurrent_monitor_downloads(self):
        """Test concurrent monitor processes with downloads."""
        import threading
        import time

        version_db_path = str(Path(self.temp_dir) / "version_db.json")
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
        self.assertEqual(len(results), 5)
        self.assertTrue(all(r[1] == "success" for r in results))

        # Verify database has one of the versions
        current = version_db.get_current_version("test", "repo")
        self.assertIn(current, [f"v1.{i}.0" for i in range(5)])


if __name__ == "__main__":
    unittest.main()
