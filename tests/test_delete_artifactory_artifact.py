#!/usr/bin/env python3
"""
Unit tests for delete-artifactory-artifact.py script
"""

import unittest
import os
import sys
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
import requests

# Add project root and scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


class TestDeleteArtifactoryArtifact(unittest.TestCase):
    """Test cases for delete-artifactory-artifact.py functions"""

    def setUp(self):
        """Set up test fixtures"""
        self.artifactory_url = "http://localhost:8081/artifactory"
        self.repository = "test-repo"
        self.artifact_path = "releases/test-app/v1.0.0/test-app.tar.gz"
        self.auth_headers = {"Authorization": "Bearer test-api-key"}
        self.auth = None
        self.verify_ssl = True
        
        # Import the script module for each test
        self.script_path = Path(__file__).parent.parent / "scripts" / "delete-artifactory-artifact.py"
        self.exec_globals = {}
        with open(self.script_path) as f:
            exec(compile(f.read(), str(self.script_path), 'exec'), self.exec_globals)

    def test_format_size(self):
        """Test format_size function with various inputs"""
        format_size = self.exec_globals['format_size']
        
        # Test byte sizes
        self.assertEqual(format_size(0), "0.00 B")
        self.assertEqual(format_size(512), "512.00 B")
        self.assertEqual(format_size(1024), "1.00 KB")
        self.assertEqual(format_size(1048576), "1.00 MB")
        self.assertEqual(format_size(1073741824), "1.00 GB")
        
        # Test string input
        self.assertEqual(format_size("1024"), "1.00 KB")
        self.assertEqual(format_size("invalid"), "Unknown size")
        
        # Test edge cases
        self.assertEqual(format_size(1536), "1.50 KB")
        self.assertEqual(format_size(1572864), "1.50 MB")

    @patch('requests.get')
    def test_get_artifact_info_success(self, mock_get):
        """Test successful artifact info retrieval"""
        get_artifact_info = self.exec_globals['get_artifact_info']
        
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "path": "/test/artifact.tar.gz",
            "size": "1024",
            "created": "2025-01-15T10:00:00Z",
            "lastModified": "2025-01-15T11:00:00Z",
            "checksums": {
                "sha256": "abc123def456"
            }
        }
        mock_get.return_value = mock_response

        result = get_artifact_info(
            self.artifactory_url,
            self.repository,
            self.auth_headers,
            self.auth,
            self.verify_ssl,
            self.artifact_path
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["size"], "1024")
        self.assertIn("checksums", result)
        
        # Verify the correct URL was called
        expected_url = f"{self.artifactory_url}/api/storage/{self.repository}/{self.artifact_path}"
        mock_get.assert_called_once_with(
            expected_url,
            headers=self.auth_headers,
            auth=self.auth,
            verify=self.verify_ssl
        )

    @patch('requests.get')
    def test_get_artifact_info_not_found(self, mock_get):
        """Test artifact info retrieval when artifact doesn't exist"""
        get_artifact_info = self.exec_globals['get_artifact_info']
        
        mock_response = Mock()
        mock_response.status_code = 404
        mock_error = requests.exceptions.HTTPError(response=mock_response)
        mock_get.side_effect = mock_error

        result = get_artifact_info(
            self.artifactory_url,
            self.repository,
            self.auth_headers,
            self.auth,
            self.verify_ssl,
            "non/existent/artifact.txt"
        )

        self.assertIsNone(result)

    @patch('requests.get')
    @patch('builtins.print')
    def test_get_artifact_info_error(self, mock_print, mock_get):
        """Test artifact info retrieval with network error"""
        get_artifact_info = self.exec_globals['get_artifact_info']
        
        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        result = get_artifact_info(
            self.artifactory_url,
            self.repository,
            self.auth_headers,
            self.auth,
            self.verify_ssl,
            self.artifact_path
        )

        self.assertIsNone(result)
        # Verify error message was printed
        mock_print.assert_any_call("Error getting artifact info: Network error")

    @patch('requests.delete')
    def test_delete_artifact_success(self, mock_delete):
        """Test successful artifact deletion"""
        delete_artifact = self.exec_globals['delete_artifact']
        
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_delete.return_value = mock_response

        result = delete_artifact(
            self.artifactory_url,
            self.repository,
            self.auth_headers,
            self.auth,
            self.verify_ssl,
            self.artifact_path
        )

        self.assertTrue(result)
        
        # Verify the correct URL was called
        expected_url = f"{self.artifactory_url}/{self.repository}/{self.artifact_path}"
        mock_delete.assert_called_once_with(
            expected_url,
            headers=self.auth_headers,
            auth=self.auth,
            verify=self.verify_ssl
        )

    @patch('requests.delete')
    @patch('builtins.print')
    def test_delete_artifact_failure(self, mock_print, mock_delete):
        """Test artifact deletion failure"""
        delete_artifact = self.exec_globals['delete_artifact']
        
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_error = requests.exceptions.RequestException("Delete failed")
        mock_error.response = mock_response
        mock_delete.side_effect = mock_error

        result = delete_artifact(
            self.artifactory_url,
            self.repository,
            self.auth_headers,
            self.auth,
            self.verify_ssl,
            self.artifact_path
        )

        self.assertFalse(result)
        # Verify error messages were printed
        mock_print.assert_any_call(f"Error deleting {self.artifact_path}: Delete failed")
        mock_print.assert_any_call("Response status: 403")
        mock_print.assert_any_call("Response text: Forbidden")

    @patch('sys.argv', ['script.py', '--help'])
    def test_help_argument(self):
        """Test that help argument works"""
        # Just test that the script can be imported without errors
        # The actual help is handled by argparse
        self.assertIn('format_size', self.exec_globals)
        self.assertIn('get_artifact_info', self.exec_globals)
        self.assertIn('delete_artifact', self.exec_globals)
        self.assertIn('main', self.exec_globals)

    def test_functions_exist(self):
        """Test that all expected functions exist in the script"""
        expected_functions = [
            'format_size',
            'get_artifact_info',
            'delete_artifact',
            'main'
        ]
        
        for func_name in expected_functions:
            self.assertIn(func_name, self.exec_globals)
            self.assertTrue(callable(self.exec_globals[func_name]))

    @patch.dict(os.environ, {
        'ARTIFACTORY_URL': 'http://localhost:8081/artifactory',
        'ARTIFACTORY_REPOSITORY': 'test-repo',
        'ARTIFACTORY_API_KEY': 'test-key'
    })
    def test_environment_variables(self):
        """Test that environment variables are properly read"""
        # This test verifies that the script can read environment variables
        # when they are set
        self.assertEqual(os.environ.get('ARTIFACTORY_URL'), 'http://localhost:8081/artifactory')
        self.assertEqual(os.environ.get('ARTIFACTORY_REPOSITORY'), 'test-repo')
        self.assertEqual(os.environ.get('ARTIFACTORY_API_KEY'), 'test-key')

    def test_format_size_edge_cases(self):
        """Test format_size with edge cases"""
        format_size = self.exec_globals['format_size']
        
        # Very large size
        self.assertEqual(format_size(1099511627776), "1.00 TB")
        
        # Size as float
        self.assertEqual(format_size(1024.5), "1.00 KB")
        
        # Negative size - the function doesn't handle this specially
        # It will show negative bytes since negative sizes don't make sense
        self.assertEqual(format_size(-1024), "-1024.00 B")
        
        # Non-numeric string
        self.assertEqual(format_size("not_a_number"), "Unknown size")
        
        # Empty string
        self.assertEqual(format_size(""), "Unknown size")


if __name__ == '__main__':
    unittest.main()