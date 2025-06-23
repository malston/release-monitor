#!/usr/bin/env python3
"""
Unit tests for email notification functionality
"""
import json
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

# Add parent directory to path for accessing repo modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the module under test
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                'ci', 'tasks', 'send-release-notification'))
from generate_email import format_release_details, generate_email_content


class TestEmailNotification(unittest.TestCase):
    """Test email notification generation"""
    
    def setUp(self):
        """Set up test data"""
        self.sample_release = {
            'repository': 'kubernetes/kubernetes',
            'owner': 'kubernetes',
            'repo': 'kubernetes',
            'tag_name': 'v1.28.0',
            'name': 'Kubernetes v1.28.0',
            'published_at': '2023-08-15T12:00:00Z',
            'html_url': 'https://github.com/kubernetes/kubernetes/releases/tag/v1.28.0',
            'author': {'login': 'k8s-release-robot'},
            'assets': [
                {
                    'name': 'kubernetes-client-linux-amd64.tar.gz',
                    'size': 50331648,  # 48 MB
                    'browser_download_url': 'https://example.com/download1'
                },
                {
                    'name': 'kubernetes-server-linux-amd64.tar.gz',
                    'size': 157286400,  # 150 MB
                    'browser_download_url': 'https://example.com/download2'
                }
            ]
        }
        
        self.sample_releases_data = {
            'timestamp': '2023-08-15T14:00:00+00:00',
            'total_repositories_checked': 5,
            'new_releases_found': 2,
            'releases': [
                self.sample_release,
                {
                    'repository': 'prometheus/prometheus',
                    'owner': 'prometheus',
                    'repo': 'prometheus',
                    'tag_name': 'v2.46.0',
                    'name': 'Prometheus 2.46.0',
                    'published_at': '2023-08-15T10:00:00Z',
                    'html_url': 'https://github.com/prometheus/prometheus/releases/tag/v2.46.0',
                    'author': {'login': 'prombot'},
                    'assets': []
                }
            ]
        }
    
    def test_format_release_details_with_assets(self):
        """Test formatting release details with assets"""
        with patch.dict(os.environ, {'INCLUDE_ASSET_DETAILS': 'true'}):
            result = format_release_details(self.sample_release)
            
            self.assertIn('Repository: kubernetes/kubernetes', result)
            self.assertIn('Release: Kubernetes v1.28.0', result)
            self.assertIn('Tag: v1.28.0', result)
            self.assertIn('Author: k8s-release-robot', result)
            self.assertIn('Published: 2023-08-15 12:00 UTC', result)
            self.assertIn('URL: https://github.com/kubernetes/kubernetes/releases/tag/v1.28.0', result)
            self.assertIn('Assets:', result)
            self.assertIn('kubernetes-client-linux-amd64.tar.gz (48.0 MB)', result)
            self.assertIn('kubernetes-server-linux-amd64.tar.gz (150.0 MB)', result)
    
    def test_format_release_details_without_assets(self):
        """Test formatting release details without asset details"""
        with patch.dict(os.environ, {'INCLUDE_ASSET_DETAILS': 'false'}):
            result = format_release_details(self.sample_release)
            
            self.assertIn('Repository: kubernetes/kubernetes', result)
            self.assertNotIn('Assets:', result)
    
    def test_format_release_details_many_assets(self):
        """Test formatting with more than 5 assets"""
        release = self.sample_release.copy()
        release['assets'] = [
            {'name': f'asset{i}.tar.gz', 'size': 1048576}
            for i in range(8)
        ]
        
        with patch.dict(os.environ, {'INCLUDE_ASSET_DETAILS': 'true'}):
            result = format_release_details(release)
            
            self.assertIn('asset0.tar.gz', result)
            self.assertIn('asset4.tar.gz', result)
            self.assertNotIn('asset5.tar.gz', result)  # Should be truncated
            self.assertIn('... and 3 more', result)
    
    def test_generate_email_content_single_release(self):
        """Test email generation for single release"""
        data = {
            'releases': [self.sample_release]
        }
        
        with patch.dict(os.environ, {'EMAIL_SUBJECT_PREFIX': '[Test]'}):
            subject, body = generate_email_content(data)
        
        self.assertEqual(subject, '[Test] New release: kubernetes/kubernetes v1.28.0')
        self.assertIn('Total new releases: 1', body)
        self.assertIn('kubernetes/kubernetes', body)
        self.assertIn('v1.28.0', body)
    
    def test_generate_email_content_multiple_releases(self):
        """Test email generation for multiple releases"""
        with patch.dict(os.environ, {'EMAIL_SUBJECT_PREFIX': '[Monitor]'}):
            subject, body = generate_email_content(self.sample_releases_data)
        
        self.assertEqual(subject, '[Monitor] 2 new releases detected')
        self.assertIn('Total new releases: 2', body)
        self.assertIn('kubernetes/kubernetes', body)
        self.assertIn('prometheus/prometheus', body)
        self.assertIn('v1.28.0', body)
        self.assertIn('v2.46.0', body)
    
    def test_generate_email_content_no_releases(self):
        """Test email generation with no releases"""
        data = {'releases': []}
        
        subject, body = generate_email_content(data)
        
        self.assertIsNone(subject)
        self.assertIsNone(body)
    
    def test_date_formatting(self):
        """Test date formatting in release details"""
        # Test valid ISO date
        result = format_release_details(self.sample_release)
        self.assertIn('Published: 2023-08-15 12:00 UTC', result)
        
        # Test invalid date
        release = self.sample_release.copy()
        release['published_at'] = 'invalid-date'
        result = format_release_details(release)
        self.assertIn('Published: invalid-date', result)
    
    def test_missing_fields(self):
        """Test handling of missing fields in release data"""
        minimal_release = {
            'repository': 'test/repo',
            'tag_name': 'v1.0.0'
        }
        
        result = format_release_details(minimal_release)
        
        self.assertIn('Repository: test/repo', result)
        self.assertIn('Tag: v1.0.0', result)
        self.assertIn('Release: v1.0.0', result)  # Falls back to tag_name
        self.assertIn('Author: Unknown', result)
        self.assertIn('Published: Unknown', result)
        self.assertIn('URL: #', result)


