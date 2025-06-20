#!/usr/bin/env python3
"""
Unit tests for S3-based Version Storage
"""

import unittest
import tempfile
import os
import json
from unittest.mock import patch, Mock, MagicMock
import sys
from pathlib import Path
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from github_version_s3 import S3VersionStorage, VersionDatabase


class TestS3VersionStorage(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment."""
        self.bucket = 'test-bucket'
        self.prefix = 'test-prefix/'
        
        # Mock S3 client
        self.mock_s3 = Mock()
        self.storage = S3VersionStorage(self.bucket, self.prefix)
        self.storage.s3_client = self.mock_s3
    
    def test_initialization(self):
        """Test storage initialization."""
        self.assertEqual(self.storage.bucket, self.bucket)
        self.assertEqual(self.storage.key_prefix, self.prefix)
        self.assertEqual(self.storage.versions_key, f"{self.prefix}version_db.json")
    
    def test_load_from_s3_existing(self):
        """Test loading existing data from S3."""
        test_data = {
            'repositories': {
                'test/repo': {
                    'current_version': 'v1.0.0',
                    'last_updated': '2024-01-01T00:00:00Z'
                }
            },
            'metadata': {
                'version': '2.0'
            }
        }
        
        # Mock S3 response
        self.mock_s3.get_object.return_value = {
            'Body': Mock(read=Mock(return_value=json.dumps(test_data).encode('utf-8'))),
            'ETag': '"test-etag"'
        }
        
        data = self.storage._load_from_s3()
        
        self.assertEqual(data['repositories']['test/repo']['current_version'], 'v1.0.0')
        self.mock_s3.get_object.assert_called_once_with(
            Bucket=self.bucket,
            Key=self.storage.versions_key
        )
    
    def test_load_from_s3_not_exists(self):
        """Test loading when file doesn't exist in S3."""
        # Mock NoSuchKey exception
        self.mock_s3.exceptions.NoSuchKey = ClientError
        self.mock_s3.get_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey'}}, 'GetObject'
        )
        
        data = self.storage._load_from_s3()
        
        self.assertIn('repositories', data)
        self.assertEqual(data['repositories'], {})
        self.assertIn('metadata', data)
    
    def test_save_to_s3(self):
        """Test saving data to S3."""
        test_data = {
            'repositories': {'test/repo': {'current_version': 'v1.0.0'}},
            'metadata': {}
        }
        
        self.mock_s3.put_object.return_value = {'ETag': '"new-etag"'}
        
        success = self.storage._save_to_s3(test_data)
        
        self.assertTrue(success)
        self.mock_s3.put_object.assert_called_once()
        
        # Check the call arguments
        call_args = self.mock_s3.put_object.call_args
        self.assertEqual(call_args.kwargs['Bucket'], self.bucket)
        self.assertEqual(call_args.kwargs['Key'], self.storage.versions_key)
        self.assertEqual(call_args.kwargs['ContentType'], 'application/json')
    
    def test_get_current_version(self):
        """Test getting current version for a repository."""
        test_data = {
            'repositories': {
                'owner/repo': {
                    'current_version': 'v2.0.0'
                }
            }
        }
        
        with patch.object(self.storage, '_load_from_s3', return_value=test_data):
            version = self.storage.get_current_version('owner', 'repo')
            self.assertEqual(version, 'v2.0.0')
            
            # Test non-existent repo
            version = self.storage.get_current_version('other', 'repo')
            self.assertIsNone(version)
    
    def test_update_version(self):
        """Test updating version for a repository."""
        initial_data = {
            'repositories': {},
            'metadata': {}
        }
        
        with patch.object(self.storage, '_load_from_s3', return_value=initial_data):
            with patch.object(self.storage, '_save_to_s3', return_value=True) as mock_save:
                success = self.storage.update_version('owner', 'repo', 'v1.0.0', {'asset': 'test.tar.gz'})
                
                self.assertTrue(success)
                
                # Check saved data
                saved_data = mock_save.call_args[0][0]
                self.assertEqual(saved_data['repositories']['owner/repo']['current_version'], 'v1.0.0')
                self.assertIn('version_history', saved_data['repositories']['owner/repo'])
                self.assertEqual(len(saved_data['repositories']['owner/repo']['version_history']), 1)
    
    def test_get_download_history(self):
        """Test getting download history."""
        test_data = {
            'repositories': {
                'owner/repo': {
                    'version_history': [
                        {'version': 'v1.0.0', 'updated_at': '2024-01-01T00:00:00Z'},
                        {'version': 'v1.1.0', 'updated_at': '2024-01-02T00:00:00Z'},
                        {'version': 'v1.2.0', 'updated_at': '2024-01-03T00:00:00Z'}
                    ]
                }
            }
        }
        
        with patch.object(self.storage, '_load_from_s3', return_value=test_data):
            history = self.storage.get_download_history('owner', 'repo', limit=2)
            
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0]['version'], 'v1.2.0')  # Most recent first
            self.assertEqual(history[1]['version'], 'v1.1.0')
    
    def test_add_download_record(self):
        """Test adding download record."""
        initial_data = {
            'repositories': {
                'owner/repo': {}
            },
            'metadata': {}
        }
        
        with patch.object(self.storage, '_load_from_s3', return_value=initial_data):
            with patch.object(self.storage, '_save_to_s3', return_value=True) as mock_save:
                success = self.storage.add_download_record(
                    'owner', 'repo', 'v1.0.0',
                    ['file1.tar.gz', 'file2.zip'],
                    {'checksum': 'abc123'}
                )
                
                self.assertTrue(success)
                
                # Check saved data
                saved_data = mock_save.call_args[0][0]
                repo_data = saved_data['repositories']['owner/repo']
                
                self.assertIn('download_history', repo_data)
                self.assertEqual(len(repo_data['download_history']), 1)
                self.assertEqual(repo_data['download_history'][0]['version'], 'v1.0.0')
                self.assertEqual(repo_data['download_history'][0]['assets'], ['file1.tar.gz', 'file2.zip'])
                
                self.assertIn('statistics', repo_data)
                self.assertEqual(repo_data['statistics']['total_downloads'], 1)
                self.assertEqual(repo_data['statistics']['total_assets_downloaded'], 2)
    
    def test_cache_behavior(self):
        """Test caching behavior."""
        test_data = {'repositories': {}}
        
        # First call should hit S3
        self.mock_s3.get_object.return_value = {
            'Body': Mock(read=Mock(return_value=json.dumps(test_data).encode('utf-8'))),
            'ETag': '"etag1"'
        }
        
        data1 = self.storage._load_from_s3()
        self.assertEqual(self.mock_s3.get_object.call_count, 1)
        
        # Second call with same ETag should use cache
        data2 = self.storage._load_from_s3()
        self.assertEqual(self.mock_s3.get_object.call_count, 2)  # Still called to check ETag
        
        # Clear cache
        self.storage.clear_cache()
        
        # Next call should hit S3 again
        data3 = self.storage._load_from_s3()
        self.assertEqual(self.mock_s3.get_object.call_count, 3)
    
    def test_test_connection(self):
        """Test connection testing."""
        # Success case
        self.mock_s3.head_bucket.return_value = {}
        self.mock_s3.head_object.return_value = {}
        
        self.assertTrue(self.storage.test_connection())
        
        # Bucket not found
        self.mock_s3.head_bucket.side_effect = ClientError(
            {'Error': {'Code': '404'}}, 'HeadBucket'
        )
        
        self.assertFalse(self.storage.test_connection())
    
    def test_export_import(self):
        """Test export and import functionality."""
        test_data = {
            'repositories': {
                'test/repo': {'current_version': 'v1.0.0'}
            },
            'metadata': {}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_file = f.name
        
        try:
            # Test export
            with patch.object(self.storage, '_load_from_s3', return_value=test_data):
                success = self.storage.export_to_file(temp_file)
                self.assertTrue(success)
            
            # Verify exported data
            with open(temp_file, 'r') as f:
                exported_data = json.load(f)
            self.assertEqual(exported_data['repositories']['test/repo']['current_version'], 'v1.0.0')
            
            # Test import
            with patch.object(self.storage, '_save_to_s3', return_value=True) as mock_save:
                success = self.storage.import_from_file(temp_file, merge=False)
                self.assertTrue(success)
                
                # Check imported data was saved
                saved_data = mock_save.call_args[0][0]
                self.assertEqual(saved_data['repositories']['test/repo']['current_version'], 'v1.0.0')
                
        finally:
            os.unlink(temp_file)


class TestVersionDatabaseWrapper(unittest.TestCase):
    """Test the compatibility wrapper."""
    
    def test_s3_mode(self):
        """Test wrapper in S3 mode."""
        with patch.dict(os.environ, {'VERSION_DB_S3_BUCKET': 'test-bucket'}):
            db = VersionDatabase(use_s3=True)
            self.assertTrue(db.use_s3)
            self.assertEqual(db.db_path, 's3://test-bucket/release-monitor/version_db.json')
    
    def test_local_mode(self):
        """Test wrapper in local mode."""
        with patch('github_version_s3.VersionDatabase.__getattribute__', wraps=VersionDatabase.__getattribute__) as mock_getattr:
            db = VersionDatabase(use_s3=False, db_path='test.json')
            # Directly access the attribute without delegation
            self.assertFalse(object.__getattribute__(db, 'use_s3'))
            self.assertEqual(object.__getattribute__(db, 'db_path'), 'test.json')
    
    def test_s3_mode_missing_bucket(self):
        """Test error when S3 bucket not specified."""
        with self.assertRaises(ValueError):
            VersionDatabase(use_s3=True)


if __name__ == '__main__':
    unittest.main()