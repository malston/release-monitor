#!/usr/bin/env python3
"""
Unit tests for Version Comparison Logic
"""

import unittest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from version_compare import VersionComparator


class TestVersionComparator(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment."""
        self.comparator = VersionComparator(include_prereleases=False)
        self.comparator_with_prereleases = VersionComparator(include_prereleases=True)
    
    def test_semver_parsing(self):
        """Test SemVer parsing."""
        test_cases = [
            ('1.2.3', {'type': 'semver', 'major': 1, 'minor': 2, 'patch': 3}),
            ('v1.2.3', {'type': 'semver', 'major': 1, 'minor': 2, 'patch': 3}),
            ('1.2.3-alpha.1', {'type': 'semver', 'major': 1, 'minor': 2, 'patch': 3, 'prerelease': 'alpha.1'}),
            ('1.2.3+build.1', {'type': 'semver', 'major': 1, 'minor': 2, 'patch': 3, 'build': 'build.1'}),
            ('1.2.3-beta.2+exp.sha.5114f85', {'type': 'semver', 'major': 1, 'minor': 2, 'patch': 3, 'prerelease': 'beta.2', 'build': 'exp.sha.5114f85'})
        ]
        
        for version, expected in test_cases:
            with self.subTest(version=version):
                parsed = self.comparator.parse_version(version)
                self.assertEqual(parsed['type'], expected['type'])
                for key, value in expected.items():
                    if key != 'type':
                        self.assertEqual(parsed[key], value)
    
    def test_calver_parsing(self):
        """Test CalVer parsing."""
        test_cases = [
            ('2024.01.15', {'type': 'calver', 'year': 2024, 'month': 1, 'day': 15, 'micro': 0}),
            ('2024.1.0', {'type': 'calver', 'year': 2024, 'month': 1, 'day': 1, 'micro': 0}),
            ('24.01', {'type': 'calver', 'year': 2024, 'month': 1, 'day': 1, 'micro': 0}),
            ('2024.12.31.1', {'type': 'calver', 'year': 2024, 'month': 12, 'day': 31, 'micro': 1}),
            ('2024.01.15-alpha', {'type': 'calver', 'year': 2024, 'month': 1, 'day': 15, 'modifier': 'alpha'})
        ]
        
        for version, expected in test_cases:
            with self.subTest(version=version):
                parsed = self.comparator.parse_version(version)
                self.assertEqual(parsed['type'], expected['type'])
                for key, value in expected.items():
                    if key != 'type':
                        self.assertEqual(parsed[key], value)
    
    def test_numeric_parsing(self):
        """Test numeric version parsing."""
        test_cases = [
            ('1.0', {'type': 'numeric', 'major': 1, 'minor': 0, 'patch': 0, 'build': 0}),
            ('1.2.3.4', {'type': 'numeric', 'major': 1, 'minor': 2, 'patch': 3, 'build': 4}),
            ('v10.1', {'type': 'numeric', 'major': 10, 'minor': 1, 'patch': 0, 'build': 0}),
            ('1.0-rc1', {'type': 'numeric', 'major': 1, 'minor': 0, 'patch': 0, 'build': 0, 'suffix': 'rc1'})
        ]
        
        for version, expected in test_cases:
            with self.subTest(version=version):
                parsed = self.comparator.parse_version(version)
                self.assertEqual(parsed['type'], expected['type'])
                for key, value in expected.items():
                    if key != 'type':
                        self.assertEqual(parsed[key], value)
    
    def test_semver_comparison(self):
        """Test SemVer comparison logic."""
        test_cases = [
            # Basic comparisons
            ('1.0.0', '1.0.1', -1),  # patch version newer
            ('1.0.1', '1.0.0', 1),   # patch version older
            ('1.0.0', '1.1.0', -1),  # minor version newer
            ('1.1.0', '1.0.0', 1),   # minor version older
            ('1.0.0', '2.0.0', -1),  # major version newer
            ('2.0.0', '1.0.0', 1),   # major version older
            ('1.0.0', '1.0.0', 0),   # equal
            
            # Pre-release comparisons
            ('1.0.0-alpha', '1.0.0', -1),      # pre-release < release
            ('1.0.0', '1.0.0-alpha', 1),       # release > pre-release
            ('1.0.0-alpha', '1.0.0-beta', -1), # alpha < beta
            ('1.0.0-alpha.1', '1.0.0-alpha.2', -1), # alpha.1 < alpha.2
            ('1.0.0-rc.1', '1.0.0-rc.2', -1),  # rc.1 < rc.2
        ]
        
        for v1, v2, expected in test_cases:
            with self.subTest(v1=v1, v2=v2):
                result = self.comparator.compare(v1, v2)
                self.assertEqual(result, expected, f"{v1} vs {v2} should be {expected}, got {result}")
    
    def test_calver_comparison(self):
        """Test CalVer comparison logic."""
        test_cases = [
            ('2024.01.15', '2024.01.16', -1),  # day newer
            ('2024.01.15', '2024.02.15', -1),  # month newer
            ('2024.01.15', '2025.01.15', -1),  # year newer
            ('2024.12.31', '2024.01.01', 1),   # year same, month/day older
            ('2024.01.15', '2024.01.15', 0),   # equal
            ('2024.01.15.1', '2024.01.15.2', -1), # micro version
        ]
        
        for v1, v2, expected in test_cases:
            with self.subTest(v1=v1, v2=v2):
                result = self.comparator.compare(v1, v2)
                self.assertEqual(result, expected, f"{v1} vs {v2} should be {expected}, got {result}")
    
    def test_numeric_comparison(self):
        """Test numeric version comparison."""
        test_cases = [
            ('1.0', '1.1', -1),
            ('1.1', '1.0', 1),
            ('1.0.0', '1.0.1', -1),
            ('2.0', '1.9', 1),
            ('1.0.0.1', '1.0.0.2', -1),
            ('10.0', '9.0', 1),  # Numeric comparison, not string
        ]
        
        for v1, v2, expected in test_cases:
            with self.subTest(v1=v1, v2=v2):
                result = self.comparator.compare(v1, v2)
                self.assertEqual(result, expected, f"{v1} vs {v2} should be {expected}, got {result}")
    
    def test_is_newer_basic(self):
        """Test is_newer method with basic cases."""
        # First time (no stored version)
        self.assertTrue(self.comparator.is_newer('1.0.0', None))
        
        # Newer version
        self.assertTrue(self.comparator.is_newer('1.1.0', '1.0.0'))
        
        # Older version
        self.assertFalse(self.comparator.is_newer('1.0.0', '1.1.0'))
        
        # Same version
        self.assertFalse(self.comparator.is_newer('1.0.0', '1.0.0'))
    
    def test_prerelease_handling(self):
        """Test pre-release version handling."""
        # Without pre-releases enabled
        self.assertFalse(self.comparator.is_newer('1.0.0-alpha', '0.9.0'))
        self.assertFalse(self.comparator.is_newer('1.0.0-beta.1', None))
        
        # With pre-releases enabled
        self.assertTrue(self.comparator_with_prereleases.is_newer('1.0.0-alpha', '0.9.0'))
        self.assertTrue(self.comparator_with_prereleases.is_newer('1.0.0-beta.1', None))
    
    def test_prerelease_detection(self):
        """Test pre-release detection."""
        prerelease_versions = [
            '1.0.0-alpha',
            '1.0.0-beta.1',
            '1.0.0-rc.1',
            '1.0.0-pre',
            '1.0.0-preview',
            '1.0.0-snapshot',
            '1.0.0-dev',
            '1.0.0-nightly',
            '1.0.0-canary',
            '1.0.0-experimental'
        ]
        
        for version in prerelease_versions:
            with self.subTest(version=version):
                self.assertTrue(self.comparator._is_prerelease(version))
        
        release_versions = [
            '1.0.0',
            '1.2.3',
            '2024.01.15',
            '1.0-final'
        ]
        
        for version in release_versions:
            with self.subTest(version=version):
                self.assertFalse(self.comparator._is_prerelease(version))
    
    def test_mixed_version_types(self):
        """Test comparison of different version types."""
        # When types don't match, should fall back to string comparison
        result = self.comparator.compare('1.0.0', '2024.01.15')
        # This should not crash and return some consistent result
        self.assertIn(result, [-1, 0, 1])
    
    def test_unknown_version_format(self):
        """Test handling of unknown version formats."""
        unknown_versions = [
            'random-string',
            'build-123',
            'latest',
            'stable'
        ]
        
        for version in unknown_versions:
            with self.subTest(version=version):
                parsed = self.comparator.parse_version(version)
                self.assertEqual(parsed['type'], 'unknown')
                self.assertEqual(parsed['original'], version)
    
    def test_edge_cases(self):
        """Test edge cases and error conditions."""
        # Empty/None versions
        self.assertEqual(self.comparator.compare('', ''), 0)
        self.assertEqual(self.comparator.compare(None, None), 0)
        self.assertEqual(self.comparator.compare('1.0.0', ''), 1)
        self.assertEqual(self.comparator.compare('', '1.0.0'), -1)
        
        # Whitespace handling
        self.assertEqual(self.comparator.compare(' 1.0.0 ', '1.0.0'), 0)
    
    def test_version_info(self):
        """Test get_version_info method."""
        info = self.comparator.get_version_info('1.2.3-alpha.1')
        
        self.assertEqual(info['original'], '1.2.3-alpha.1')
        self.assertEqual(info['type'], 'semver')
        self.assertTrue(info['is_prerelease'])
        self.assertIn('parsed', info)
    
    def test_real_world_versions(self):
        """Test with real-world version examples."""
        kubernetes_versions = [
            'v1.28.0',
            'v1.28.1',
            'v1.29.0-alpha.1',
            'v1.29.0-beta.0',
            'v1.29.0'
        ]
        
        # Test that versions are ordered correctly
        for i in range(len(kubernetes_versions) - 1):
            v1 = kubernetes_versions[i]
            v2 = kubernetes_versions[i + 1]
            with self.subTest(v1=v1, v2=v2):
                # Each version should be less than the next
                result = self.comparator_with_prereleases.compare(v1, v2)
                self.assertEqual(result, -1, f"{v1} should be less than {v2}")
    
    def test_complex_prerelease_comparison(self):
        """Test complex pre-release version comparisons."""
        test_cases = [
            ('1.0.0-alpha', '1.0.0-alpha.1', -1),
            ('1.0.0-alpha.1', '1.0.0-alpha.beta', -1),
            ('1.0.0-alpha.beta', '1.0.0-beta', -1),
            ('1.0.0-beta', '1.0.0-beta.2', -1),
            ('1.0.0-beta.2', '1.0.0-beta.11', -1),
            ('1.0.0-beta.11', '1.0.0-rc.1', -1),
            ('1.0.0-rc.1', '1.0.0', -1)
        ]
        
        for v1, v2, expected in test_cases:
            with self.subTest(v1=v1, v2=v2):
                result = self.comparator_with_prereleases.compare(v1, v2)
                self.assertEqual(result, expected, f"{v1} vs {v2} should be {expected}, got {result}")


if __name__ == '__main__':
    unittest.main()