class TestEmailGenerationScript(unittest.TestCase):
    """Test the main email generation script functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_releases = {
            'timestamp': '2023-08-15T14:00:00+00:00',
            'total_repositories_checked': 1,
            'new_releases_found': 1,
            'releases': [{
                'repository': 'test/repo',
                'tag_name': 'v1.0.0',
                'name': 'Test Release',
                'published_at': '2023-08-15T12:00:00Z',
                'html_url': 'https://github.com/test/repo/releases/tag/v1.0.0',
                'author': {'login': 'testuser'},
                'assets': []
            }]
        }
    
    @patch('generate_email.Path.exists')
    @patch('generate_email.open', new_callable=mock_open)
    @patch('generate_email.Path.mkdir')
    def test_main_with_new_releases(self, mock_mkdir, mock_file_open, mock_exists):
        """Test main function with new releases"""
        # Mock file existence
        mock_exists.return_value = True
        
        # Mock file content
        mock_file_open.return_value.read.return_value = json.dumps(self.test_releases)
        
        # Import and run main
        from generate_email import main
        
        # Should exit with 0 (success)
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 0)
        
        # Verify files were written
        calls = mock_file_open.call_args_list
        
        # Should read releases.json
        self.assertEqual(calls[0][0][0], Path('../release-output/releases.json'))
        self.assertEqual(calls[0][0][1], 'r')
        
        # Should write subject
        self.assertEqual(calls[1][0][0], Path('../email/subject'))
        self.assertEqual(calls[1][0][1], 'w')
        
        # Should write body
        self.assertEqual(calls[2][0][0], Path('../email/body'))
        self.assertEqual(calls[2][0][1], 'w')
        
        # Should write HTML body
        self.assertEqual(calls[3][0][0], Path('../email/body.html'))
        self.assertEqual(calls[3][0][1], 'w')
        
        # Should write headers
        self.assertEqual(calls[4][0][0], Path('../email/headers'))
        self.assertEqual(calls[4][0][1], 'w')
    
    @patch('generate_email.Path.exists')
    def test_main_no_releases_file(self, mock_exists):
        """Test main function when releases file doesn't exist"""
        mock_exists.return_value = False
        
        from generate_email import main
        
        # Should exit with 0 (skip)
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 0)
    
    @patch('generate_email.Path.exists')
    @patch('generate_email.open', new_callable=mock_open)
    def test_main_empty_releases(self, mock_file_open, mock_exists):
        """Test main function with empty releases"""
        mock_exists.return_value = True
        
        # Mock empty releases
        empty_data = {'releases': []}
        mock_file_open.return_value.read.return_value = json.dumps(empty_data)
        
        from generate_email import main
        
        # Should exit with 0 (skip)
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 0)
    
    @patch('generate_email.Path.exists')
    @patch('generate_email.open', new_callable=mock_open)
    def test_main_invalid_json(self, mock_file_open, mock_exists):
        """Test main function with invalid JSON"""
        mock_exists.return_value = True
        
        # Mock invalid JSON
        mock_file_open.return_value.read.return_value = "invalid json"
        
        from generate_email import main
        
        # Should exit with 1 (error)
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 1)


