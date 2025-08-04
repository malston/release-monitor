#!/usr/bin/env python3
"""
Integration tests for Artifactory version storage.

These tests require a running Artifactory instance and proper environment variables.
"""

import unittest
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from github_version_artifactory import ArtifactoryVersionStorage


class TestArtifactoryVersionStorageIntegration(unittest.TestCase):
    """Integration tests that test the full flow without mocking HTTP calls."""

    def setUp(self):
        """Set up test environment for integration tests."""
        # Check if Artifactory integration test environment is configured
        self.artifactory_url = os.environ.get('ARTIFACTORY_URL')
        self.artifactory_repository = os.environ.get('ARTIFACTORY_REPOSITORY')
        self.artifactory_api_key = os.environ.get('ARTIFACTORY_API_KEY')

        # Skip if required environment variables are not set
        if not self.artifactory_url or not self.artifactory_repository:
            self.skipTest("Integration tests require ARTIFACTORY_URL and ARTIFACTORY_REPOSITORY environment variables")

        if not (self.artifactory_api_key or (os.environ.get('ARTIFACTORY_USERNAME') and os.environ.get('ARTIFACTORY_PASSWORD'))):
            self.skipTest("Integration tests require ARTIFACTORY_API_KEY or ARTIFACTORY_USERNAME/ARTIFACTORY_PASSWORD")

        # Try to connect to Artifactory to verify it's available
        try:
            import requests
            # Test basic connectivity
            response = requests.get(f"{self.artifactory_url}/api/system/ping", timeout=5)
            if response.status_code != 200:
                self.skipTest(f"Artifactory not accessible at {self.artifactory_url} (status: {response.status_code})")
        except Exception as e:
            self.skipTest(f"Cannot connect to Artifactory at {self.artifactory_url}: {e}")

        # Set up test storage instance
        self.storage = ArtifactoryVersionStorage(
            base_url=self.artifactory_url,
            repository=self.artifactory_repository,
            path_prefix='test-integration/',
            api_key=self.artifactory_api_key,
            username=os.environ.get('ARTIFACTORY_USERNAME'),
            password=os.environ.get('ARTIFACTORY_PASSWORD')
        )
        self.test_prefix = f"test-{int(time.time())}-"

    def test_full_lifecycle(self):
        """Test complete lifecycle: create, update, retrieve, save."""
        # Test repository data
        test_owner = f"{self.test_prefix}owner"
        test_repo = f"{self.test_prefix}repo"

        # 1. Test that initially no version exists
        initial_version = self.storage.get_current_version(test_owner, test_repo)
        self.assertIsNone(initial_version)

        # 2. Test updating version
        test_metadata = {
            'download_count': 1,
            'total_assets': 2,
            'downloaded_files': ['test.tar.gz'],
            'download_time': 1.5,
            'total_size': 1024
        }
        self.storage.update_version(test_owner, test_repo, 'v1.0.0', test_metadata)

        # 3. Test retrieving version
        current_version = self.storage.get_current_version(test_owner, test_repo)
        self.assertEqual(current_version, 'v1.0.0')

        # 4. Test updating to newer version
        self.storage.update_version(test_owner, test_repo, 'v1.1.0', test_metadata)
        current_version = self.storage.get_current_version(test_owner, test_repo)
        self.assertEqual(current_version, 'v1.1.0')

        # 5. Test download history
        history = self.storage.get_download_history(test_owner, test_repo)
        self.assertGreaterEqual(len(history), 2)
        self.assertEqual(history[0]['version'], 'v1.1.0')  # Most recent first
        self.assertEqual(history[1]['version'], 'v1.0.0')

        # 6. Test database stats
        stats = self.storage.get_database_stats()
        self.assertIn('total_repositories', stats)
        self.assertIn('total_downloads', stats)
        self.assertGreaterEqual(stats['total_repositories'], 1)
        self.assertGreaterEqual(stats['total_downloads'], 2)

        print(f"✓ Integration test passed with Artifactory at {self.artifactory_url}")

    def tearDown(self):
        """Clean up test data from Artifactory."""
        if hasattr(self, 'storage') and hasattr(self, 'test_prefix'):
            try:
                # Clean up test data by clearing the entire test database
                # This is safe because we use a test-specific prefix
                test_data = self.storage.load_versions()
                if 'repositories' in test_data:
                    # Remove any repositories that start with our test prefix
                    repos_to_remove = [repo for repo in test_data['repositories'].keys()
                                     if self.test_prefix in repo]
                    for repo in repos_to_remove:
                        del test_data['repositories'][repo]

                    if repos_to_remove:
                        self.storage.save_versions(test_data)
                        print(f"✓ Cleaned up {len(repos_to_remove)} test repositories")
            except Exception as e:
                print(f"Warning: Could not clean up test data: {e}")


if __name__ == '__main__':
    unittest.main()
