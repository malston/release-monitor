#!/usr/bin/env python3
"""
Unit tests for GitHub Downloader
"""

import unittest
import tempfile
import os
import json
import hashlib
from unittest.mock import patch, Mock, MagicMock
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from github_downloader import GitHubDownloader


class TestGitHubDownloader(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock the session creation to avoid network initialization
        with patch('requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            
            self.downloader = GitHubDownloader(
                token='test_token',
                download_dir=self.temp_dir,
                timeout=10
            )
            
            # Store the mock session for test use
            self.mock_session = mock_session
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test downloader initialization."""
        self.assertEqual(str(self.downloader.download_dir), self.temp_dir)
        self.assertTrue(self.downloader.download_dir.exists())
        self.assertEqual(self.downloader.timeout, 10)
        # Verify session was mocked
        self.assertEqual(self.downloader.session, self.mock_session)
    
    def test_pattern_matching(self):
        """Test asset pattern matching."""
        patterns = ['*.tar.gz', '*.zip', '!*sources*']
        
        # Should match
        self.assertTrue(self.downloader._matches_patterns('file.tar.gz', patterns))
        self.assertTrue(self.downloader._matches_patterns('release.zip', patterns))
        
        # Should not match (exclusion)
        self.assertFalse(self.downloader._matches_patterns('sources-1.0.zip', patterns))
        
        # Should not match (no pattern match)
        self.assertFalse(self.downloader._matches_patterns('readme.txt', patterns))
    
    def test_pattern_matching_case_insensitive(self):
        """Test pattern matching is case insensitive."""
        patterns = ['*.ZIP', '*.Tar.Gz']
        
        self.assertTrue(self.downloader._matches_patterns('file.zip', patterns))
        self.assertTrue(self.downloader._matches_patterns('FILE.ZIP', patterns))
        self.assertTrue(self.downloader._matches_patterns('release.tar.gz', patterns))
    
    def test_download_with_retry_success(self):
        """Test successful download with retry logic."""
        # Mock successful response on the session
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {'content-length': '12'}  # Match actual content length
        mock_response.iter_content.return_value = [b'test content']
        self.mock_session.get.return_value = mock_response
        
        # Create test file path
        test_file = Path(self.temp_dir) / 'test.txt'
        
        # Test the download
        asset = {'size': 12}  # Length of 'test content'
        success, error = self.downloader._download_with_retry(
            'https://example.com/file.txt', test_file, asset
        )
        
        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertTrue(test_file.exists())
        self.assertEqual(test_file.read_text(), 'test content')
        
        # Check checksum file was created
        checksum_file = test_file.with_suffix('.txt.sha256')
        self.assertTrue(checksum_file.exists())
    
    def test_download_with_retry_failure(self):
        """Test download failure and retry logic."""
        # Mock failed response
        self.mock_session.get.side_effect = Exception("Network error")
        
        test_file = Path(self.temp_dir) / 'test.txt'
        asset = {'size': 1024}
        
        success, error = self.downloader._download_with_retry(
            'https://example.com/file.txt', test_file, asset, max_retries=2
        )
        
        self.assertFalse(success)
        self.assertIn("Failed after 3 attempts", error)
        self.assertFalse(test_file.exists())
    
    def test_verify_download_success(self):
        """Test download verification with correct checksum."""
        # Create test file
        test_content = b'test file content'
        test_file = Path(self.temp_dir) / 'test.txt'
        test_file.write_bytes(test_content)
        
        # Create checksum file
        expected_hash = hashlib.sha256(test_content).hexdigest()
        checksum_file = test_file.with_suffix('.txt.sha256')
        checksum_file.write_text(f"{expected_hash}  test.txt\n")
        
        # Verify
        result = self.downloader.verify_download(test_file)
        
        self.assertTrue(result['verified'])
        self.assertTrue(result['checksum_match'])
        self.assertEqual(result['sha256'], expected_hash)
        self.assertEqual(result['file_size'], len(test_content))
    
    def test_verify_download_checksum_mismatch(self):
        """Test download verification with incorrect checksum."""
        # Create test file
        test_content = b'test file content'
        test_file = Path(self.temp_dir) / 'test.txt'
        test_file.write_bytes(test_content)
        
        # Create checksum file with wrong hash
        checksum_file = test_file.with_suffix('.txt.sha256')
        checksum_file.write_text("wronghash  test.txt\n")
        
        # Verify
        result = self.downloader.verify_download(test_file)
        
        self.assertTrue(result['verified'])  # File exists and can be read
        self.assertFalse(result['checksum_match'])  # But checksum doesn't match
        self.assertIn('error', result)
    
    def test_verify_download_missing_file(self):
        """Test verification of non-existent file."""
        test_file = Path(self.temp_dir) / 'nonexistent.txt'
        
        result = self.downloader.verify_download(test_file)
        
        self.assertFalse(result['verified'])
        self.assertIn('does not exist', result['error'])
    
    def test_download_stats_empty(self):
        """Test download stats for empty directory."""
        stats = self.downloader.get_download_stats()
        
        self.assertEqual(stats['total_files'], 0)
        self.assertEqual(stats['total_size'], 0)
        self.assertEqual(stats['repositories'], 0)
    
    def test_download_stats_with_files(self):
        """Test download stats with downloaded files."""
        # Create mock downloaded files
        repo_dir = Path(self.temp_dir) / 'test_repo'
        version_dir = repo_dir / 'v1.0.0'
        version_dir.mkdir(parents=True)
        
        # Create test files
        (version_dir / 'file1.txt').write_bytes(b'content1')
        (version_dir / 'file2.txt').write_bytes(b'content2')
        (version_dir / 'file1.txt.sha256').write_text('checksum')  # Should be ignored
        
        stats = self.downloader.get_download_stats()
        
        self.assertEqual(stats['total_files'], 2)
        self.assertEqual(stats['total_size'], 16)  # 8 + 8 bytes
        self.assertEqual(stats['repositories'], 1)
    
    def test_cleanup_old_downloads(self):
        """Test cleanup of old downloaded versions."""
        # Create mock repository with multiple versions
        repo_dir = Path(self.temp_dir) / 'test_repo'
        
        versions = ['v1.0.0', 'v1.1.0', 'v1.2.0', 'v1.3.0']
        for i, version in enumerate(versions):
            version_dir = repo_dir / version
            version_dir.mkdir(parents=True)
            
            # Create test file
            test_file = version_dir / 'file.txt'
            test_file.write_bytes(b'x' * 100)  # 100 bytes
            
            # Set different modification times
            import time
            os.utime(test_file, (time.time() - (len(versions) - i) * 3600, 
                                time.time() - (len(versions) - i) * 3600))
        
        # Keep only 2 versions
        cleanup_stats = self.downloader.cleanup_old_downloads(keep_versions=2)
        
        # Should have cleaned up 2 old versions
        self.assertEqual(cleanup_stats['cleaned_files'], 2)
        self.assertEqual(cleanup_stats['freed_space'], 200)  # 2 * 100 bytes
        
        # Check that only newest 2 versions remain
        remaining_versions = [d.name for d in repo_dir.iterdir() if d.is_dir()]
        remaining_versions.sort()
        self.assertEqual(len(remaining_versions), 2)
    
    @patch('github_downloader.GitHubDownloader._download_with_retry')
    def test_download_release_assets_success(self, mock_download):
        """Test downloading release assets."""
        # Mock successful download
        mock_download.return_value = (True, None)
        
        # Create test release data
        release_data = {
            'repository': 'test/repo',
            'tag_name': 'v1.0.0',
            'assets': [
                {
                    'name': 'release.tar.gz',
                    'browser_download_url': 'https://example.com/release.tar.gz',
                    'size': 1024
                },
                {
                    'name': 'checksums.txt',
                    'browser_download_url': 'https://example.com/checksums.txt',
                    'size': 256
                }
            ]
        }
        
        # Download assets
        results = self.downloader.download_release_assets(release_data)
        
        # Should have attempted to download both assets
        self.assertEqual(len(results), 2)
        self.assertEqual(mock_download.call_count, 2)
    
    def test_download_release_assets_with_patterns(self):
        """Test downloading with asset patterns filtering."""
        release_data = {
            'repository': 'test/repo',
            'tag_name': 'v1.0.0',
            'assets': [
                {'name': 'release.tar.gz', 'browser_download_url': 'https://example.com/release.tar.gz'},
                {'name': 'sources.zip', 'browser_download_url': 'https://example.com/sources.zip'},
                {'name': 'readme.txt', 'browser_download_url': 'https://example.com/readme.txt'}
            ]
        }
        
        # Only download .tar.gz and .zip files
        patterns = ['*.tar.gz', '*.zip']
        
        with patch.object(self.downloader, '_download_single_asset') as mock_download:
            mock_download.return_value = {'success': True}
            
            results = self.downloader.download_release_assets(release_data, patterns)
            
            # Should only download 2 assets (tar.gz and zip)
            self.assertEqual(len(results), 2)
    
    def test_download_release_assets_no_assets(self):
        """Test handling release with no assets."""
        release_data = {
            'repository': 'test/repo',
            'tag_name': 'v1.0.0',
            'assets': []
        }
        
        results = self.downloader.download_release_assets(release_data)
        
        self.assertEqual(len(results), 0)


if __name__ == '__main__':
    unittest.main()