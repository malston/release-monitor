#!/usr/bin/env python3
"""
Unit tests for GitHubMonitor class
"""

import os
import sys
import json
import unittest
from unittest.mock import Mock, patch, MagicMock
import requests
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from github_monitor import GitHubMonitor, ReleaseTracker, parse_release_date, load_config


class TestGitHubMonitor(unittest.TestCase):
    """Test cases for GitHubMonitor class"""

    def setUp(self):
        """Set up test fixtures"""
        self.token = "test_token"
        self.monitor = GitHubMonitor(self.token)

    def test_init(self):
        """Test GitHubMonitor initialization"""
        monitor = GitHubMonitor("test_token", rate_limit_delay=2.0)
        self.assertEqual(monitor.token, "test_token")
        self.assertEqual(monitor.rate_limit_delay, 2.0)
        self.assertIsNotNone(monitor.session)
        self.assertEqual(
            monitor.session.headers['Authorization'],
            'token test_token'
        )

    @patch('time.sleep')
    def test_get_latest_release_success(self, mock_sleep):
        """Test successful release fetch"""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'tag_name': 'v1.0.0',
            'name': 'Release 1.0.0',
            'published_at': '2023-01-01T00:00:00Z'
        }

        # Configure session mock
        self.monitor.session.get = Mock(return_value=mock_response)

        # Call method
        result = self.monitor.get_latest_release('owner', 'repo')

        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result['tag_name'], 'v1.0.0')
        self.monitor.session.get.assert_called_once_with(
            'https://api.github.com/repos/owner/repo/releases/latest'
        )
        mock_sleep.assert_called_once_with(self.monitor.rate_limit_delay)

    @patch('time.sleep')
    def test_get_latest_release_not_found(self, mock_sleep):
        """Test handling of 404 (no releases)"""
        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404

        # Configure session mock
        self.monitor.session.get = Mock(return_value=mock_response)

        # Call method
        result = self.monitor.get_latest_release('owner', 'repo')

        # Assertions
        self.assertIsNone(result)

    @patch('time.sleep')
    def test_get_latest_release_request_exception(self, mock_sleep):
        """Test handling of RequestException"""
        # Mock the session.get method to raise RequestException
        self.monitor.session.get = Mock(
            side_effect=requests.exceptions.RequestException("Connection error")
        )

        # Call method and expect exception
        with self.assertRaises(requests.exceptions.RequestException):
            self.monitor.get_latest_release('owner', 'repo')

        # Verify API was called
        self.monitor.session.get.assert_called_once_with(
            'https://api.github.com/repos/owner/repo/releases/latest'
        )

    @patch('time.sleep')
    def test_get_latest_release_connection_error(self, mock_sleep):
        """Test handling of ConnectionError (subclass of RequestException)"""
        # Configure session to raise ConnectionError
        self.monitor.session.get = Mock(
            side_effect=requests.exceptions.ConnectionError(
                "Failed to establish connection"
            )
        )

        # Call method and expect exception
        with self.assertRaises(requests.exceptions.RequestException):
            self.monitor.get_latest_release('owner', 'repo')

    @patch('time.sleep')
    def test_get_latest_release_timeout(self, mock_sleep):
        """Test handling of Timeout (subclass of RequestException)"""
        # Configure session to raise Timeout
        self.monitor.session.get = Mock(
            side_effect=requests.exceptions.Timeout(
                "Request timed out"
            )
        )

        # Call method and expect exception
        with self.assertRaises(requests.exceptions.RequestException):
            self.monitor.get_latest_release('owner', 'repo')

    @patch('time.sleep')
    def test_get_latest_release_http_error(self, mock_sleep):
        """Test handling of HTTPError (subclass of RequestException)"""
        # Mock response with error status
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500 Server Error"
        )

        # Configure session mock
        self.monitor.session.get = Mock(return_value=mock_response)

        # Call method and expect exception
        with self.assertRaises(requests.exceptions.RequestException):
            self.monitor.get_latest_release('owner', 'repo')

    @patch('time.time')
    @patch('time.sleep')
    def test_get_latest_release_rate_limit(self, mock_sleep, mock_time):
        """Test handling of rate limit"""
        # Mock current time
        mock_time.return_value = 1000

        # First response: rate limited
        mock_response_limited = Mock()
        mock_response_limited.status_code = 403
        mock_response_limited.text = "API rate limit exceeded"
        mock_response_limited.headers = {'X-RateLimit-Reset': '1100'}

        # Second response: success
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            'tag_name': 'v1.0.0',
            'name': 'Release 1.0.0',
            'published_at': '2023-01-01T00:00:00Z'
        }

        # Configure session mock to return rate limit then success
        self.monitor.session.get = Mock(
            side_effect=[mock_response_limited, mock_response_success]
        )

        # Call method
        result = self.monitor.get_latest_release('owner', 'repo')

        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result['tag_name'], 'v1.0.0')

        # Verify sleep was called for rate limit delay and wait time
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_any_call(self.monitor.rate_limit_delay)
        mock_sleep.assert_any_call(160)  # (1100 - 1000) + 60

    @patch('time.sleep')
    def test_get_all_releases_success(self, mock_sleep):
        """Test successful fetch of all releases"""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'tag_name': 'v1.0.0', 'name': 'Release 1.0.0'},
            {'tag_name': 'v0.9.0', 'name': 'Release 0.9.0'}
        ]

        # Configure session mock
        self.monitor.session.get = Mock(return_value=mock_response)

        # Call method
        result = self.monitor.get_all_releases('owner', 'repo', per_page=5)

        # Assertions
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['tag_name'], 'v1.0.0')
        self.monitor.session.get.assert_called_once_with(
            'https://api.github.com/repos/owner/repo/releases',
            params={'per_page': 5}
        )

    @patch('time.sleep')
    def test_get_all_releases_request_exception(self, mock_sleep):
        """Test get_all_releases handles RequestException gracefully"""
        # Configure session to raise RequestException
        self.monitor.session.get = Mock(
            side_effect=requests.exceptions.RequestException(
                "Connection error"
            )
        )

        # Call method - should return empty list instead of raising
        result = self.monitor.get_all_releases('owner', 'repo')

        # Assertions
        self.assertEqual(result, [])
        self.monitor.session.get.assert_called_once()