class TestVersionDatabaseFiltering(unittest.TestCase):
    """Test version database filtering functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.sample_releases = [
            {
                'repository': 'kubernetes/kubernetes',
                'tag_name': 'v1.28.0',
                'name': 'Kubernetes v1.28.0',
                'published_at': '2023-08-15T12:00:00Z',
                'html_url': 'https://github.com/kubernetes/kubernetes/releases/tag/v1.28.0',
                'author': {'login': 'k8s-release-robot'},
                'assets': []
            },
            {
                'repository': 'prometheus/prometheus',
                'tag_name': 'v2.46.0',
                'name': 'Prometheus 2.46.0',
                'published_at': '2023-08-15T10:00:00Z',
                'html_url': 'https://github.com/prometheus/prometheus/releases/tag/v2.46.0',
                'author': {'login': 'prombot'},
                'assets': []
            }
        ]
    
    def test_filter_with_no_version_db(self):
        """Test filtering when no version database is available"""
        from generate_email import filter_undownloaded_releases
        
        result = filter_undownloaded_releases(self.sample_releases, None)
        
        # Should return all releases when no version DB
        self.assertEqual(len(result), 2)
        self.assertEqual(result, self.sample_releases)
    
    def test_filter_with_version_db(self):
        """Test filtering with version database"""
        from generate_email import filter_undownloaded_releases
        
        # Mock version database
        mock_version_db = MagicMock()
        mock_version_db.get_current_version.side_effect = lambda owner, repo: {
            ('kubernetes', 'kubernetes'): 'v1.28.0',  # Already downloaded
            ('prometheus', 'prometheus'): 'v2.45.0'   # Older version, new one available
        }.get((owner, repo))
        
        result = filter_undownloaded_releases(self.sample_releases, mock_version_db)
        
        # Should only return prometheus release (kubernetes already downloaded)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['repository'], 'prometheus/prometheus')
        self.assertEqual(result[0]['tag_name'], 'v2.46.0')
    
    def test_filter_with_new_repos(self):
        """Test filtering when repositories have no previous versions"""
        from generate_email import filter_undownloaded_releases
        
        # Mock version database with no existing versions
        mock_version_db = MagicMock()
        mock_version_db.get_current_version.return_value = None
        
        result = filter_undownloaded_releases(self.sample_releases, mock_version_db)
        
        # Should return all releases for new repositories
        self.assertEqual(len(result), 2)
        self.assertEqual(result, self.sample_releases)
    
    def test_filter_with_invalid_repository_format(self):
        """Test filtering with invalid repository format"""
        from generate_email import filter_undownloaded_releases
        
        invalid_releases = [
            {
                'repository': 'invalid-repo-format',
                'tag_name': 'v1.0.0',
                'name': 'Invalid Release',
                'published_at': '2023-08-15T12:00:00Z',
                'html_url': 'https://github.com/invalid',
                'author': {'login': 'user'},
                'assets': []
            }
        ]
        
        mock_version_db = MagicMock()
        result = filter_undownloaded_releases(invalid_releases, mock_version_db)
        
        # Should skip releases with invalid format
        self.assertEqual(len(result), 0)
    
    @patch.dict(os.environ, {'USE_S3_VERSION_DB': 'true', 'VERSION_DB_S3_BUCKET': 'test-bucket'})
    @patch('github_version_s3.S3VersionStorage')
    def test_get_version_database_success(self, mock_s3_class):
        """Test successful version database initialization"""
        from generate_email import get_version_database
        
        mock_instance = MagicMock()
        mock_s3_class.return_value = mock_instance
        
        result = get_version_database()
        
        self.assertIsNotNone(result)
        mock_s3_class.assert_called_once_with(bucket='test-bucket', key_prefix='version-db/')
    
    @patch.dict(os.environ, {'DISABLE_S3_VERSION_DB': 'true'})
    def test_get_version_database_disabled(self):
        """Test version database when disabled"""
        from generate_email import get_version_database
        
        result = get_version_database()
        
        self.assertIsNone(result)
    
    @patch.dict(os.environ, {'USE_S3_VERSION_DB': 'false'})
    def test_get_version_database_not_enabled(self):
        """Test version database when not enabled"""
        from generate_email import get_version_database
        
        result = get_version_database()
        
        self.assertIsNone(result)


class TestAssetFiltering(unittest.TestCase):
    """Test asset filtering functionality for email notifications"""
    
    def setUp(self):
        """Set up test data with Istio 1.26.2 release assets"""
        self.istio_release = {
            'repository': 'istio/istio',
            'owner': 'istio',
            'repo': 'istio',
            'tag_name': '1.26.2',
            'name': 'Istio 1.26.2',
            'published_at': '2024-11-14T20:35:04Z',
            'html_url': 'https://github.com/istio/istio/releases/tag/1.26.2',
            'author': {'login': 'istio-release-robot'},
            'assets': [
                {
                    'name': 'istio-1.26.2-linux-amd64.tar.gz',
                    'size': 23456789,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istio-1.26.2-linux-amd64.tar.gz'
                },
                {
                    'name': 'istio-1.26.2-linux-arm64.tar.gz',
                    'size': 22345678,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istio-1.26.2-linux-arm64.tar.gz'
                },
                {
                    'name': 'istio-1.26.2-osx-amd64.tar.gz',
                    'size': 23567890,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istio-1.26.2-osx-amd64.tar.gz'
                },
                {
                    'name': 'istio-1.26.2-osx-arm64.tar.gz',
                    'size': 23678901,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istio-1.26.2-osx-arm64.tar.gz'
                },
                {
                    'name': 'istio-1.26.2-win.zip',
                    'size': 24567890,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istio-1.26.2-win.zip'
                },
                {
                    'name': 'istioctl-1.26.2-linux-amd64.tar.gz',
                    'size': 12345678,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istioctl-1.26.2-linux-amd64.tar.gz'
                },
                {
                    'name': 'istioctl-1.26.2-linux-arm64.tar.gz',
                    'size': 12234567,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istioctl-1.26.2-linux-arm64.tar.gz'
                },
                {
                    'name': 'istioctl-1.26.2-osx-amd64.tar.gz',
                    'size': 12456789,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istioctl-1.26.2-osx-amd64.tar.gz'
                },
                {
                    'name': 'istioctl-1.26.2-osx-arm64.tar.gz',
                    'size': 12567890,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istioctl-1.26.2-osx-arm64.tar.gz'
                },
                {
                    'name': 'istioctl-1.26.2-win.exe',
                    'size': 13456789,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istioctl-1.26.2-win.exe'
                }
            ]
        }
    
    def filter_istio_assets(self, release, target_asset_name):
        """
        Filter Istio release assets to only include the specified asset.
        
        Args:
            release: Release dictionary with assets
            target_asset_name: Name of the asset to keep
            
        Returns:
            Modified release with filtered assets
        """
        filtered_release = release.copy()
        
        # Filter assets to only include the target asset
        filtered_assets = [
            asset for asset in release.get('assets', [])
            if asset.get('name') == target_asset_name
        ]
        
        filtered_release['assets'] = filtered_assets
        return filtered_release
    
    def test_filter_istio_linux_amd64_only(self):
        """Test filtering Istio 1.26.2 assets to keep only linux-amd64 package"""
        target_asset = 'istio-1.26.2-linux-amd64.tar.gz'
        
        # Filter the release
        filtered_release = self.filter_istio_assets(self.istio_release, target_asset)
        
        # Verify only one asset remains
        self.assertEqual(len(filtered_release['assets']), 1)
        
        # Verify it's the correct asset
        remaining_asset = filtered_release['assets'][0]
        self.assertEqual(remaining_asset['name'], target_asset)
        self.assertEqual(remaining_asset['size'], 23456789)
        self.assertIn('linux-amd64', remaining_asset['browser_download_url'])
        
        # Verify other release metadata is preserved
        self.assertEqual(filtered_release['repository'], 'istio/istio')
        self.assertEqual(filtered_release['tag_name'], '1.26.2')
        self.assertEqual(filtered_release['name'], 'Istio 1.26.2')
    
    def test_filter_nonexistent_asset(self):
        """Test filtering for an asset that doesn't exist"""
        target_asset = 'istio-1.26.2-nonexistent.tar.gz'
        
        # Filter the release
        filtered_release = self.filter_istio_assets(self.istio_release, target_asset)
        
        # Verify no assets remain
        self.assertEqual(len(filtered_release['assets']), 0)
        
        # Verify other release metadata is preserved
        self.assertEqual(filtered_release['repository'], 'istio/istio')
        self.assertEqual(filtered_release['tag_name'], '1.26.2')
    
    def test_email_generation_with_filtered_istio_assets(self):
        """Test email generation with filtered Istio assets"""
        from generate_email import format_release_details
        
        # Filter to only include linux-amd64 asset
        filtered_release = self.filter_istio_assets(
            self.istio_release, 
            'istio-1.26.2-linux-amd64.tar.gz'
        )
        
        # Generate email content
        with patch.dict(os.environ, {'INCLUDE_ASSET_DETAILS': 'true'}):
            email_content = format_release_details(filtered_release)
        
        # Verify the email contains the filtered asset
        self.assertIn('istio-1.26.2-linux-amd64.tar.gz', email_content)
        self.assertIn('22.4 MB', email_content)  # Size in MB
        
        # Verify other assets are not mentioned
        self.assertNotIn('linux-arm64', email_content)
        self.assertNotIn('osx-amd64', email_content)
        self.assertNotIn('osx-arm64', email_content)
        self.assertNotIn('win.zip', email_content)
        self.assertNotIn('istioctl', email_content)
        
        # Verify release metadata is present
        self.assertIn('Repository: istio/istio', email_content)
        self.assertIn('Tag: 1.26.2', email_content)
        self.assertIn('Release: Istio 1.26.2', email_content)
    
    def test_practical_istio_filtering_scenario(self):
        """Test a practical scenario for filtering Istio releases in email notifications"""
        # Simulate what might happen in the email notification pipeline
        releases_data = {
            'timestamp': '2024-11-14T21:00:00Z',
            'total_repositories_checked': 1,
            'new_releases_found': 1,
            'releases': [self.istio_release]
        }
        
        # Apply filtering logic that might be used for specific deployment needs
        # For example, only notify about Linux AMD64 releases for CI/CD systems
        def filter_for_linux_amd64_deployment(releases):
            """Filter releases to only include Linux AMD64 assets for deployment"""
            filtered_releases = []
            
            for release in releases:
                filtered_release = release.copy()
                
                # Keep only Linux AMD64 main package (not istioctl)
                filtered_assets = [
                    asset for asset in release.get('assets', [])
                    if (asset.get('name', '').endswith('-linux-amd64.tar.gz') and
                        not asset.get('name', '').startswith('istioctl-'))
                ]
                
                if filtered_assets:
                    filtered_release['assets'] = filtered_assets
                    filtered_releases.append(filtered_release)
            
            return filtered_releases
        
        # Apply the filtering
        filtered_releases = filter_for_linux_amd64_deployment(releases_data['releases'])
        
        # Verify results
        self.assertEqual(len(filtered_releases), 1)
        self.assertEqual(len(filtered_releases[0]['assets']), 1)
        self.assertEqual(
            filtered_releases[0]['assets'][0]['name'], 
            'istio-1.26.2-linux-amd64.tar.gz'
        )
        
        # Update the releases data
        filtered_releases_data = releases_data.copy()
        filtered_releases_data['releases'] = filtered_releases
        
        # Generate email content
        from generate_email import generate_email_content
        with patch.dict(os.environ, {'EMAIL_SUBJECT_PREFIX': '[Istio Deploy]'}):
            subject, body = generate_email_content(filtered_releases_data)
        
        # Verify email content
        self.assertEqual(subject, '[Istio Deploy] New release: istio/istio 1.26.2')
        self.assertIn('Total new releases: 1', body)
        self.assertIn('istio/istio', body)
        self.assertIn('1.26.2', body)


