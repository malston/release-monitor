#!/usr/bin/env python3
"""
Integration tests for main loop error handling with subprocess execution.
These tests require actual script execution and should not be run with unit tests.
"""

import os
import sys
import unittest
import subprocess
from unittest.mock import Mock, patch, MagicMock
import requests
import tempfile
import yaml
import json

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestMainLoopErrorHandling(unittest.TestCase):
    """Integration tests for the main loop error handling behavior with RequestException"""

    def setUp(self):
        """Set up test environment"""
        # Create a temporary config file
        self.config = {
            "repositories": [
                {"owner": "test-owner-1", "repo": "test-repo-1"},
                {"owner": "test-owner-2", "repo": "test-repo-2"}
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.config, f)
            self.config_file = f.name

    def tearDown(self):
        """Clean up test environment"""
        if hasattr(self, 'config_file') and os.path.exists(self.config_file):
            os.unlink(self.config_file)

    def test_exits_on_request_exception_by_default(self):
        """Test that script exits with code 1 on RequestException by default"""
        # Set up environment
        env = os.environ.copy()
        env['GITHUB_TOKEN'] = 'test-token'
        env.pop('CONTINUE_ON_API_ERROR', None)  # Make sure it's not set
        
        # Create test script with mocked request exception
        script_content = f'''
import sys
import os
sys.path.insert(0, "{os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))}") 
from unittest.mock import patch
import requests.exceptions
import github_monitor

# Mock get_latest_release to raise RequestException on first repo
original_get_latest_release = github_monitor.GitHubMonitor.get_latest_release

def mock_get_latest_release(self, owner, repo):
    if owner == "test-owner-1":
        raise requests.exceptions.RequestException("Connection failed")
    return {{
        "tag_name": "v1.0.0", 
        "name": "Release v1.0.0", 
        "published_at": "2023-01-01T00:00:00Z",
        "tarball_url": "https://api.github.com/repos/test-owner-2/test-repo-2/tarball/v1.0.0",
        "zipball_url": "https://api.github.com/repos/test-owner-2/test-repo-2/zipball/v1.0.0",
        "html_url": "https://github.com/test-owner-2/test-repo-2/releases/tag/v1.0.0",
        "prerelease": False,
        "draft": False,
        "assets": []
    }}

with patch.object(github_monitor.GitHubMonitor, 'get_latest_release', mock_get_latest_release):
    import sys
    old_argv = sys.argv
    sys.argv = [
        "github_monitor.py",
        "--config", "{self.config_file}",
        "--force-check"
    ]
    try:
        github_monitor.main()
    finally:
        sys.argv = old_argv
'''
        
        result = subprocess.run(
            [sys.executable, '-c', script_content],
            capture_output=True,
            text=True,
            env=env
        )
        
        # Should exit with error code 1
        self.assertEqual(result.returncode, 1)

    def test_continues_with_continue_on_api_error(self):
        """Test that script continues when CONTINUE_ON_API_ERROR=true"""
        # Set up environment with CONTINUE_ON_API_ERROR
        env = os.environ.copy()
        env['GITHUB_TOKEN'] = 'test-token'
        env['CONTINUE_ON_API_ERROR'] = 'true'
        
        # Create test script with mocked request exception
        script_content = f'''
import sys
import os
sys.path.insert(0, "{os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))}") 
from unittest.mock import patch
import requests.exceptions
import github_monitor

# Mock get_latest_release to raise RequestException on first repo only
def mock_get_latest_release(self, owner, repo):
    if owner == "test-owner-1":
        raise requests.exceptions.RequestException("Connection failed")
    return {{
        "tag_name": "v1.0.0", 
        "name": "Release v1.0.0", 
        "published_at": "2023-01-01T00:00:00Z",
        "tarball_url": "https://api.github.com/repos/test-owner-2/test-repo-2/tarball/v1.0.0",
        "zipball_url": "https://api.github.com/repos/test-owner-2/test-repo-2/zipball/v1.0.0",
        "html_url": "https://github.com/test-owner-2/test-repo-2/releases/tag/v1.0.0",
        "prerelease": False,
        "draft": False,
        "assets": []
    }}

with patch.object(github_monitor.GitHubMonitor, 'get_latest_release', mock_get_latest_release):
    import sys
    old_argv = sys.argv
    sys.argv = [
        "github_monitor.py",
        "--config", "{self.config_file}",
        "--force-check",
        "--format", "json"
    ]
    try:
        github_monitor.main()
    finally:
        sys.argv = old_argv
'''
        
        result = subprocess.run(
            [sys.executable, '-c', script_content],
            capture_output=True,
            text=True,
            env=env
        )
        
        # Should complete successfully (exit code 0)
        self.assertEqual(result.returncode, 0)
        
        # Should have processed both repositories (continuing after error)
        if result.stdout:
            try:
                output = json.loads(result.stdout)
                self.assertEqual(output['total_repositories_checked'], 2)
            except json.JSONDecodeError:
                # Output might not be JSON if there were issues
                pass

    def test_error_message_content(self):
        """Test that appropriate error messages are logged"""
        # Set up environment without CONTINUE_ON_API_ERROR
        env = os.environ.copy()
        env['GITHUB_TOKEN'] = 'test-token'
        env.pop('CONTINUE_ON_API_ERROR', None)
        
        script_content = f'''
import sys
import os
sys.path.insert(0, "{os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))}") 
from unittest.mock import patch
import requests.exceptions
import github_monitor

def mock_get_latest_release(self, owner, repo):
    raise requests.exceptions.RequestException("Connection failed")

with patch.object(github_monitor.GitHubMonitor, 'get_latest_release', mock_get_latest_release):
    import sys
    old_argv = sys.argv
    sys.argv = [
        "github_monitor.py",
        "--config", "{self.config_file}",
        "--force-check"
    ]
    try:
        github_monitor.main()
    finally:
        sys.argv = old_argv
'''
        
        result = subprocess.run(
            [sys.executable, '-c', script_content],
            capture_output=True,
            text=True,
            env=env
        )
        
        # Should contain appropriate error messages
        self.assertIn('Exiting due to API error', result.stderr)


if __name__ == '__main__':
    unittest.main()