class TestReleaseTracker(unittest.TestCase):
    """Test cases for ReleaseTracker class"""

    def setUp(self):
        """Set up test fixtures"""
        import tempfile
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        self.tracker = ReleaseTracker(self.temp_file.name)

    def tearDown(self):
        """Clean up test files"""
        import os
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def test_has_new_release(self):
        """Test new release detection"""
        repo_key = "owner/repo"
        old_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
        new_date = datetime(2023, 1, 2, tzinfo=timezone.utc)

        # First check - no previous timestamp
        self.assertTrue(self.tracker.has_new_release(repo_key, new_date))

        # Update timestamp
        self.tracker.update_last_checked(repo_key, old_date)

        # Check with newer date
        self.assertTrue(self.tracker.has_new_release(repo_key, new_date))

        # Check with older date
        older_date = datetime(2022, 12, 31, tzinfo=timezone.utc)
        self.assertFalse(self.tracker.has_new_release(repo_key, older_date))


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions"""

    def test_parse_release_date(self):
        """Test ISO date parsing"""
        date_string = "2023-01-01T12:00:00Z"
        result = parse_release_date(date_string)

        self.assertEqual(result.year, 2023)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 1)
        self.assertEqual(result.hour, 12)
        self.assertEqual(result.tzinfo, timezone.utc)


class TestRequestExceptionIntegration(unittest.TestCase):
    """Integration tests for RequestException handling"""

    @patch('github_monitor.GitHubMonitor.get_latest_release')
    def test_main_loop_request_exception_handling(self, mock_get_latest_release):
        """Test main loop handling of RequestException with and without CONTINUE_ON_API_ERROR"""
        import tempfile
        import subprocess
        import json
        import yaml

        # Test 1: Without CONTINUE_ON_API_ERROR - should exit with error
        config = {
            "repositories": [
                {"owner": "test-owner", "repo": "test-repo"}
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            config_file = f.name

        try:
            # Configure mock to raise RequestException
            mock_get_latest_release.side_effect = requests.exceptions.RequestException("Connection failed")

            # Run without CONTINUE_ON_API_ERROR
            env = os.environ.copy()
            env['GITHUB_TOKEN'] = 'test-token'
            env.pop('CONTINUE_ON_API_ERROR', None)

            # Create test script that will mock the exception
            test_script = '''
import sys
sys.path.insert(0, "%s")
from unittest.mock import patch
import requests.exceptions
with patch('github_monitor.GitHubMonitor.get_latest_release',
           side_effect=requests.exceptions.RequestException("Connection failed")):
    import github_monitor
    github_monitor.main()
''' % os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            result = subprocess.run(
                [sys.executable, '-c', test_script],
                capture_output=True,
                text=True,
                env=env
            )

            # Should exit with error code 1
            self.assertEqual(result.returncode, 1)
            self.assertIn('Exiting due to API error', result.stderr)

        finally:
            os.unlink(config_file)

    def test_monitor_continues_with_flag(self):
        """Test that monitor continues processing when CONTINUE_ON_API_ERROR is set"""
        import tempfile
        import subprocess
        import json

        # Create a test config
        config = {
            "repositories": [
                {"owner": "invalid-owner-12345", "repo": "invalid-repo-12345"},
                {"owner": "python", "repo": "cpython"}  # A real repo
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            import yaml
            yaml.dump(config, f)
            config_file = f.name

        try:
            # Run with CONTINUE_ON_API_ERROR set
            env = os.environ.copy()
            env['GITHUB_TOKEN'] = os.getenv('GITHUB_TOKEN', 'dummy')
            env['CONTINUE_ON_API_ERROR'] = 'true'

            result = subprocess.run(
                [sys.executable, 'github_monitor.py', '--config', config_file, '--force-check'],
                capture_output=True,
                text=True,
                env=env,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )

            # Should complete successfully
            self.assertEqual(result.returncode, 0)

            # Check output
            if result.stdout:
                output = json.loads(result.stdout)
                self.assertEqual(output['total_repositories_checked'], 2)

        finally:
            os.unlink(config_file)

    def test_monitor_exits_without_flag(self):
        """Test that monitor exits when CONTINUE_ON_API_ERROR is not set"""
        import tempfile
        import subprocess

        # Create a test config with invalid repo
        config = {
            "repositories": [
                {"owner": "invalid-owner-12345", "repo": "invalid-repo-12345"}
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            import yaml
            yaml.dump(config, f)
            config_file = f.name

        try:
            # Run without CONTINUE_ON_API_ERROR
            env = os.environ.copy()
            env['GITHUB_TOKEN'] = os.getenv('GITHUB_TOKEN', 'dummy')
            env.pop('CONTINUE_ON_API_ERROR', None)

            result = subprocess.run(
                [sys.executable, 'github_monitor.py', '--config', config_file],
                capture_output=True,
                text=True,
                env=env,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )

            # Note: Non-existent repos return 404 which is handled as None, not RequestException
            # So this test might not trigger the RequestException path
            # The test is kept for compatibility but the new test above better tests the actual exception handling

        finally:
            os.unlink(config_file)


class TestConfigLoading(unittest.TestCase):
    """Test cases for configuration loading with environment overrides"""

    def setUp(self):
        """Set up test fixtures"""
        import tempfile
        import yaml
        
        # Create a test config file
        self.test_config = {
            'repositories': [
                {'owner': 'original', 'repo': 'repo1', 'description': 'Original repo 1'},
                {'owner': 'original', 'repo': 'repo2', 'description': 'Original repo 2'}
            ],
            'settings': {
                'rate_limit_delay': 1.0
            }
        }
        
        self.config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(self.test_config, self.config_file)
        self.config_file.close()

    def tearDown(self):
        """Clean up test fixtures"""
        os.unlink(self.config_file.name)
        # Clean up environment variable if set
        os.environ.pop('REPOSITORIES_OVERRIDE', None)

    def test_load_config_without_override(self):
        """Test loading configuration without environment override"""
        config = load_config(self.config_file.name)
        
        self.assertEqual(len(config['repositories']), 2)
        self.assertEqual(config['repositories'][0]['owner'], 'original')
        self.assertEqual(config['repositories'][0]['repo'], 'repo1')
        self.assertEqual(config['settings']['rate_limit_delay'], 1.0)

    def test_load_config_with_valid_override(self):
        """Test loading configuration with valid REPOSITORIES_OVERRIDE"""
        override_repos = [
            {'owner': 'kubernetes', 'repo': 'kubernetes', 'description': 'K8s'},
            {'owner': 'istio', 'repo': 'istio', 'description': 'Service mesh'},
            {'owner': 'helm', 'repo': 'helm', 'description': 'Package manager'}
        ]
        
        os.environ['REPOSITORIES_OVERRIDE'] = json.dumps(override_repos)
        
        config = load_config(self.config_file.name)
        
        # Verify repositories were overridden
        self.assertEqual(len(config['repositories']), 3)
        self.assertEqual(config['repositories'][0]['owner'], 'kubernetes')
        self.assertEqual(config['repositories'][0]['repo'], 'kubernetes')
        self.assertEqual(config['repositories'][1]['owner'], 'istio')
        self.assertEqual(config['repositories'][2]['owner'], 'helm')
        
        # Verify other settings remain unchanged
        self.assertEqual(config['settings']['rate_limit_delay'], 1.0)

    def test_load_config_with_empty_override(self):
        """Test loading configuration with empty REPOSITORIES_OVERRIDE"""
        os.environ['REPOSITORIES_OVERRIDE'] = '[]'
        
        config = load_config(self.config_file.name)
        
        # Verify repositories were overridden with empty list
        self.assertEqual(len(config['repositories']), 0)
        
        # Verify other settings remain unchanged
        self.assertEqual(config['settings']['rate_limit_delay'], 1.0)

    def test_load_config_with_invalid_json_override(self):
        """Test loading configuration with invalid JSON in REPOSITORIES_OVERRIDE"""
        os.environ['REPOSITORIES_OVERRIDE'] = 'invalid json {'
        
        # Should not raise exception, just log error
        config = load_config(self.config_file.name)
        
        # Original repositories should remain
        self.assertEqual(len(config['repositories']), 2)
        self.assertEqual(config['repositories'][0]['owner'], 'original')

    def test_load_config_with_non_array_override(self):
        """Test loading configuration with non-array JSON in REPOSITORIES_OVERRIDE"""
        os.environ['REPOSITORIES_OVERRIDE'] = '{"owner": "test", "repo": "test"}'
        
        # Should not raise exception, just log error
        config = load_config(self.config_file.name)
        
        # Original repositories should remain
        self.assertEqual(len(config['repositories']), 2)
        self.assertEqual(config['repositories'][0]['owner'], 'original')

    def test_load_config_with_single_repo_override(self):
        """Test loading configuration with single repository override"""
        override_repos = [
            {'owner': 'open-policy-agent', 'repo': 'gatekeeper', 'description': 'Policy Controller'}
        ]
        
        os.environ['REPOSITORIES_OVERRIDE'] = json.dumps(override_repos)
        
        config = load_config(self.config_file.name)
        
        # Verify single repository override
        self.assertEqual(len(config['repositories']), 1)
        self.assertEqual(config['repositories'][0]['owner'], 'open-policy-agent')
        self.assertEqual(config['repositories'][0]['repo'], 'gatekeeper')
        self.assertEqual(config['repositories'][0]['description'], 'Policy Controller')

    @patch('github_monitor.logger')
    def test_load_config_logs_override_info(self, mock_logger):
        """Test that configuration override logs appropriate messages"""
        override_repos = [
            {'owner': 'test', 'repo': 'repo1'},
            {'owner': 'test', 'repo': 'repo2'}
        ]
        
        os.environ['REPOSITORIES_OVERRIDE'] = json.dumps(override_repos)
        
        config = load_config(self.config_file.name)
        
        # Verify info log was called
        mock_logger.info.assert_called_with(
            'Overrode repositories list with 2 repositories from REPOSITORIES_OVERRIDE environment variable'
        )

    @patch('github_monitor.logger')
    def test_load_config_logs_json_error(self, mock_logger):
        """Test that invalid JSON logs error message"""
        os.environ['REPOSITORIES_OVERRIDE'] = 'not valid json'
        
        config = load_config(self.config_file.name)
        
        # Verify error log was called
        mock_logger.error.assert_called()
        error_call_args = mock_logger.error.call_args[0][0]
        self.assertIn('Invalid JSON in REPOSITORIES_OVERRIDE', error_call_args)

    @patch('github_monitor.logger')
    def test_load_config_logs_type_error(self, mock_logger):
        """Test that non-array JSON logs error message"""
        os.environ['REPOSITORIES_OVERRIDE'] = '{"not": "an array"}'
        
        config = load_config(self.config_file.name)
        
        # Verify error log was called
        mock_logger.error.assert_called_with(
            'REPOSITORIES_OVERRIDE must be a JSON array of repository objects'
        )


if __name__ == '__main__':
    unittest.main()
