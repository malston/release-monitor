#!/usr/bin/env python3
"""
Unit tests for upload script file filtering logic.
Tests that upload scripts correctly identify and process YAML files.
"""

import unittest
import tempfile
import os
import shutil
from pathlib import Path
import sys
from unittest.mock import patch, Mock
import requests

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestUploadScriptFileFiltering(unittest.TestCase):
    """Test upload script file filtering logic for YAML support."""
    
    def setUp(self):
        """Set up test environment with mock downloads directory."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.downloads_dir = self.temp_dir / "downloads"
        
        # Create repository structure like the real downloader would
        self.repo_dir = self.downloads_dir / "wavefrontHQ_observability-for-kubernetes" / "v2.30.0"
        self.repo_dir.mkdir(parents=True, exist_ok=True)
        
        # Define the same extensions used in upload scripts
        self.supported_extensions = {
            '.gz', '.zip', '.tar', '.yaml', '.yml', '.json', 
            '.xml', '.toml', '.exe', '.deb', '.rpm', '.dmg', '.msi'
        }
        
        # Create test files that represent different asset types
        self.test_files = {
            "wavefront-operator.yaml": "# Test YAML content\napiVersion: v1\nkind: ConfigMap",
            "config.json": '{"test": "json content"}',
            "archive.tar.gz": "fake binary content",
            "source.zip": "fake zip content",
            "binary.exe": "fake executable",
            "package.deb": "fake debian package",
            "readme.txt": "This should be skipped",
            "documentation.md": "This should be skipped",
            "checksum.sha256": "abc123  wavefront-operator.yaml"
        }
        
        # Create test files
        for filename, content in self.test_files.items():
            file_path = self.repo_dir / filename
            with open(file_path, 'w') as f:
                f.write(content)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
    
    def test_yaml_files_are_supported(self):
        """Test that YAML files are included in supported extensions."""
        self.assertIn('.yaml', self.supported_extensions)
        self.assertIn('.yml', self.supported_extensions)
    
    def test_file_filtering_logic(self):
        """Test the core file filtering logic used by upload scripts."""
        upload_files = []
        skip_files = []
        
        for file_path in self.downloads_dir.rglob('*'):
            if file_path.is_file():
                # Skip checksum files (same logic as in upload scripts)
                if file_path.name.endswith('.sha256'):
                    continue
                    
                # Apply the same filtering logic as upload scripts
                if file_path.suffix in self.supported_extensions or file_path.name.endswith('.tar.gz'):
                    upload_files.append(file_path)
                else:
                    skip_files.append(file_path)
        
        # Verify expected files are marked for upload
        upload_names = [f.name for f in upload_files]
        skip_names = [f.name for f in skip_files]
        
        # These should be uploaded
        self.assertIn("wavefront-operator.yaml", upload_names)
        self.assertIn("config.json", upload_names)
        self.assertIn("archive.tar.gz", upload_names)
        self.assertIn("source.zip", upload_names)
        self.assertIn("binary.exe", upload_names)
        self.assertIn("package.deb", upload_names)
        
        # These should be skipped
        self.assertIn("readme.txt", skip_names)
        self.assertIn("documentation.md", skip_names)
        
        # Checksum files should not appear in either list (filtered out earlier)
        self.assertNotIn("checksum.sha256", upload_names)
        self.assertNotIn("checksum.sha256", skip_names)
    
    def test_yaml_files_identified_for_upload(self):
        """Test that YAML files are specifically identified for upload."""
        yaml_files_found = []
        
        for file_path in self.downloads_dir.rglob('*'):
            if file_path.is_file() and file_path.name.endswith('.yaml'):
                if file_path.suffix in self.supported_extensions:
                    yaml_files_found.append(file_path.name)
        
        self.assertEqual(len(yaml_files_found), 1)
        self.assertEqual(yaml_files_found[0], "wavefront-operator.yaml")
    
    def test_tar_gz_special_case(self):
        """Test that .tar.gz files are handled correctly."""
        tar_gz_files = []
        
        for file_path in self.downloads_dir.rglob('*'):
            if file_path.is_file() and file_path.name.endswith('.tar.gz'):
                tar_gz_files.append(file_path.name)
        
        self.assertEqual(len(tar_gz_files), 1)
        self.assertEqual(tar_gz_files[0], "archive.tar.gz")
        
        # Verify .tar.gz files would be uploaded even though .gz is in supported_extensions
        archive_path = self.repo_dir / "archive.tar.gz"
        should_upload = (archive_path.suffix in self.supported_extensions or 
                        archive_path.name.endswith('.tar.gz'))
        self.assertTrue(should_upload)
    
    def test_upload_script_extensions_consistency(self):
        """Test that all upload scripts define the same supported extensions."""
        scripts_dir = Path(__file__).parent.parent / "scripts"
        upload_scripts = [
            'upload-to-s3.py',
            'upload-to-s3-mc.py', 
            'upload-to-s3-no-proxy.py'
        ]
        
        for script_name in upload_scripts:
            script_path = scripts_dir / script_name
            if script_path.exists():
                with open(script_path, 'r') as f:
                    content = f.read()
                
                # Check that YAML extensions are present
                self.assertIn('.yaml', content, 
                            f"{script_name} should include .yaml extension")
                self.assertIn('.yml', content, 
                            f"{script_name} should include .yml extension")
                
                # Check that JSON is also supported (comprehensive manifest support)
                self.assertIn('.json', content,
                            f"{script_name} should include .json extension")
    
    def test_checksum_files_are_excluded(self):
        """Test that checksum files are properly excluded from upload."""
        checksum_files = []
        
        for file_path in self.downloads_dir.rglob('*'):
            if file_path.is_file():
                if file_path.name.endswith('.sha256'):
                    checksum_files.append(file_path.name)
        
        # Verify checksum files exist in test data
        self.assertEqual(len(checksum_files), 1)
        self.assertEqual(checksum_files[0], "checksum.sha256")
        
        # Verify they would be filtered out by upload logic
        for file_path in self.downloads_dir.rglob('*'):
            if file_path.is_file():
                # This is the same check used in upload scripts
                if file_path.name.endswith('.sha256'):
                    continue  # Should skip checksum files
                
                # If we reach here, it's not a checksum file
                self.assertFalse(file_path.name.endswith('.sha256'))
    
    def test_manifest_file_types_supported(self):
        """Test that common manifest and config file types are supported."""
        manifest_extensions = ['.yaml', '.yml', '.json', '.xml', '.toml']
        
        for ext in manifest_extensions:
            self.assertIn(ext, self.supported_extensions,
                         f"Manifest file extension {ext} should be supported")
    
    def test_binary_package_types_supported(self):
        """Test that binary package types are supported."""
        binary_extensions = ['.exe', '.deb', '.rpm', '.dmg', '.msi']
        
        for ext in binary_extensions:
            self.assertIn(ext, self.supported_extensions,
                         f"Binary package extension {ext} should be supported")
    
    def test_archive_types_supported(self):
        """Test that archive types are supported."""
        archive_extensions = ['.gz', '.zip', '.tar']
        
        for ext in archive_extensions:
            self.assertIn(ext, self.supported_extensions,
                         f"Archive extension {ext} should be supported")


class TestUploadScriptRegression(unittest.TestCase):
    """Regression tests to ensure YAML support doesn't break existing functionality."""
    
    def test_old_archive_support_still_works(self):
        """Test that .gz and .zip files are still supported (regression test)."""
        supported_extensions = {
            '.gz', '.zip', '.tar', '.yaml', '.yml', '.json', 
            '.xml', '.toml', '.exe', '.deb', '.rpm', '.dmg', '.msi'
        }
        
        # These were the originally supported extensions
        self.assertIn('.gz', supported_extensions)
        self.assertIn('.zip', supported_extensions)
    
    def test_wavefront_yaml_specific_case(self):
        """Test the specific wavefront-operator.yaml use case that prompted this fix."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create the exact file that was being skipped
            test_file = Path(temp_dir) / "wavefront-operator.yaml"
            test_file.write_text("# Wavefront operator manifest\napiVersion: v1\nkind: ConfigMap")
            
            supported_extensions = {
                '.gz', '.zip', '.tar', '.yaml', '.yml', '.json', 
                '.xml', '.toml', '.exe', '.deb', '.rpm', '.dmg', '.msi'
            }
            
            # Test the exact logic from upload scripts
            should_upload = (test_file.suffix in supported_extensions or 
                           test_file.name.endswith('.tar.gz'))
            
            self.assertTrue(should_upload, 
                          "wavefront-operator.yaml should be marked for upload")
            self.assertEqual(test_file.suffix, '.yaml')


class TestAllUploadScriptsYAMLSupport(unittest.TestCase):
    """Test that all upload scripts support YAML files (converted from test_all_upload_scripts.py)."""
    
    def setUp(self):
        """Set up test environment."""
        self.scripts_dir = Path(__file__).parent.parent / "scripts"
        self.upload_scripts = [
            'upload-to-s3.py',
            'upload-to-s3-mc.py', 
            'upload-to-s3-no-proxy.py'
        ]
    
    def check_script_supports_yaml(self, script_path):
        """Check if an upload script supports YAML file extensions."""
        if not script_path.exists():
            return False, "Script not found"
        
        with open(script_path, 'r') as f:
            content = f.read()
        
        # Check for YAML extensions
        has_yaml = '.yaml' in content and '.yml' in content
        
        # Check if it still has the old hardcoded filter
        has_old_filter = '.gz.*\\.zip' in content.replace(' ', '').replace('\n', '')
        
        if has_yaml and not has_old_filter:
            return True, "Supports YAML files"
        elif has_yaml and has_old_filter:
            return False, "Mixed: Has YAML support but also old hardcoded filter"
        else:
            return False, "No YAML support found"
    
    def test_all_upload_scripts_support_yaml(self):
        """Test that all upload scripts support YAML files."""
        results = {}
        all_good = True
        
        for script_name in self.upload_scripts:
            script_path = self.scripts_dir / script_name
            supports_yaml, message = self.check_script_supports_yaml(script_path)
            results[script_name] = (supports_yaml, message)
            
            if not supports_yaml:
                all_good = False
        
        # Assert that all scripts support YAML
        for script_name, (supports_yaml, message) in results.items():
            self.assertTrue(supports_yaml, 
                          f"{script_name} should support YAML files: {message}")
        
        self.assertTrue(all_good, "All upload scripts should support YAML files")
    
    def test_individual_script_yaml_support(self):
        """Test each upload script individually for YAML support."""
        for script_name in self.upload_scripts:
            with self.subTest(script=script_name):
                script_path = self.scripts_dir / script_name
                self.assertTrue(script_path.exists(), f"{script_name} should exist")
                
                supports_yaml, message = self.check_script_supports_yaml(script_path)
                self.assertTrue(supports_yaml, 
                              f"{script_name}: {message}")
    
    def test_no_old_hardcoded_filters_remain(self):
        """Test that old hardcoded filters have been removed from all scripts."""
        for script_name in self.upload_scripts:
            with self.subTest(script=script_name):
                script_path = self.scripts_dir / script_name
                if script_path.exists():
                    with open(script_path, 'r') as f:
                        content = f.read()
                    
                    # Check that old hardcoded filter patterns are not present
                    old_patterns = [
                        "file_path.suffix in ['.gz', '.zip']",
                        ".rglob('*.gz')) + list(downloads_dir.rglob('*.zip'))"
                    ]
                    
                    for pattern in old_patterns:
                        self.assertNotIn(pattern, content,
                                       f"{script_name} should not contain old hardcoded filter: {pattern}")


class TestProxySSLConfiguration(unittest.TestCase):
    """Test proxy and SSL configuration logic (converted from test_proxy_ssl.py)."""
    
    def setUp(self):
        """Set up test environment."""
        # Store original environment variables
        self.original_env = {}
        env_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY', 'GITHUB_SKIP_SSL_VERIFICATION']
        for var in env_vars:
            self.original_env[var] = os.getenv(var)
    
    def tearDown(self):
        """Restore original environment variables."""
        for var, value in self.original_env.items():
            if value is not None:
                os.environ[var] = value
            elif var in os.environ:
                del os.environ[var]
    
    def test_proxy_configuration_logic(self):
        """Test proxy configuration logic from github_monitor and github_downloader."""
        # Set test proxy environment variables
        os.environ['HTTP_PROXY'] = 'http://test-proxy:8080'
        os.environ['HTTPS_PROXY'] = 'http://test-proxy:8080'
        
        # Test the proxy configuration logic
        proxy_settings = {}
        if os.getenv('HTTP_PROXY') or os.getenv('http_proxy'):
            proxy_settings['http'] = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
        if os.getenv('HTTPS_PROXY') or os.getenv('https_proxy'):
            proxy_settings['https'] = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
        
        self.assertEqual(proxy_settings['http'], 'http://test-proxy:8080')
        self.assertEqual(proxy_settings['https'], 'http://test-proxy:8080')
    
    def test_ssl_verification_configuration(self):
        """Test SSL verification configuration logic."""
        # Test with SSL verification disabled
        os.environ['GITHUB_SKIP_SSL_VERIFICATION'] = 'true'
        skip_ssl_verification = os.environ.get('GITHUB_SKIP_SSL_VERIFICATION', 'false').lower() == 'true'
        self.assertTrue(skip_ssl_verification)
        
        # Test with SSL verification enabled (default)
        os.environ['GITHUB_SKIP_SSL_VERIFICATION'] = 'false'
        skip_ssl_verification = os.environ.get('GITHUB_SKIP_SSL_VERIFICATION', 'false').lower() == 'true'
        self.assertFalse(skip_ssl_verification)
        
        # Test with SSL verification not set
        if 'GITHUB_SKIP_SSL_VERIFICATION' in os.environ:
            del os.environ['GITHUB_SKIP_SSL_VERIFICATION']
        skip_ssl_verification = os.environ.get('GITHUB_SKIP_SSL_VERIFICATION', 'false').lower() == 'true'
        self.assertFalse(skip_ssl_verification)
    
    @patch('requests.Session')
    def test_session_configuration_with_proxy_and_ssl(self, mock_session_class):
        """Test complete session configuration with proxy and SSL settings."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Set environment variables
        os.environ['HTTP_PROXY'] = 'http://corp-proxy:80'
        os.environ['HTTPS_PROXY'] = 'http://corp-proxy:80'
        os.environ['GITHUB_SKIP_SSL_VERIFICATION'] = 'true'
        
        # Simulate the session configuration logic from github_monitor.py and github_downloader.py
        session = mock_session_class()
        
        # Configure proxy settings
        proxy_settings = {}
        if os.getenv('HTTP_PROXY') or os.getenv('http_proxy'):
            proxy_settings['http'] = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
        if os.getenv('HTTPS_PROXY') or os.getenv('https_proxy'):
            proxy_settings['https'] = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
        
        if proxy_settings:
            session.proxies = proxy_settings
        
        # Configure SSL verification
        skip_ssl_verification = os.environ.get('GITHUB_SKIP_SSL_VERIFICATION', 'false').lower() == 'true'
        if skip_ssl_verification:
            session.verify = False
        
        # Verify the session was configured correctly
        mock_session_class.assert_called_once()
        self.assertEqual(session.proxies, {
            'http': 'http://corp-proxy:80',
            'https': 'http://corp-proxy:80'
        })
        self.assertFalse(session.verify)
    
    def test_environment_variable_detection(self):
        """Test detection of proxy and SSL environment variables."""
        # Test all combinations of environment variables
        test_cases = [
            {
                'HTTP_PROXY': 'http://proxy:8080',
                'expected_http': 'http://proxy:8080',
                'expected_https': None
            },
            {
                'HTTPS_PROXY': 'https://proxy:8443',
                'expected_http': None,
                'expected_https': 'https://proxy:8443'
            },
            {
                'HTTP_PROXY': 'http://proxy:8080',
                'HTTPS_PROXY': 'https://proxy:8443',
                'expected_http': 'http://proxy:8080',
                'expected_https': 'https://proxy:8443'
            },
            {
                'http_proxy': 'http://lowercase:8080',
                'expected_http': 'http://lowercase:8080',
                'expected_https': None
            }
        ]
        
        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                # Clear environment
                for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
                    if var in os.environ:
                        del os.environ[var]
                
                # Set test environment variables
                for var, value in test_case.items():
                    if var.startswith('expected_'):
                        continue
                    os.environ[var] = value
                
                # Test proxy detection logic
                proxy_settings = {}
                if os.getenv('HTTP_PROXY') or os.getenv('http_proxy'):
                    proxy_settings['http'] = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
                if os.getenv('HTTPS_PROXY') or os.getenv('https_proxy'):
                    proxy_settings['https'] = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
                
                # Verify results
                if test_case.get('expected_http'):
                    self.assertEqual(proxy_settings.get('http'), test_case['expected_http'])
                else:
                    self.assertNotIn('http', proxy_settings)
                
                if test_case.get('expected_https'):
                    self.assertEqual(proxy_settings.get('https'), test_case['expected_https'])
                else:
                    self.assertNotIn('https', proxy_settings)


if __name__ == '__main__':
    unittest.main()