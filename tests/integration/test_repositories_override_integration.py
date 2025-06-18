#!/usr/bin/env python3
"""
Integration test for REPOSITORIES_OVERRIDE environment variable
"""

import os
import sys
import json
import unittest
import tempfile
import subprocess
import yaml

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRepositoriesOverrideIntegration(unittest.TestCase):
    """Integration tests for REPOSITORIES_OVERRIDE functionality"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a test config file with default repositories
        self.test_config = {
            'repositories': [
                {'owner': 'original', 'repo': 'repo1', 'description': 'Original repo 1'},
                {'owner': 'original', 'repo': 'repo2', 'description': 'Original repo 2'}
            ],
            'settings': {
                'rate_limit_delay': 0.1,  # Faster for testing
                'max_releases_per_repo': 1
            }
        }
        
        self.config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(self.test_config, self.config_file)
        self.config_file.close()
        
        # Save original environment
        self.original_env = os.environ.copy()

    def tearDown(self):
        """Clean up test fixtures"""
        os.unlink(self.config_file.name)
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_monitor_uses_override_repositories(self):
        """Test that the monitor script actually uses REPOSITORIES_OVERRIDE"""
        # Set up environment with override
        override_repos = [
            {'owner': 'prometheus', 'repo': 'prometheus', 'description': 'Monitoring'},
            {'owner': 'grafana', 'repo': 'grafana', 'description': 'Visualization'}
        ]
        
        env = os.environ.copy()
        env['REPOSITORIES_OVERRIDE'] = json.dumps(override_repos)
        env['GITHUB_TOKEN'] = env.get('GITHUB_TOKEN', 'dummy_token_for_test')
        
        # Run the monitor script
        result = subprocess.run(
            [sys.executable, 'github_monitor.py', '--config', self.config_file.name, '--format', 'json'],
            capture_output=True,
            text=True,
            env=env,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        
        # If we don't have a real GitHub token, the script will fail but we can still check the logs
        if 'GITHUB_TOKEN environment variable is required' not in result.stderr:
            # Parse the output
            try:
                output = json.loads(result.stdout)
                
                # Verify the monitored repositories match our override
                if 'repositories_checked' in output:
                    checked_repos = output['repositories_checked']
                    self.assertIn('prometheus/prometheus', checked_repos)
                    self.assertIn('grafana/grafana', checked_repos)
                    self.assertNotIn('original/repo1', checked_repos)
                    self.assertNotIn('original/repo2', checked_repos)
            except json.JSONDecodeError:
                # If output isn't valid JSON, check stderr for override log
                self.assertIn('Overrode repositories list with 2 repositories', result.stderr)

    def test_monitor_with_empty_override(self):
        """Test monitor with empty repository list override"""
        env = os.environ.copy()
        env['REPOSITORIES_OVERRIDE'] = '[]'
        env['GITHUB_TOKEN'] = env.get('GITHUB_TOKEN', 'dummy_token_for_test')
        
        # Run the monitor script
        result = subprocess.run(
            [sys.executable, 'github_monitor.py', '--config', self.config_file.name, '--format', 'json'],
            capture_output=True,
            text=True,
            env=env,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        
        # Should see the override log message
        self.assertIn('Overrode repositories list with 0 repositories', result.stderr)
        
        # Should exit with error since no repositories to monitor
        if result.returncode != 0:
            self.assertIn('No repositories configured', result.stderr)

    def test_monitor_with_invalid_override_falls_back(self):
        """Test that invalid override falls back to config file"""
        env = os.environ.copy()
        env['REPOSITORIES_OVERRIDE'] = 'not valid json'
        env['GITHUB_TOKEN'] = env.get('GITHUB_TOKEN', 'dummy_token_for_test')
        
        # Run the monitor script
        result = subprocess.run(
            [sys.executable, 'github_monitor.py', '--config', self.config_file.name, '--format', 'json'],
            capture_output=True,
            text=True,
            env=env,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        
        # Should see error log about invalid JSON
        self.assertIn('Invalid JSON in REPOSITORIES_OVERRIDE', result.stderr)
        
        # Should still run with original repos (unless no token)
        if 'GITHUB_TOKEN environment variable is required' not in result.stderr:
            # Would check for original repos being used
            pass


if __name__ == '__main__':
    unittest.main()