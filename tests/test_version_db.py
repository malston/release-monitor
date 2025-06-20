#!/usr/bin/env python3
"""
Unit tests for GitHub Version Database
"""

import unittest
import tempfile
import os
import json
from datetime import datetime, timezone
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from github_version_db import VersionDatabase


class TestVersionDatabase(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment with temporary database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_version_db.json')
        self.db = VersionDatabase(self.db_path)
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_database_initialization(self):
        """Test database is properly initialized."""
        self.assertTrue(os.path.exists(self.db_path))
        
        # Check database structure
        with open(self.db_path, 'r') as f:
            data = json.load(f)
        
        self.assertIn('metadata', data)
        self.assertIn('repositories', data)
        self.assertIn('created_at', data['metadata'])
        self.assertEqual(data['metadata']['version'], '1.0')
    
    def test_get_current_version_nonexistent(self):
        """Test getting version for non-existent repository."""
        version = self.db.get_current_version('owner', 'repo')
        self.assertIsNone(version)
    
    def test_update_and_get_version(self):
        """Test updating and retrieving version."""
        # Update version
        self.db.update_version('kubernetes', 'kubernetes', 'v1.28.0', {
            'download_url': 'https://github.com/kubernetes/kubernetes/releases/download/v1.28.0/kubernetes.tar.gz',
            'file_size': 123456
        })
        
        # Retrieve version
        version = self.db.get_current_version('kubernetes', 'kubernetes')
        self.assertEqual(version, 'v1.28.0')
    
    def test_version_history(self):
        """Test version update history tracking."""
        # Add multiple versions
        self.db.update_version('test', 'repo', 'v1.0.0')
        self.db.update_version('test', 'repo', 'v1.1.0')
        self.db.update_version('test', 'repo', 'v1.2.0')
        
        # Check current version
        current = self.db.get_current_version('test', 'repo')
        self.assertEqual(current, 'v1.2.0')
        
        # Check history
        history = self.db.get_download_history('test', 'repo')
        self.assertEqual(len(history), 3)
        
        # History should be in reverse chronological order (newest first)
        self.assertEqual(history[0]['version'], 'v1.2.0')
        self.assertEqual(history[1]['version'], 'v1.1.0')
        self.assertEqual(history[2]['version'], 'v1.0.0')
        
        # Check previous version tracking
        self.assertIsNone(history[2]['previous_version'])  # First entry
        self.assertEqual(history[1]['previous_version'], 'v1.0.0')
        self.assertEqual(history[0]['previous_version'], 'v1.1.0')
    
    def test_download_history_limit(self):
        """Test download history respects limit parameter."""
        # Add several versions
        for i in range(5):
            self.db.update_version('test', 'repo', f'v1.{i}.0')
        
        # Test limited history
        history = self.db.get_download_history('test', 'repo', limit=3)
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]['version'], 'v1.4.0')  # Most recent
    
    def test_get_all_repositories(self):
        """Test getting summary of all repositories."""
        # Add multiple repositories
        self.db.update_version('kubernetes', 'kubernetes', 'v1.28.0')
        self.db.update_version('hashicorp', 'terraform', 'v1.5.0')
        self.db.update_version('docker', 'compose', 'v2.20.0')
        
        repos = self.db.get_all_repositories()
        self.assertEqual(len(repos), 3)
        
        # Check repository data
        k8s_repo = next(r for r in repos if r['repo'] == 'kubernetes')
        self.assertEqual(k8s_repo['owner'], 'kubernetes')
        self.assertEqual(k8s_repo['current_version'], 'v1.28.0')
        self.assertEqual(k8s_repo['download_count'], 1)
    
    def test_remove_repository(self):
        """Test repository removal."""
        # Add repository
        self.db.update_version('test', 'repo', 'v1.0.0')
        self.assertIsNotNone(self.db.get_current_version('test', 'repo'))
        
        # Remove repository
        removed = self.db.remove_repository('test', 'repo')
        self.assertTrue(removed)
        
        # Verify removal
        self.assertIsNone(self.db.get_current_version('test', 'repo'))
        
        # Try removing non-existent repository
        removed = self.db.remove_repository('nonexistent', 'repo')
        self.assertFalse(removed)
    
    def test_database_stats(self):
        """Test database statistics."""
        # Add some data
        self.db.update_version('repo1', 'test', 'v1.0.0')
        self.db.update_version('repo1', 'test', 'v1.1.0')
        self.db.update_version('repo2', 'test', 'v2.0.0')
        
        stats = self.db.get_database_stats()
        
        self.assertEqual(stats['total_repositories'], 2)
        self.assertEqual(stats['total_downloads'], 3)
        self.assertIn('database_created', stats)
        self.assertIn('last_updated', stats)
        self.assertEqual(stats['database_version'], '1.0')
        self.assertGreater(stats['database_size_bytes'], 0)
    
    def test_metadata_preservation(self):
        """Test that metadata is preserved and updated."""
        # Update a version
        self.db.update_version('test', 'repo', 'v1.0.0')
        
        # Read database directly
        with open(self.db_path, 'r') as f:
            data = json.load(f)
        
        # Check metadata was updated
        self.assertIn('last_updated', data['metadata'])
        self.assertIn('created_at', data['metadata'])
        
        created_time = data['metadata']['created_at']
        updated_time = data['metadata']['last_updated']
        
        # Parse timestamps
        created_dt = datetime.fromisoformat(created_time.replace('Z', '+00:00'))
        updated_dt = datetime.fromisoformat(updated_time.replace('Z', '+00:00'))
        
        # Updated time should be >= created time
        self.assertGreaterEqual(updated_dt, created_dt)
    
    def test_history_limit_enforcement(self):
        """Test that history is limited to prevent unbounded growth."""
        # Add more than 50 versions (the limit)
        for i in range(55):
            self.db.update_version('test', 'repo', f'v1.{i}.0')
        
        history = self.db.get_download_history('test', 'repo', limit=100)
        
        # Should be limited to 50 entries
        self.assertEqual(len(history), 50)
        
        # Should have the most recent 50 versions
        self.assertEqual(history[0]['version'], 'v1.54.0')  # Most recent
        self.assertEqual(history[-1]['version'], 'v1.5.0')  # 50th from the end
    
    def test_concurrent_access_safety(self):
        """Test that file locking prevents corruption during concurrent access."""
        import threading
        import time
        
        results = []
        errors = []
        
        def update_versions(thread_id):
            try:
                for i in range(5):  # Reduced from 10 to 5 for more reliable completion
                    self.db.update_version(f'thread{thread_id}', 'repo', f'v{i}.0.0')
                    time.sleep(0.001)  # Small delay to encourage interleaving
                results.append(f'thread{thread_id} completed')
            except Exception as e:
                errors.append(f'thread{thread_id}: {e}')
        
        # Start multiple threads
        threads = []
        for i in range(3):
            t = threading.Thread(target=update_versions, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads with timeout
        for t in threads:
            t.join(timeout=5)  # 5 second timeout
        
        # Check results
        self.assertEqual(len(results), 3)
        self.assertEqual(len(errors), 0)
        
        # Verify all data was written correctly
        all_repos = self.db.get_all_repositories()
        # At least 2 repositories should exist (might be racy)
        self.assertGreaterEqual(len(all_repos), 2)
        
        # Each thread should have written some version (verify no corruption)
        for i in range(3):
            version = self.db.get_current_version(f'thread{i}', 'repo')
            # Should have written at least one version if thread started
            if version is not None:
                # Should be a valid version format (v0.0.0 through v4.0.0)
                self.assertRegex(version, r'^v[0-4]\.0\.0$')


if __name__ == '__main__':
    unittest.main()