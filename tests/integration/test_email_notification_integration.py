#!/usr/bin/env python3
"""
Integration tests for email notification in the release monitor pipeline
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestEmailNotificationIntegration(unittest.TestCase):
    """Integration tests for email notification functionality"""

    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.release_output_dir = Path(self.test_dir) / 'release-output'
        self.email_output_dir = Path(self.test_dir) / 'email'
        self.release_output_dir.mkdir()

        # Sample releases data matching actual monitor output format
        self.sample_releases = {
            "timestamp": "2023-08-15T14:00:00+00:00",
            "total_repositories_checked": 3,
            "new_releases_found": 2,
            "releases": [
                {
                    "repository": "kubernetes/kubernetes",
                    "owner": "kubernetes",
                    "repo": "kubernetes",
                    "tag_name": "v1.28.0",
                    "name": "Kubernetes v1.28.0",
                    "published_at": "2023-08-15T12:00:00Z",
                    "tarball_url": "https://api.github.com/repos/kubernetes/kubernetes/tarball/v1.28.0",
                    "zipball_url": "https://api.github.com/repos/kubernetes/kubernetes/zipball/v1.28.0",
                    "html_url": "https://github.com/kubernetes/kubernetes/releases/tag/v1.28.0",
                    "prerelease": False,
                    "draft": False,
                    "author": {"login": "k8s-release-robot"},
                    "assets": [
                        {
                            "name": "kubernetes-client-linux-amd64.tar.gz",
                            "size": 50331648,
                            "browser_download_url": "https://github.com/kubernetes/kubernetes/releases/download/v1.28.0/kubernetes-client-linux-amd64.tar.gz"
                        }
                    ]
                },
                {
                    "repository": "prometheus/prometheus",
                    "owner": "prometheus",
                    "repo": "prometheus",
                    "tag_name": "v2.46.0",
                    "name": "2.46.0 / 2023-07-25",
                    "published_at": "2023-07-25T14:00:00Z",
                    "tarball_url": "https://api.github.com/repos/prometheus/prometheus/tarball/v2.46.0",
                    "zipball_url": "https://api.github.com/repos/prometheus/prometheus/zipball/v2.46.0",
                    "html_url": "https://github.com/prometheus/prometheus/releases/tag/v2.46.0",
                    "prerelease": False,
                    "draft": False,
                    "author": {"login": "prombot"},
                    "assets": []
                }
            ]
        }

        # Write test releases file
        with open(self.release_output_dir / 'releases.json', 'w') as f:
            json.dump(self.sample_releases, f)

    def tearDown(self):
        """Clean up test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_email_generation_script(self):
        """Test running the email generation script"""
        script_path = Path(__file__).parent.parent.parent / 'ci' / 'tasks' / 'send-release-notification' / 'generate_email.py'

        # Set up environment with custom paths
        env = os.environ.copy()
        env['EMAIL_SUBJECT_PREFIX'] = '[Test Monitor]'
        env['INCLUDE_ASSET_DETAILS'] = 'true'
        env['RELEASES_INPUT_DIR'] = str(self.release_output_dir)
        env['EMAIL_OUTPUT_DIR'] = str(self.email_output_dir)

        # Add project root to Python path and run script
        project_root = script_path.parent.parent.parent
        script_content = f"""
import sys
sys.path.insert(0, '{project_root}')
{script_path.read_text()}
"""

        result = subprocess.run(
            [sys.executable, '-c', script_content],
            env=env,
            capture_output=True,
            text=True
        )

        # Check script succeeded
        self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")

        # Verify email files were created
        self.assertTrue((self.email_output_dir / 'subject').exists())
        self.assertTrue((self.email_output_dir / 'body').exists())
        self.assertTrue((self.email_output_dir / 'body.html').exists())

        # Check subject content
        subject = (self.email_output_dir / 'subject').read_text()
        self.assertEqual(subject, '[Test Monitor] 2 new releases detected')

        # Check body content
        body = (self.email_output_dir / 'body').read_text()
        self.assertIn('Total new releases: 2', body)
        self.assertIn('kubernetes/kubernetes', body)
        self.assertIn('v1.28.0', body)
        self.assertIn('prometheus/prometheus', body)
        self.assertIn('v2.46.0', body)
        self.assertIn('kubernetes-client-linux-amd64.tar.gz (48.0 MB)', body)

        # Check HTML content
        html = (self.email_output_dir / 'body.html').read_text()
        self.assertIn('<h2>New GitHub Releases Detected</h2>', html)
        self.assertIn('kubernetes/kubernetes - Kubernetes v1.28.0', html)
        self.assertIn('prometheus/prometheus - 2.46.0 / 2023-07-25', html)

    def test_no_releases_scenario(self):
        """Test when there are no new releases"""
        # Create empty releases file
        empty_releases = {
            "timestamp": "2023-08-15T14:00:00+00:00",
            "total_repositories_checked": 3,
            "new_releases_found": 0,
            "releases": []
        }

        with open(self.release_output_dir / 'releases.json', 'w') as f:
            json.dump(empty_releases, f)

        script_path = Path(__file__).parent.parent.parent / 'ci' / 'tasks' / 'send-release-notification' / 'generate_email.py'

        # Set up environment with custom paths
        env = os.environ.copy()
        env['RELEASES_INPUT_DIR'] = str(self.release_output_dir)
        env['EMAIL_OUTPUT_DIR'] = str(self.email_output_dir)

        # Add project root to Python path and run script
        project_root = script_path.parent.parent.parent
        script_content = f"""
import sys
sys.path.insert(0, '{project_root}')
{script_path.read_text()}
"""

        result = subprocess.run(
            [sys.executable, '-c', script_content],
            env=env,
            capture_output=True,
            text=True
        )

        # Should exit cleanly
        self.assertEqual(result.returncode, 0)
        self.assertIn('No releases found in releases.json, creating empty email notification', result.stdout)

        # Empty email files should be created
        self.assertTrue((self.email_output_dir / 'subject').exists())
        self.assertTrue((self.email_output_dir / 'body').exists())
        self.assertEqual((self.email_output_dir / 'subject').read_text(), '')
        self.assertEqual((self.email_output_dir / 'body').read_text(), '')

    def test_environment_variable_overrides(self):
        """Test environment variable configuration"""
        script_path = Path(__file__).parent.parent.parent / 'ci' / 'tasks' / 'send-release-notification' / 'generate_email.py'

        # Test with custom paths and configuration
        env = os.environ.copy()
        env['EMAIL_SUBJECT_PREFIX'] = '[PRODUCTION]'
        env['INCLUDE_ASSET_DETAILS'] = 'false'
        env['RELEASES_INPUT_DIR'] = str(self.release_output_dir)
        env['EMAIL_OUTPUT_DIR'] = str(self.email_output_dir)

        # Run with single release
        single_release = {
            "releases": [self.sample_releases["releases"][0]]
        }

        with open(self.release_output_dir / 'releases.json', 'w') as f:
            json.dump(single_release, f)

        # Add project root to Python path and run script directly
        project_root = script_path.parent.parent.parent
        script_content = f"""
import sys
sys.path.insert(0, '{project_root}')
{script_path.read_text()}
"""

        result = subprocess.run(
            [sys.executable, '-c', script_content],
            env=env,
            capture_output=True,
            text=True
        )

        self.assertEqual(result.returncode, 0)

        # Check custom subject prefix
        subject = (self.email_output_dir / 'subject').read_text()
        self.assertIn('[PRODUCTION]', subject)

        # Check assets are not included
        body = (self.email_output_dir / 'body').read_text()
        self.assertNotIn('Assets:', body)
        self.assertNotIn('kubernetes-client-linux-amd64.tar.gz', body)


class TestConcourseTaskIntegration(unittest.TestCase):
    """Test the Concourse task configuration"""

    def test_task_yaml_validity(self):
        """Test that the task YAML is valid"""
        import yaml

        task_file = Path(__file__).parent.parent.parent / 'ci' / 'tasks' / 'send-release-notification' / 'task.yml'

        with open(task_file, 'r') as f:
            task_config = yaml.safe_load(f)

        # Verify required fields
        self.assertEqual(task_config['platform'], 'linux')
        self.assertIn('image_resource', task_config)
        self.assertIn('inputs', task_config)
        self.assertIn('outputs', task_config)
        self.assertIn('params', task_config)
        self.assertIn('run', task_config)

        # Check inputs
        input_names = [i['name'] for i in task_config['inputs']]
        self.assertIn('release-monitor-repo', input_names)
        self.assertIn('release-output', input_names)

        # Check outputs
        output_names = [o['name'] for o in task_config['outputs']]
        self.assertIn('email', output_names)

        # Check params
        self.assertIn('EMAIL_SUBJECT_PREFIX', task_config['params'])
        self.assertIn('INCLUDE_ASSET_DETAILS', task_config['params'])


if __name__ == '__main__':
    unittest.main()
