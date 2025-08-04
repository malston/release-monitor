#!/usr/bin/env python3
"""
Integration tests for manifest and source code downloads.
Tests the complete flow from monitor output to downloaded files.
"""

import unittest
import tempfile
import shutil
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from download_releases import ReleaseDownloadCoordinator
from github_downloader import GitHubDownloader
from github_monitor import GitHubMonitor


@patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'}, clear=True)
class TestManifestDownloadIntegration(unittest.TestCase):
    """Integration tests for the complete download flow."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.version_db_path = os.path.join(self.test_dir, 'version_db.json')

    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def create_test_config(self):
        """Create test configuration with wavefront overrides."""
        return {
            'download': {
                'enabled': True,
                'directory': self.test_dir,
                'version_db': self.version_db_path,
                'asset_patterns': [
                    '*.tar.gz',
                    '*.zip',
                    '*.yaml',
                    '*.yml',
                    '*.json'
                ],
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

    def create_wavefront_monitor_output(self):
        """Create monitor output for wavefront repository."""
        return {
            'timestamp': '2024-01-01T00:00:00Z',
            'total_repositories_checked': 1,
            'new_releases_found': 1,
            'releases': [{
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
            }]
        }

    def test_wavefront_download_flow(self):
        """Test complete download flow for wavefront repository."""
        config = self.create_test_config()
        monitor_output = self.create_wavefront_monitor_output()

        # Mock the actual file downloads
        downloaded_files = []

        def mock_download_with_retry(self, url, file_path, asset, max_retries=3):
            # Track what's being downloaded
            downloaded_files.append({
                'url': url,
                'file_path': str(file_path),
                'asset_name': asset.get('name', 'unknown')
            })

            # Create the file
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(f"Mock content for {asset.get('name', 'unknown')}")

            return True, None

        # Patch both the download method and session creation
        with patch('requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session

            with patch.object(GitHubDownloader, '_download_with_retry', mock_download_with_retry):
                # Create coordinator and process
                coordinator = ReleaseDownloadCoordinator(config, 'fake_token')
                results = coordinator.process_monitor_output(monitor_output)

                # Verify results
                self.assertEqual(results['new_downloads'], 1)
                self.assertEqual(results['failed_downloads'], 0)

                # Check downloaded files
                self.assertEqual(len(downloaded_files), 2,
                               f"Expected 2 files (yaml + source), got {len(downloaded_files)}")

                # Verify both asset and source were downloaded
                asset_names = [f['asset_name'] for f in downloaded_files]
                self.assertIn('wavefront-operator.yaml', asset_names)
                self.assertTrue(any('.tar.gz' in name for name in asset_names))

                # Check download metadata
                download_result = results['download_results'][0]
                self.assertEqual(download_result['action'], 'downloaded')
                self.assertEqual(download_result['repository'], 'wavefrontHQ/observability-for-kubernetes')

                metadata = download_result['metadata']
                self.assertEqual(metadata['download_count'], 2)
                self.assertEqual(len(metadata['downloaded_files']), 2)

    def test_manifest_only_repository(self):
        """Test repository with only manifest files (no binaries)."""
        config = self.create_test_config()

        # Create a release with only YAML manifests
        monitor_output = {
            'releases': [{
                'repository': 'test/k8s-manifests',
                'owner': 'test',
                'repo': 'k8s-manifests',
                'tag_name': 'v1.0.0',
                'assets': [
                    {
                        'name': 'deployment.yaml',
                        'size': 1024,
                        'browser_download_url': 'https://github.com/test/deployment.yaml'
                    },
                    {
                        'name': 'service.yml',
                        'size': 512,
                        'browser_download_url': 'https://github.com/test/service.yml'
                    }
                ],
                'tarball_url': 'https://api.github.com/repos/test/k8s-manifests/tarball/v1.0.0',
                'zipball_url': 'https://api.github.com/repos/test/k8s-manifests/zipball/v1.0.0'
            }]
        }

        downloaded_files = []

        def track_downloads(self, url, file_path, asset, max_retries=3):
            downloaded_files.append(asset.get('name', Path(file_path).name))
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("mock")
            return True, None

        with patch.object(GitHubDownloader, '_download_with_retry', track_downloads):
            coordinator = ReleaseDownloadCoordinator(config, 'fake_token')
            results = coordinator.process_monitor_output(monitor_output)

            # Should download both YAML files
            self.assertEqual(results['new_downloads'], 1)
            self.assertIn('deployment.yaml', downloaded_files)
            self.assertIn('service.yml', downloaded_files)

            # Should NOT download source (fallback_only=True and assets were found)
            self.assertFalse(any('.tar.gz' in f for f in downloaded_files))

    def test_source_only_repository(self):
        """Test repository with no release assets (source only)."""
        config = self.create_test_config()

        # Create a release with no assets
        monitor_output = {
            'releases': [{
                'repository': 'test/source-only',
                'owner': 'test',
                'repo': 'source-only',
                'tag_name': 'v1.0.0',
                'assets': [],  # No assets
                'tarball_url': 'https://api.github.com/repos/test/source-only/tarball/v1.0.0',
                'zipball_url': 'https://api.github.com/repos/test/source-only/zipball/v1.0.0'
            }]
        }

        downloaded_files = []

        def track_downloads(self, url, file_path, asset, max_retries=3):
            downloaded_files.append(Path(file_path).name)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("mock")
            return True, None

        with patch.object(GitHubDownloader, '_download_with_retry', track_downloads):
            coordinator = ReleaseDownloadCoordinator(config, 'fake_token')
            results = coordinator.process_monitor_output(monitor_output)

            # Should download source archive since no assets
            self.assertEqual(results['new_downloads'], 1)
            self.assertEqual(len(downloaded_files), 1)
            self.assertTrue(downloaded_files[0].endswith('.tar.gz'))

    def test_version_tracking(self):
        """Test that version tracking prevents re-downloads."""
        config = self.create_test_config()
        monitor_output = self.create_wavefront_monitor_output()

        # First download
        with patch.object(GitHubDownloader, '_download_with_retry',
                         lambda self, url, fp, asset, max_retries=3: (fp.parent.mkdir(parents=True, exist_ok=True) or fp.write_text("mock") or True, None)):
            coordinator = ReleaseDownloadCoordinator(config, 'fake_token')
            results1 = coordinator.process_monitor_output(monitor_output)
            self.assertEqual(results1['new_downloads'], 1)

        # Second attempt - should skip
        with patch.object(GitHubDownloader, '_download_with_retry',
                         lambda self, url, fp, asset, max_retries=3: (fp.parent.mkdir(parents=True, exist_ok=True) or fp.write_text("mock") or True, None)):
            coordinator2 = ReleaseDownloadCoordinator(config, 'fake_token')
            results2 = coordinator2.process_monitor_output(monitor_output)
            self.assertEqual(results2['new_downloads'], 0)
            self.assertEqual(results2['skipped_releases'], 1)


class TestDownloadPatterns(unittest.TestCase):
    """Test asset pattern matching and filtering."""

    def test_yaml_pattern_matching(self):
        """Test YAML file pattern matching."""
        downloader = GitHubDownloader('fake_token')

        test_cases = [
            ('deployment.yaml', ['*.yaml'], True),
            ('service.yml', ['*.yml'], True),
            ('config.yaml', ['*.yaml', '*.yml'], True),
            ('values.yml', ['*.yaml', '*.yml'], True),
            ('README.md', ['*.yaml', '*.yml'], False),
            ('binary.exe', ['*.yaml'], False),
            ('manifest.json', ['*.json'], True),
            ('config.toml', ['*.toml'], True),
        ]

        for filename, patterns, expected in test_cases:
            result = downloader._matches_patterns(filename, patterns)
            self.assertEqual(result, expected,
                           f"{filename} vs {patterns} should be {expected}")

    def test_exclusion_patterns(self):
        """Test exclusion patterns."""
        downloader = GitHubDownloader('fake_token')

        patterns = ['*.zip', '!*-sources.zip']

        self.assertTrue(downloader._matches_patterns('release.zip', patterns))
        self.assertFalse(downloader._matches_patterns('release-sources.zip', patterns))


if __name__ == '__main__':
    unittest.main()