class TestAssetPatternsFiltering(unittest.TestCase):
    """Test ASSET_PATTERNS parameter filtering for Istio releases"""
    
    def setUp(self):
        """Set up test data for asset patterns testing"""
        # Add the repo root to path so we can import GitHubDownloader
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        
        from github_downloader import GitHubDownloader
        self.GitHubDownloader = GitHubDownloader
        
        # Sample Istio 1.26.2 release with all assets
        self.istio_release_data = {
            'id': 12345,
            'tag_name': '1.26.2',
            'name': 'Istio 1.26.2',
            'published_at': '2024-11-14T20:35:04Z',
            'html_url': 'https://github.com/istio/istio/releases/tag/1.26.2',
            'assets': [
                {
                    'id': 1001,
                    'name': 'istio-1.26.2-linux-amd64.tar.gz',
                    'size': 23456789,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istio-1.26.2-linux-amd64.tar.gz',
                    'content_type': 'application/gzip'
                },
                {
                    'id': 1002,
                    'name': 'istio-1.26.2-linux-arm64.tar.gz',
                    'size': 22345678,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istio-1.26.2-linux-arm64.tar.gz',
                    'content_type': 'application/gzip'
                },
                {
                    'id': 1003,
                    'name': 'istio-1.26.2-osx-amd64.tar.gz',
                    'size': 23567890,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istio-1.26.2-osx-amd64.tar.gz',
                    'content_type': 'application/gzip'
                },
                {
                    'id': 1004,
                    'name': 'istio-1.26.2-osx-arm64.tar.gz',
                    'size': 23678901,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istio-1.26.2-osx-arm64.tar.gz',
                    'content_type': 'application/gzip'
                },
                {
                    'id': 1005,
                    'name': 'istio-1.26.2-win.zip',
                    'size': 24567890,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istio-1.26.2-win.zip',
                    'content_type': 'application/zip'
                },
                {
                    'id': 1006,
                    'name': 'istioctl-1.26.2-linux-amd64.tar.gz',
                    'size': 12345678,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istioctl-1.26.2-linux-amd64.tar.gz',
                    'content_type': 'application/gzip'
                },
                {
                    'id': 1007,
                    'name': 'istioctl-1.26.2-linux-arm64.tar.gz',
                    'size': 12234567,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istioctl-1.26.2-linux-arm64.tar.gz',
                    'content_type': 'application/gzip'
                },
                {
                    'id': 1008,
                    'name': 'istioctl-1.26.2-osx-amd64.tar.gz',
                    'size': 12456789,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istioctl-1.26.2-osx-amd64.tar.gz',
                    'content_type': 'application/gzip'
                },
                {
                    'id': 1009,
                    'name': 'istioctl-1.26.2-osx-arm64.tar.gz',
                    'size': 12567890,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istioctl-1.26.2-osx-arm64.tar.gz',
                    'content_type': 'application/gzip'
                },
                {
                    'id': 1010,
                    'name': 'istioctl-1.26.2-win.exe',
                    'size': 13456789,
                    'browser_download_url': 'https://github.com/istio/istio/releases/download/1.26.2/istioctl-1.26.2-win.exe',
                    'content_type': 'application/octet-stream'
                }
            ]
        }
    
    def test_asset_patterns_filter_amd64_tarballs_only(self):
        """Test ASSET_PATTERNS filtering to keep only AMD64 tarballs from Istio 1.26.2"""
        # Create a temporary directory for downloads
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            # Initialize downloader
            downloader = self.GitHubDownloader(
                token="fake-token",
                download_dir=temp_dir
            )
            
            # Define asset patterns to only match AMD64 tarballs
            asset_patterns = ["*-amd64.tar.gz"]
            
            # Get the list of assets that would be downloaded
            matching_assets = []
            for asset in self.istio_release_data['assets']:
                if downloader._matches_patterns(asset['name'], asset_patterns):
                    matching_assets.append(asset)
            
            # Verify only AMD64 tarballs are matched
            self.assertEqual(len(matching_assets), 4)  # 2 istio + 2 istioctl amd64 variants
            
            expected_assets = [
                'istio-1.26.2-linux-amd64.tar.gz',
                'istio-1.26.2-osx-amd64.tar.gz', 
                'istioctl-1.26.2-linux-amd64.tar.gz',
                'istioctl-1.26.2-osx-amd64.tar.gz'
            ]
            
            matching_names = [asset['name'] for asset in matching_assets]
            for expected_name in expected_assets:
                self.assertIn(expected_name, matching_names)
            
            # Verify excluded assets
            excluded_assets = [
                'istio-1.26.2-linux-arm64.tar.gz',
                'istio-1.26.2-osx-arm64.tar.gz', 
                'istio-1.26.2-win.zip',
                'istioctl-1.26.2-linux-arm64.tar.gz',
                'istioctl-1.26.2-osx-arm64.tar.gz',
                'istioctl-1.26.2-win.exe'
            ]
            
            for excluded_name in excluded_assets:
                self.assertNotIn(excluded_name, matching_names)
    
    def test_asset_patterns_filter_linux_amd64_only(self):
        """Test ASSET_PATTERNS filtering to keep only Linux AMD64 tarballs"""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader = self.GitHubDownloader(
                token="fake-token",
                download_dir=temp_dir
            )
            
            # Define asset patterns to only match Linux AMD64 tarballs
            asset_patterns = ["*-linux-amd64.tar.gz"]
            
            # Get matching assets
            matching_assets = []
            for asset in self.istio_release_data['assets']:
                if downloader._matches_patterns(asset['name'], asset_patterns):
                    matching_assets.append(asset)
            
            # Verify only Linux AMD64 tarballs are matched
            self.assertEqual(len(matching_assets), 2)
            
            expected_assets = [
                'istio-1.26.2-linux-amd64.tar.gz',
                'istioctl-1.26.2-linux-amd64.tar.gz'
            ]
            
            matching_names = [asset['name'] for asset in matching_assets]
            for expected_name in expected_assets:
                self.assertIn(expected_name, matching_names)
            
            # Verify all other assets are excluded
            self.assertEqual(len(self.istio_release_data['assets']) - len(matching_assets), 8)
    
    def test_asset_patterns_exclude_istioctl(self):
        """Test ASSET_PATTERNS filtering to exclude istioctl, keep only main istio AMD64"""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader = self.GitHubDownloader(
                token="fake-token",
                download_dir=temp_dir
            )
            
            # Define asset patterns: include AMD64 tarballs but exclude istioctl
            asset_patterns = ["*-amd64.tar.gz", "!istioctl-*"]
            
            # Get matching assets
            matching_assets = []
            for asset in self.istio_release_data['assets']:
                if downloader._matches_patterns(asset['name'], asset_patterns):
                    matching_assets.append(asset)
            
            # Verify only main istio AMD64 packages (no istioctl)
            self.assertEqual(len(matching_assets), 2)
            
            expected_assets = [
                'istio-1.26.2-linux-amd64.tar.gz',
                'istio-1.26.2-osx-amd64.tar.gz'
            ]
            
            matching_names = [asset['name'] for asset in matching_assets]
            for expected_name in expected_assets:
                self.assertIn(expected_name, matching_names)
            
            # Verify istioctl packages are excluded
            for name in matching_names:
                self.assertNotIn('istioctl', name)
    
    def test_asset_patterns_single_specific_file(self):
        """Test ASSET_PATTERNS filtering to get only istio-1.26.2-linux-amd64.tar.gz"""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader = self.GitHubDownloader(
                token="fake-token",
                download_dir=temp_dir
            )
            
            # Define very specific pattern for exactly one file
            asset_patterns = ["istio-1.26.2-linux-amd64.tar.gz"]
            
            # Get matching assets
            matching_assets = []
            for asset in self.istio_release_data['assets']:
                if downloader._matches_patterns(asset['name'], asset_patterns):
                    matching_assets.append(asset)
            
            # Verify only one specific asset matches
            self.assertEqual(len(matching_assets), 1)
            self.assertEqual(matching_assets[0]['name'], 'istio-1.26.2-linux-amd64.tar.gz')
            self.assertEqual(matching_assets[0]['size'], 23456789)
    
    def test_asset_patterns_real_world_deployment_scenario(self):
        """Test realistic deployment scenario filtering"""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader = self.GitHubDownloader(
                token="fake-token",
                download_dir=temp_dir
            )
            
            # Real-world scenario: CI/CD system that only needs Linux AMD64 
            # main istio package for deployment, not istioctl or other platforms
            asset_patterns = ["istio-*.tar.gz", "!istioctl-*", "!*-arm64*", "!*-osx-*", "!*-win*"]
            
            # Get matching assets
            matching_assets = []
            for asset in self.istio_release_data['assets']:
                if downloader._matches_patterns(asset['name'], asset_patterns):
                    matching_assets.append(asset)
            
            # Should match only the main istio Linux AMD64 package
            self.assertEqual(len(matching_assets), 1)
            self.assertEqual(matching_assets[0]['name'], 'istio-1.26.2-linux-amd64.tar.gz')
            
            # Verify it's the right size (matches our test data)
            self.assertEqual(matching_assets[0]['size'], 23456789)
    
    def test_asset_patterns_demonstrate_filtering_power(self):
        """Comprehensive test demonstrating the power of ASSET_PATTERNS filtering"""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader = self.GitHubDownloader(
                token="fake-token",
                download_dir=temp_dir
            )
            
            # Test multiple filtering scenarios
            test_scenarios = [
                {
                    'name': 'All AMD64 tarballs',
                    'patterns': ['*-amd64.tar.gz'],
                    'expected_count': 4,
                    'expected_includes': ['istio-1.26.2-linux-amd64.tar.gz', 'istioctl-1.26.2-linux-amd64.tar.gz']
                },
                {
                    'name': 'Only Linux AMD64',
                    'patterns': ['*-linux-amd64.tar.gz'],
                    'expected_count': 2,
                    'expected_includes': ['istio-1.26.2-linux-amd64.tar.gz', 'istioctl-1.26.2-linux-amd64.tar.gz']
                },
                {
                    'name': 'Main istio only (no istioctl)',
                    'patterns': ['istio-*.tar.gz', '!istioctl-*'],
                    'expected_count': 4,
                    'expected_includes': ['istio-1.26.2-linux-amd64.tar.gz', 'istio-1.26.2-osx-amd64.tar.gz']
                },
                {
                    'name': 'Single specific file',
                    'patterns': ['istio-1.26.2-linux-amd64.tar.gz'],
                    'expected_count': 1,
                    'expected_includes': ['istio-1.26.2-linux-amd64.tar.gz']
                },
                {
                    'name': 'No Windows files',
                    'patterns': ['*.tar.gz', '!*-win*'],
                    'expected_count': 8,  # All tarballs, excluding win.zip and win.exe
                    'expected_excludes': ['istio-1.26.2-win.zip', 'istioctl-1.26.2-win.exe']
                }
            ]
            
            print(f"\n{'='*60}")
            print(f"ASSET_PATTERNS Filtering Demonstration - Istio 1.26.2")
            print(f"{'='*60}")
            print(f"Original release has {len(self.istio_release_data['assets'])} assets:")
            for asset in self.istio_release_data['assets']:
                size_mb = asset['size'] / (1024 * 1024)
                print(f"  - {asset['name']} ({size_mb:.1f} MB)")
            
            for scenario in test_scenarios:
                print(f"\n{'-'*40}")
                print(f"Scenario: {scenario['name']}")
                print(f"Patterns: {scenario['patterns']}")
                
                # Apply filtering
                matching_assets = []
                for asset in self.istio_release_data['assets']:
                    if downloader._matches_patterns(asset['name'], scenario['patterns']):
                        matching_assets.append(asset)
                
                # Verify count
                self.assertEqual(len(matching_assets), scenario['expected_count'])
                print(f"Matched {len(matching_assets)} assets:")
                
                matching_names = [asset['name'] for asset in matching_assets]
                for asset in matching_assets:
                    size_mb = asset['size'] / (1024 * 1024)
                    print(f"  ✓ {asset['name']} ({size_mb:.1f} MB)")
                
                # Verify expected includes
                if 'expected_includes' in scenario:
                    for expected_name in scenario['expected_includes']:
                        self.assertIn(expected_name, matching_names)
                
                # Verify expected excludes
                if 'expected_excludes' in scenario:
                    for excluded_name in scenario['expected_excludes']:
                        self.assertNotIn(excluded_name, matching_names)
            
            print(f"\n{'='*60}")
            print("✅ All ASSET_PATTERNS filtering scenarios verified!")
            print(f"{'='*60}")


