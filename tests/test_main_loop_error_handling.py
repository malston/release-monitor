#!/usr/bin/env python3
"""
Unit tests specifically for main loop RequestException handling
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
import requests
import tempfile
import yaml
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMainLoopErrorHandling(unittest.TestCase):
    """Test the main loop error handling behavior with RequestException"""

    def setUp(self):
        """Set up test environment"""
        # Create a temporary config file
        self.config = {
            "repositories": [
                {"owner": "test-owner-1", "repo": "test-repo-1"},
                {"owner": "test-owner-2", "repo": "test-repo-2"}
            ]
        }

        self.config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(self.config, self.config_file)
        self.config_file.close()

        # Set up test args
        self.test_args = [
            'github_monitor.py',
            '--config', self.config_file.name,
            '--force-check'
        ]

    def tearDown(self):
        """Clean up"""
        os.unlink(self.config_file.name)

    @patch('sys.argv')
    @patch('os.getenv')
    @patch('github_monitor.GitHubMonitor')
    def test_exits_on_request_exception_by_default(self, mock_monitor_class, mock_getenv, mock_argv):
        """Test that script exits with code 1 on RequestException by default"""
        # Set up mocks
        mock_argv.__getitem__.side_effect = lambda x: self.test_args[x]
        mock_argv.__len__.return_value = len(self.test_args)

        # Mock environment - GITHUB_TOKEN is set, CONTINUE_ON_API_ERROR is not
        def getenv_side_effect(key, default=None):
            if key == 'GITHUB_TOKEN':
                return 'test-token'
            elif key == 'CONTINUE_ON_API_ERROR':
                return default  # Not set
            return default

        mock_getenv.side_effect = getenv_side_effect

        # Create mock monitor instance
        mock_monitor_instance = Mock()
        mock_monitor_class.return_value = mock_monitor_instance

        # Configure get_latest_release to raise RequestException on first call
        mock_monitor_instance.get_latest_release.side_effect = requests.exceptions.RequestException("Connection failed")

        # Import and run main
        from github_monitor import main

        # Should exit with code 1
        with self.assertRaises(SystemExit) as cm:
            main()

        self.assertEqual(cm.exception.code, 1)

    @patch('sys.argv')
    @patch('os.getenv')
    @patch('github_monitor.GitHubMonitor')
    @patch('builtins.print')
    def test_continues_with_continue_on_api_error(self, mock_print, mock_monitor_class, mock_getenv, mock_argv):
        """Test that script continues when CONTINUE_ON_API_ERROR=true"""
        # Set up mocks
        mock_argv.__getitem__.side_effect = lambda x: self.test_args[x]
        mock_argv.__len__.return_value = len(self.test_args)

        # Mock environment - both GITHUB_TOKEN and CONTINUE_ON_API_ERROR are set
        def getenv_side_effect(key, default=None):
            if key == 'GITHUB_TOKEN':
                return 'test-token'
            elif key == 'CONTINUE_ON_API_ERROR':
                return 'true'
            return default

        mock_getenv.side_effect = getenv_side_effect

        # Create mock monitor instance
        mock_monitor_instance = Mock()
        mock_monitor_class.return_value = mock_monitor_instance

        # Configure get_latest_release to:
        # - Raise RequestException on first repo
        # - Return valid data for second repo
        def get_latest_release_side_effect(owner, repo):
            if owner == "test-owner-1":
                raise requests.exceptions.RequestException("Connection failed")
            else:
                return {
                    'tag_name': 'v1.0.0',
                    'name': 'Release 1.0.0',
                    'published_at': '2023-01-01T00:00:00Z',
                    'tarball_url': 'https://example.com/tarball',
                    'zipball_url': 'https://example.com/zipball',
                    'html_url': 'https://example.com/release',
                    'prerelease': False,
                    'draft': False,
                    'assets': []
                }

        mock_monitor_instance.get_latest_release.side_effect = get_latest_release_side_effect

        # Import and run main
        from github_monitor import main

        # Should complete successfully
        try:
            main()
        except SystemExit as e:
            if e.code != 0:
                self.fail(f"main() exited with non-zero code: {e.code}")

        # Verify that the second repository was checked
        self.assertEqual(mock_monitor_instance.get_latest_release.call_count, 2)

        # Verify output was produced
        mock_print.assert_called()

    @patch('sys.argv')
    @patch('os.getenv')
    @patch('github_monitor.GitHubMonitor')
    def test_error_message_content(self, mock_monitor_class, mock_getenv, mock_argv):
        """Test that appropriate error messages are logged"""
        # Set up mocks
        mock_argv.__getitem__.side_effect = lambda x: self.test_args[x]
        mock_argv.__len__.return_value = len(self.test_args)

        # Mock environment
        def getenv_side_effect(key, default=None):
            if key == 'GITHUB_TOKEN':
                return 'test-token'
            return default

        mock_getenv.side_effect = getenv_side_effect

        # Create mock monitor instance
        mock_monitor_instance = Mock()
        mock_monitor_class.return_value = mock_monitor_instance

        # Configure to raise a specific error
        mock_monitor_instance.get_latest_release.side_effect = requests.exceptions.ConnectionError(
            "Failed to establish a new connection: [Errno -2] Name or service not known"
        )

        # Capture logs
        with self.assertLogs('github_monitor', level='ERROR') as cm:
            from github_monitor import main

            with self.assertRaises(SystemExit) as exit_cm:
                main()

        # Check that appropriate error messages were logged
        error_logs = [log for log in cm.output if 'ERROR' in log]
        self.assertTrue(any('Failed to check test-owner-1/test-repo-1' in log for log in error_logs))
        self.assertTrue(any('Exiting due to API error' in log for log in error_logs))
        self.assertTrue(any('CONTINUE_ON_API_ERROR' in log for log in error_logs))


if __name__ == '__main__':
    unittest.main()
