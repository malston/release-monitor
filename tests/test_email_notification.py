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