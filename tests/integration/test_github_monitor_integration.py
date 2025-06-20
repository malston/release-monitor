#!/usr/bin/env python3
"""
Integration tests for GitHub Monitor that use subprocess calls and external dependencies.
These tests require actual execution of the main script and should not be run with unit tests.
"""

import os
import sys
import unittest
import subprocess
import tempfile
import json
import yaml
from unittest.mock import patch
import requests

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestRequestExceptionIntegration(unittest.TestCase):
    """Integration tests for RequestException handling"""

    @patch('github_monitor.GitHubMonitor.get_latest_release')
    def test_main_loop_request_exception_handling(self, mock_get_latest_release):
        """Test main loop handling of RequestException with and without CONTINUE_ON_API_ERROR"""

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
sys.argv = ["github_monitor.py", "--config", "%s"]
with patch('github_monitor.GitHubMonitor.get_latest_release',
           side_effect=requests.exceptions.RequestException("Connection failed")):
    import github_monitor
    github_monitor.main()
''' % (os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), config_file)

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

        # Create a test config
        config = {
            "repositories": [
                {"owner": "invalid-owner-12345", "repo": "invalid-repo-12345"},
                {"owner": "python", "repo": "cpython"}  # A real repo
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
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
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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

        # Create a test config with invalid repo
        config = {
            "repositories": [
                {"owner": "invalid-owner-12345", "repo": "invalid-repo-12345"}
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
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
                timeout=30,  # Don't wait forever
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            )

            # Should exit with error
            self.assertNotEqual(result.returncode, 0)

        finally:
            os.unlink(config_file)


if __name__ == '__main__':
    unittest.main()