#!/usr/bin/env python3
"""
S3/MinIO integration tests.
Tests the S3 version database functionality with a running MinIO instance.
"""

import unittest
import os
import sys
import tempfile
import json
from unittest.mock import patch

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from github_version_s3_mc import S3VersionDatabase, S3VersionStorageMC


class TestS3Integration(unittest.TestCase):
    """Integration tests for S3/MinIO functionality."""
    
    @classmethod
    def setUpClass(cls):
        """Check if MinIO is available."""
        cls.skip_tests = False
        
        # Check environment
        if not os.environ.get('MINIO_TESTS'):
            cls.skip_tests = True
            cls.skip_reason = "MINIO_TESTS not set, skipping S3 integration tests"
            return
        
        # Check if mc command is available
        import subprocess
        try:
            subprocess.run(['mc', '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            cls.skip_tests = True
            cls.skip_reason = "MinIO client (mc) not found"
            return
        
        # Set up test bucket name
        cls.test_bucket = 'test-release-monitor'
        cls.test_prefix = 'integration-test/'
    
    def setUp(self):
        """Set up test environment."""
        if self.skip_tests:
            self.skipTest(self.skip_reason)
        
        # Create unique test prefix
        import uuid
        self.test_id = str(uuid.uuid4())[:8]
        self.unique_prefix = f"{self.test_prefix}{self.test_id}/"
    
    def tearDown(self):
        """Clean up test data."""
        if not self.skip_tests:
            try:
                # Clean up test data using mc
                import subprocess
                subprocess.run([
                    'mc', 'rm', '--recursive', '--force',
                    f"s3versiondb/{self.test_bucket}/{self.unique_prefix}"
                ], capture_output=True)
            except:
                pass
    
    def test_s3_version_database_basic(self):
        """Test basic S3 version database operations."""
        # Create S3 version database
        db = S3VersionDatabase(
            bucket=self.test_bucket,
            key_prefix=self.unique_prefix
        )
        
        # Test initialization
        self.assertIsNotNone(db)
        
        # Test get current version (should be None for new repo)
        version = db.get_current_version('test-owner', 'test-repo')
        self.assertIsNone(version)
        
        # Test update version
        metadata = {
            'download_count': 2,
            'downloaded_files': ['file1.yaml', 'file2.tar.gz']
        }
        db.update_version('test-owner', 'test-repo', 'v1.0.0', metadata)
        
        # Test get current version after update
        version = db.get_current_version('test-owner', 'test-repo')
        self.assertEqual(version, 'v1.0.0')
        
        # Test get version metadata
        stored_metadata = db.get_version_metadata('test-owner', 'test-repo')
        self.assertIsNotNone(stored_metadata)
        self.assertEqual(stored_metadata.get('download_count'), 2)
    
    def test_s3_storage_mc_operations(self):
        """Test S3StorageMC low-level operations."""
        storage = S3VersionStorageMC(
            bucket=self.test_bucket,
            key_prefix=self.unique_prefix
        )
        
        # Test save
        test_data = {
            'test': 'data',
            'version': '1.0.0',
            'items': ['a', 'b', 'c']
        }
        
        success = storage.save_versions(test_data)
        self.assertTrue(success)
        
        # Test load
        loaded_data = storage.load_versions()
        self.assertIsNotNone(loaded_data)
        self.assertEqual(loaded_data.get('test'), 'data')
        self.assertEqual(loaded_data.get('version'), '1.0.0')
        
        # Test exists
        exists = storage.exists()
        self.assertTrue(exists)
    
    def test_concurrent_updates(self):
        """Test concurrent updates to version database."""
        db1 = S3VersionDatabase(
            bucket=self.test_bucket,
            key_prefix=self.unique_prefix
        )
        
        db2 = S3VersionDatabase(
            bucket=self.test_bucket,
            key_prefix=self.unique_prefix
        )
        
        # Both update different repos
        db1.update_version('owner1', 'repo1', 'v1.0.0', {})
        db2.update_version('owner2', 'repo2', 'v2.0.0', {})
        
        # Verify both updates are present
        version1 = db1.get_current_version('owner1', 'repo1')
        version2 = db1.get_current_version('owner2', 'repo2')
        
        self.assertEqual(version1, 'v1.0.0')
        self.assertEqual(version2, 'v2.0.0')
    
    def test_large_metadata(self):
        """Test storing large metadata."""
        db = S3VersionDatabase(
            bucket=self.test_bucket,
            key_prefix=self.unique_prefix
        )
        
        # Create large metadata
        large_metadata = {
            'downloaded_files': [f"file_{i}.tar.gz" for i in range(100)],
            'download_stats': {
                str(i): {
                    'size': i * 1000,
                    'time': i * 0.5,
                    'checksum': f"sha256_{i}" * 8
                } for i in range(50)
            }
        }
        
        # Update with large metadata
        db.update_version('test', 'large-repo', 'v1.0.0', large_metadata)
        
        # Retrieve and verify
        stored = db.get_version_metadata('test', 'large-repo')
        self.assertEqual(len(stored.get('downloaded_files', [])), 100)
        self.assertEqual(len(stored.get('download_stats', {})), 50)


if __name__ == '__main__':
    # Set up environment if running directly
    if not os.environ.get('S3_ENDPOINT'):
        os.environ['S3_ENDPOINT'] = 'http://localhost:9000'
    if not os.environ.get('AWS_ACCESS_KEY_ID'):
        os.environ['AWS_ACCESS_KEY_ID'] = 'minioadmin'
    if not os.environ.get('AWS_SECRET_ACCESS_KEY'):
        os.environ['AWS_SECRET_ACCESS_KEY'] = 'minioadmin'
    
    unittest.main()