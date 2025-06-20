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



if __name__ == '__main__':
    unittest.main()