class TestGatekeeperAssetPatterns(unittest.TestCase):
    """Test ASSET_PATTERNS filtering for Gatekeeper releases"""
    
    def setUp(self):
        """Set up test data for Gatekeeper pattern testing"""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        
        from github_downloader import GitHubDownloader
        self.GitHubDownloader = GitHubDownloader
        
        # Sample Gatekeeper v3.14.0 release data
        self.gatekeeper_release_data = {
            'id': 987654321,
            'tag_name': 'v3.14.0',
            'name': 'Gatekeeper v3.14.0',
            'published_at': '2023-11-15T18:30:00Z',
            'html_url': 'https://github.com/open-policy-agent/gatekeeper/releases/tag/v3.14.0',
            'assets': [
                # Gator CLI binaries
                {
                    'id': 2001,
                    'name': 'gator-v3.14.0-linux-amd64.tar.gz',
                    'size': 15234567,
                    'browser_download_url': 'https://github.com/open-policy-agent/gatekeeper/releases/download/v3.14.0/gator-v3.14.0-linux-amd64.tar.gz',
                    'content_type': 'application/gzip'
                },
                {
                    'id': 2002,
                    'name': 'gator-v3.14.0-linux-arm64.tar.gz',
                    'size': 14876543,
                    'browser_download_url': 'https://github.com/open-policy-agent/gatekeeper/releases/download/v3.14.0/gator-v3.14.0-linux-arm64.tar.gz',
                    'content_type': 'application/gzip'
                },
                {
                    'id': 2003,
                    'name': 'gator-v3.14.0-darwin-amd64.tar.gz',
                    'size': 15456789,
                    'browser_download_url': 'https://github.com/open-policy-agent/gatekeeper/releases/download/v3.14.0/gator-v3.14.0-darwin-amd64.tar.gz',
                    'content_type': 'application/gzip'
                },
                {
                    'id': 2004,
                    'name': 'gator-v3.14.0-windows-amd64.tar.gz',
                    'size': 16234567,
                    'browser_download_url': 'https://github.com/open-policy-agent/gatekeeper/releases/download/v3.14.0/gator-v3.14.0-windows-amd64.tar.gz',
                    'content_type': 'application/gzip'
                },
                # Manager binaries
                {
                    'id': 2005,
                    'name': 'manager-v3.14.0-linux-amd64.tar.gz',
                    'size': 45234567,
                    'browser_download_url': 'https://github.com/open-policy-agent/gatekeeper/releases/download/v3.14.0/manager-v3.14.0-linux-amd64.tar.gz',
                    'content_type': 'application/gzip'
                },
                {
                    'id': 2006,
                    'name': 'manager-v3.14.0-linux-arm64.tar.gz',
                    'size': 44876543,
                    'browser_download_url': 'https://github.com/open-policy-agent/gatekeeper/releases/download/v3.14.0/manager-v3.14.0-linux-arm64.tar.gz',
                    'content_type': 'application/gzip'
                },
                {
                    'id': 2007,
                    'name': 'manager-v3.14.0-darwin-amd64.tar.gz',
                    'size': 45456789,
                    'browser_download_url': 'https://github.com/open-policy-agent/gatekeeper/releases/download/v3.14.0/manager-v3.14.0-darwin-amd64.tar.gz',
                    'content_type': 'application/gzip'
                },
                # Additional assets
                {
                    'id': 2008,
                    'name': 'gatekeeper-v3.14.0-helm-chart.tgz',
                    'size': 12345,
                    'browser_download_url': 'https://github.com/open-policy-agent/gatekeeper/releases/download/v3.14.0/gatekeeper-v3.14.0-helm-chart.tgz',
                    'content_type': 'application/gzip'
                },
                {
                    'id': 2009,
                    'name': 'gatekeeper-v3.14.0-manifests.yaml',
                    'size': 67890,
                    'browser_download_url': 'https://github.com/open-policy-agent/gatekeeper/releases/download/v3.14.0/gatekeeper-v3.14.0-manifests.yaml',
                    'content_type': 'text/yaml'
                }
            ]
        }
    
    def test_specific_gatekeeper_pattern(self):
        """Test the specific pattern: ['gator-v*-linux-amd64.tar.gz', '*-linux-amd64.tar.gz']"""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader = self.GitHubDownloader(
                token="fake-token",
                download_dir=temp_dir
            )
            
            # Your specific pattern
            asset_patterns = ['gator-v*-linux-amd64.tar.gz', '*-linux-amd64.tar.gz']
            
            # Get matching assets
            matching_assets = []
            for asset in self.gatekeeper_release_data['assets']:
                if downloader._matches_patterns(asset['name'], asset_patterns):
                    matching_assets.append(asset)
            
            # Verify exactly 2 assets match (gator + manager, both Linux AMD64)
            self.assertEqual(len(matching_assets), 2)
            
            expected_assets = [
                'gator-v3.14.0-linux-amd64.tar.gz',
                'manager-v3.14.0-linux-amd64.tar.gz'
            ]
            
            matching_names = [asset['name'] for asset in matching_assets]
            for expected_name in expected_assets:
                self.assertIn(expected_name, matching_names)
            
            # Verify excluded assets
            excluded_assets = [
                'gator-v3.14.0-linux-arm64.tar.gz',
                'gator-v3.14.0-darwin-amd64.tar.gz',
                'gator-v3.14.0-windows-amd64.tar.gz',
                'manager-v3.14.0-linux-arm64.tar.gz',
                'manager-v3.14.0-darwin-amd64.tar.gz',
                'gatekeeper-v3.14.0-helm-chart.tgz',
                'gatekeeper-v3.14.0-manifests.yaml'
            ]
            
            for excluded_name in excluded_assets:
                self.assertNotIn(excluded_name, matching_names)
            
            # Verify file sizes
            gator_asset = next(a for a in matching_assets if 'gator' in a['name'])
            manager_asset = next(a for a in matching_assets if 'manager' in a['name'])
            
            self.assertEqual(gator_asset['size'], 15234567)  # ~14.5 MB
            self.assertEqual(manager_asset['size'], 45234567)  # ~43.1 MB
    
    def test_gator_cli_only_pattern(self):
        """Test pattern for Gator CLI only: ['gator-v*-linux-amd64.tar.gz']"""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader = self.GitHubDownloader(
                token="fake-token",
                download_dir=temp_dir
            )
            
            # Gator CLI only pattern
            asset_patterns = ['gator-v*-linux-amd64.tar.gz']
            
            # Get matching assets
            matching_assets = []
            for asset in self.gatekeeper_release_data['assets']:
                if downloader._matches_patterns(asset['name'], asset_patterns):
                    matching_assets.append(asset)
            
            # Verify only 1 asset matches (gator CLI only)
            self.assertEqual(len(matching_assets), 1)
            self.assertEqual(matching_assets[0]['name'], 'gator-v3.14.0-linux-amd64.tar.gz')
            
            # Verify manager is excluded
            matching_names = [asset['name'] for asset in matching_assets]
            self.assertNotIn('manager-v3.14.0-linux-amd64.tar.gz', matching_names)
    
    def test_manager_only_pattern(self):
        """Test pattern for Manager only: ['manager-v*-linux-amd64.tar.gz']"""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader = self.GitHubDownloader(
                token="fake-token",
                download_dir=temp_dir
            )
            
            # Manager only pattern
            asset_patterns = ['manager-v*-linux-amd64.tar.gz']
            
            # Get matching assets
            matching_assets = []
            for asset in self.gatekeeper_release_data['assets']:
                if downloader._matches_patterns(asset['name'], asset_patterns):
                    matching_assets.append(asset)
            
            # Verify only 1 asset matches (manager only)
            self.assertEqual(len(matching_assets), 1)
            self.assertEqual(matching_assets[0]['name'], 'manager-v3.14.0-linux-amd64.tar.gz')
            
            # Verify gator is excluded
            matching_names = [asset['name'] for asset in matching_assets]
            self.assertNotIn('gator-v3.14.0-linux-amd64.tar.gz', matching_names)
    
    def test_all_linux_amd64_pattern(self):
        """Test pattern for all Linux AMD64: ['*-linux-amd64.tar.gz']"""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader = self.GitHubDownloader(
                token="fake-token",
                download_dir=temp_dir
            )
            
            # All Linux AMD64 pattern
            asset_patterns = ['*-linux-amd64.tar.gz']
            
            # Get matching assets
            matching_assets = []
            for asset in self.gatekeeper_release_data['assets']:
                if downloader._matches_patterns(asset['name'], asset_patterns):
                    matching_assets.append(asset)
            
            # Verify 2 assets match (gator + manager, both Linux AMD64)
            self.assertEqual(len(matching_assets), 2)
            
            expected_assets = [
                'gator-v3.14.0-linux-amd64.tar.gz',
                'manager-v3.14.0-linux-amd64.tar.gz'
            ]
            
            matching_names = [asset['name'] for asset in matching_assets]
            for expected_name in expected_assets:
                self.assertIn(expected_name, matching_names)
    
    def test_multi_platform_gator_pattern(self):
        """Test pattern for multi-platform Gator: ['gator-v*']"""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader = self.GitHubDownloader(
                token="fake-token",
                download_dir=temp_dir
            )
            
            # Multi-platform Gator pattern
            asset_patterns = ['gator-v*']
            
            # Get matching assets
            matching_assets = []
            for asset in self.gatekeeper_release_data['assets']:
                if downloader._matches_patterns(asset['name'], asset_patterns):
                    matching_assets.append(asset)
            
            # Verify 4 Gator assets match (all platforms)
            self.assertEqual(len(matching_assets), 4)
            
            # All should be gator assets
            for asset in matching_assets:
                self.assertTrue(asset['name'].startswith('gator-v'))
                self.assertFalse(asset['name'].startswith('manager-v'))
    
    def test_config_only_pattern(self):
        """Test pattern for config only: ['*.yaml', '*.yml', '*.tgz']"""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader = self.GitHubDownloader(
                token="fake-token",
                download_dir=temp_dir
            )
            
            # Config only pattern
            asset_patterns = ['*.yaml', '*.yml', '*.tgz']
            
            # Get matching assets
            matching_assets = []
            for asset in self.gatekeeper_release_data['assets']:
                if downloader._matches_patterns(asset['name'], asset_patterns):
                    matching_assets.append(asset)
            
            # Verify 2 config assets match
            self.assertEqual(len(matching_assets), 2)
            
            expected_assets = [
                'gatekeeper-v3.14.0-helm-chart.tgz',
                'gatekeeper-v3.14.0-manifests.yaml'
            ]
            
            matching_names = [asset['name'] for asset in matching_assets]
            for expected_name in expected_assets:
                self.assertIn(expected_name, matching_names)
            
            # Verify no binary assets
            for asset in matching_assets:
                self.assertNotIn('.tar.gz', asset['name'])


