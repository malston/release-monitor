#!/usr/bin/env python3
"""
Unit tests for Artifactory-based Version Storage
"""

import unittest
import os
import sys
from pathlib import Path
from unittest.mock import patch, Mock
import requests

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from github_version_artifactory import ArtifactoryVersionStorage


class TestArtifactoryVersionStorage(unittest.TestCase):

    def setUp(self):
        """Set up test environment."""
        self.base_url = 'https://artifactory.example.com/artifactory'
        self.repository = 'test-repo'
        self.path_prefix = 'test-prefix/'
        self.api_key = 'test-api-key'

        # Mock requests to avoid actual HTTP calls
        with patch.dict(os.environ, {'ARTIFACTORY_API_KEY': self.api_key}):
            self.storage = ArtifactoryVersionStorage(
                base_url=self.base_url,
                repository=self.repository,
                path_prefix=self.path_prefix
            )

    def test_initialization(self):
        """Test storage initialization."""
        self.assertEqual(self.storage.base_url, self.base_url)
        self.assertEqual(self.storage.repository, self.repository)
        self.assertEqual(self.storage.path_prefix, self.path_prefix)
        self.assertEqual(self.storage.versions_path, f"{self.path_prefix}version_db.json")
        self.assertIn('Authorization', self.storage.headers)

    def test_initialization_with_username_password(self):
        """Test initialization with username/password."""
        username = 'test-user'
        password = 'test-pass'

        storage = ArtifactoryVersionStorage(
            base_url=self.base_url,
            repository=self.repository,
            username=username,
            password=password
        )

        self.assertIsNotNone(storage.auth)
        self.assertEqual(storage.auth.username, username)
        self.assertEqual(storage.auth.password, password)

    def test_initialization_with_env_vars(self):
        """Test initialization using environment variables."""
        env_vars = {
            'ARTIFACTORY_URL': 'https://env.artifactory.com/artifactory',
            'ARTIFACTORY_REPOSITORY': 'env-repo',
            'ARTIFACTORY_API_KEY': 'env-api-key'
        }

        with patch.dict(os.environ, env_vars):
            storage = ArtifactoryVersionStorage(
                base_url=env_vars['ARTIFACTORY_URL'],
                repository=env_vars['ARTIFACTORY_REPOSITORY']
            )

            self.assertEqual(storage.headers['Authorization'], 'Bearer env-api-key')

    def test_initialization_no_credentials(self):
        """Test initialization failure when no credentials provided."""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as context:
                ArtifactoryVersionStorage(
                    base_url=self.base_url,
                    repository=self.repository
                )
            self.assertIn('No Artifactory credentials', str(context.exception))

    def test_get_artifact_url(self):
        """Test URL building for artifacts."""
        path = 'test-path/file.json'
        expected_url = f"{self.base_url}/{self.repository}/{path}"

        url = self.storage._get_artifact_url(path)
        self.assertEqual(url, expected_url)

    @patch('requests.get')
    def test_load_from_artifactory_existing(self, mock_get):
        """Test loading existing data from Artifactory."""
        test_data = {
            'repositories': {
                'test/repo': {
                    'current_version': 'v1.0.0',
                    'last_updated': '2024-01-01T00:00:00Z'
                }
            },
            'metadata': {
                'version': '2.0',
                'storage': 'artifactory'
            }
        }

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = test_data
        mock_response.headers = {'ETag': 'test-etag'}
        mock_get.return_value = mock_response

        data = self.storage._load_from_artifactory()

        self.assertEqual(data['repositories']['test/repo']['current_version'], 'v1.0.0')
        self.assertEqual(data['metadata']['storage'], 'artifactory')
        mock_get.assert_called_once()

    @patch('requests.get')
    def test_load_from_artifactory_not_found(self, mock_get):
        """Test loading when file doesn't exist in Artifactory."""
        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        data = self.storage._load_from_artifactory()

        self.assertIn('repositories', data)
        self.assertEqual(data['repositories'], {})
        self.assertIn('metadata', data)
        self.assertEqual(data['metadata']['storage'], 'artifactory')

    @patch('requests.get')
    def test_load_from_artifactory_cached(self, mock_get):
        """Test using cached data when ETag matches."""
        cached_data = {'repositories': {}, 'metadata': {'version': '2.0'}}
        self.storage._cache = cached_data
        self.storage._cache_etag = 'cached-etag'

        # Mock 304 Not Modified response
        mock_response = Mock()
        mock_response.status_code = 304
        mock_get.return_value = mock_response

        data = self.storage._load_from_artifactory()

        self.assertEqual(data, cached_data)
        mock_get.assert_called_once()

    @patch('requests.get')
    def test_load_from_artifactory_error(self, mock_get):
        """Test error handling during load."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        with self.assertRaises(requests.exceptions.ConnectionError):
            self.storage._load_from_artifactory()

    @patch('requests.put')
    def test_save_to_artifactory(self, mock_put):
        """Test saving data to Artifactory."""
        test_data = {
            'repositories': {'test/repo': {'current_version': 'v1.0.0'}},
            'metadata': {}
        }

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.headers = {'ETag': 'new-etag'}
        mock_put.return_value = mock_response
        mock_response.raise_for_status = Mock()

        success = self.storage._save_to_artifactory(test_data)

        self.assertTrue(success)
        mock_put.assert_called_once()

        # Check the call arguments
        call_args = mock_put.call_args
        self.assertIn(f"{self.base_url}/{self.repository}", call_args[0][0])

        # Check that metadata was added
        self.assertEqual(test_data['metadata']['version'], '2.0')
        self.assertEqual(test_data['metadata']['storage'], 'artifactory')
        self.assertIn('last_updated', test_data['metadata'])

    @patch('requests.put')
    def test_save_to_artifactory_error(self, mock_put):
        """Test error handling during save."""
        mock_put.side_effect = requests.exceptions.ConnectionError("Connection failed")

        test_data = {'repositories': {}, 'metadata': {}}

        with self.assertRaises(requests.exceptions.ConnectionError):
            self.storage._save_to_artifactory(test_data)

    @patch.object(ArtifactoryVersionStorage, '_load_from_artifactory')
    def test_get_current_version_exists(self, mock_load):
        """Test getting current version for existing repository."""
        mock_load.return_value = {
            'repositories': {
                'test/repo': {'current_version': 'v1.2.3'}
            }
        }

        version = self.storage.get_current_version('test', 'repo')
        self.assertEqual(version, 'v1.2.3')

    @patch.object(ArtifactoryVersionStorage, '_load_from_artifactory')
    def test_get_current_version_not_exists(self, mock_load):
        """Test getting current version for non-existent repository."""
        mock_load.return_value = {'repositories': {}}

        version = self.storage.get_current_version('test', 'repo')
        self.assertIsNone(version)

    @patch.object(ArtifactoryVersionStorage, '_load_from_artifactory')
    @patch.object(ArtifactoryVersionStorage, '_save_to_artifactory')
    def test_update_version(self, mock_save, mock_load):
        """Test updating version for a repository."""
        mock_load.return_value = {'repositories': {}, 'metadata': {}}
        mock_save.return_value = True

        metadata = {'release_id': 12345, 'assets': ['file.tar.gz']}
        success = self.storage.update_version('test', 'repo', 'v2.0.0', metadata)

        self.assertTrue(success)
        mock_save.assert_called_once()

        # Check the data passed to save
        saved_data = mock_save.call_args[0][0]
        repo_data = saved_data['repositories']['test/repo']
        self.assertEqual(repo_data['current_version'], 'v2.0.0')
        self.assertIn('download_history', repo_data)
        self.assertEqual(len(repo_data['download_history']), 1)

        history_entry = repo_data['download_history'][0]
        self.assertEqual(history_entry['version'], 'v2.0.0')
        self.assertEqual(history_entry['metadata'], metadata)
        self.assertIn('downloaded_at', history_entry)

    @patch.object(ArtifactoryVersionStorage, '_load_from_artifactory')
    @patch.object(ArtifactoryVersionStorage, '_save_to_artifactory')
    def test_update_version_existing_repo(self, mock_save, mock_load):
        """Test updating version for existing repository."""
        existing_data = {
            'repositories': {
                'test/repo': {
                    'current_version': 'v1.0.0',
                    'download_history': [
                        {'version': 'v1.0.0', 'downloaded_at': '2024-01-01T00:00:00Z'}
                    ]
                }
            },
            'metadata': {}
        }
        mock_load.return_value = existing_data
        mock_save.return_value = True

        success = self.storage.update_version('test', 'repo', 'v2.0.0')

        self.assertTrue(success)

        # Check that history was updated
        saved_data = mock_save.call_args[0][0]
        repo_data = saved_data['repositories']['test/repo']
        self.assertEqual(repo_data['current_version'], 'v2.0.0')
        self.assertEqual(len(repo_data['download_history']), 2)

    @patch.object(ArtifactoryVersionStorage, '_load_from_artifactory')
    def test_get_download_history(self, mock_load):
        """Test getting download history."""
        history_data = [
            {'version': 'v1.0.0', 'downloaded_at': '2024-01-01T00:00:00Z'},
            {'version': 'v1.1.0', 'downloaded_at': '2024-01-02T00:00:00Z'},
            {'version': 'v2.0.0', 'downloaded_at': '2024-01-03T00:00:00Z'}
        ]

        mock_load.return_value = {
            'repositories': {
                'test/repo': {'download_history': history_data}
            }
        }

        history = self.storage.get_download_history('test', 'repo', limit=2)

        # Should return most recent first
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]['version'], 'v2.0.0')
        self.assertEqual(history[1]['version'], 'v1.1.0')

    @patch.object(ArtifactoryVersionStorage, '_load_from_artifactory')
    def test_get_download_history_empty(self, mock_load):
        """Test getting download history for repository with no history."""
        mock_load.return_value = {'repositories': {}}

        history = self.storage.get_download_history('test', 'repo')
        self.assertEqual(history, [])

    @patch.object(ArtifactoryVersionStorage, '_load_from_artifactory')
    def test_load_versions(self, mock_load):
        """Test loading complete version database."""
        test_data = {'repositories': {}, 'metadata': {'version': '2.0'}}
        mock_load.return_value = test_data

        data = self.storage.load_versions()
        self.assertEqual(data, test_data)

    @patch.object(ArtifactoryVersionStorage, '_save_to_artifactory')
    def test_save_versions(self, mock_save):
        """Test saving complete version database."""
        test_data = {'repositories': {}, 'metadata': {'version': '2.0'}}
        mock_save.return_value = True

        success = self.storage.save_versions(test_data)
        self.assertTrue(success)
        mock_save.assert_called_once_with(test_data)

    def test_ssl_verification_disabled(self):
        """Test SSL verification can be disabled."""
        with patch.dict(os.environ, {'ARTIFACTORY_API_KEY': 'test-key'}):
            storage = ArtifactoryVersionStorage(
                base_url=self.base_url,
                repository=self.repository,
                verify_ssl=False
            )
            self.assertFalse(storage.verify_ssl)

    def test_history_limit_enforcement(self):
        """Test that download history is limited to 100 entries."""
        # Create data with over 100 history entries
        history_data = [
            {'version': f'v{i}.0.0', 'downloaded_at': '2024-01-01T00:00:00Z'}
            for i in range(110)
        ]

        existing_data = {
            'repositories': {
                'test/repo': {'download_history': history_data}
            },
            'metadata': {}
        }

        with patch.object(self.storage, '_load_from_artifactory', return_value=existing_data):
            with patch.object(self.storage, '_save_to_artifactory', return_value=True) as mock_save:
                self.storage.update_version('test', 'repo', 'v111.0.0')

                # Check that history was trimmed to 100 entries
                saved_data = mock_save.call_args[0][0]
                repo_data = saved_data['repositories']['test/repo']
                self.assertEqual(len(repo_data['download_history']), 100)




if __name__ == '__main__':
    unittest.main()