class TestHTMLGeneration(unittest.TestCase):
    """Test HTML email generation"""
    
    def setUp(self):
        """Set up test data"""
        self.sample_release = {
            'repository': 'kubernetes/kubernetes',
            'tag_name': 'v1.28.0',
            'name': 'Kubernetes v1.28.0',
            'published_at': '2023-08-15T12:00:00Z',
            'html_url': 'https://github.com/kubernetes/kubernetes/releases/tag/v1.28.0',
            'author': {'login': 'k8s-release-robot'},
            'assets': [
                {
                    'name': 'kubernetes.tar.gz',
                    'size': 50331648,
                    'browser_download_url': 'https://example.com/download'
                }
            ]
        }
    
    @patch('generate_email.Path.exists')
    @patch('generate_email.open', new_callable=mock_open)
    @patch('generate_email.Path.mkdir')
    def test_html_generation(self, mock_mkdir, mock_file_open, mock_exists):
        """Test HTML email generation"""
        mock_exists.return_value = True
        
        releases_data = {'releases': [self.sample_release]}
        mock_file_open.return_value.read.return_value = json.dumps(releases_data)
        
        from generate_email import main
        
        with self.assertRaises(SystemExit):
            main()
        
        # Get HTML content from write calls
        html_write_call = None
        for call in mock_file_open.return_value.write.call_args_list:
            content = call[0][0]
            if '<html>' in content:
                html_write_call = content
                break
        
        self.assertIsNotNone(html_write_call)
        self.assertIn('<h2>New GitHub Releases Detected</h2>', html_write_call)
        self.assertIn('kubernetes/kubernetes', html_write_call)
        self.assertIn('v1.28.0', html_write_call)
        self.assertIn('<a href="https://github.com/kubernetes/kubernetes/releases/tag/v1.28.0">', 
                     html_write_call)
        
        # Check asset link when INCLUDE_ASSET_DETAILS is true
        with patch.dict(os.environ, {'INCLUDE_ASSET_DETAILS': 'true'}):
            self.assertIn('kubernetes.tar.gz', html_write_call)


if __name__ == '__main__':
    unittest.main()