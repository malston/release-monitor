#!/usr/bin/env python3
"""
Version Comparison Logic

Handles intelligent comparison of version strings supporting various formats:
- Semantic Versioning (SemVer): 1.2.3, 1.2.3-alpha.1, 1.2.3+build.1
- Calendar Versioning (CalVer): 2024.01.15, 2024.1.0, 24.01
- Custom formats: v1.0, release-1.0, etc.
"""

import re
import logging
from typing import Optional, Tuple, List, Union
from datetime import datetime

logger = logging.getLogger(__name__)


class VersionComparator:
    """
    Handles comparison of version strings with support for multiple formats.
    """
    
    # Regex patterns for different version formats
    SEMVER_PATTERN = re.compile(
        r'^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)'
        r'(?:-(?P<prerelease>[0-9A-Za-z\-\.]+))?'
        r'(?:\+(?P<build>[0-9A-Za-z\-\.]+))?$'
    )
    
    CALVER_PATTERN = re.compile(
        r'^v?(?P<year>20\d{2}|19\d{2})\.(?P<month>0?\d|1[0-2])(?:\.(?P<day>[0-3]?\d))?'
        r'(?:\.(?P<micro>\d+))?(?:-(?P<modifier>[0-9A-Za-z\-\.]+))?$'
    )
    
    SIMPLE_NUMERIC_PATTERN = re.compile(
        r'^v?(?P<major>\d+)(?:\.(?P<minor>\d+))?(?:\.(?P<patch>\d+))?'
        r'(?:\.(?P<build>\d+))?(?:-(?P<suffix>[0-9A-Za-z\-\.]+))?$'
    )
    
    def __init__(self, include_prereleases: bool = False):
        """
        Initialize version comparator.
        
        Args:
            include_prereleases: Whether to consider pre-releases as valid newer versions
        """
        self.include_prereleases = include_prereleases
    
    def compare(self, version1: str, version2: str) -> int:
        """
        Compare two version strings.
        
        Args:
            version1: First version string
            version2: Second version string
            
        Returns:
            -1 if version1 < version2
             0 if version1 == version2
             1 if version1 > version2
        """
        if not version1 or not version2:
            # Handle None/empty versions
            if version1 == version2:
                return 0
            return -1 if not version1 else 1
        
        # Try to parse as different version types
        v1_parsed = self.parse_version(version1)
        v2_parsed = self.parse_version(version2)
        
        # If both versions are the same type, compare appropriately
        if v1_parsed['type'] == v2_parsed['type'] and v1_parsed['type'] != 'unknown':
            return self._compare_parsed_versions(v1_parsed, v2_parsed)
        
        # Fallback to string comparison for unknown or mismatched types
        logger.debug(f"Using string comparison for {version1} vs {version2}")
        return self._string_compare(version1, version2)
    
    def is_newer(self, release_version: str, stored_version: Optional[str]) -> bool:
        """
        Determine if release version is newer than stored version.
        
        Args:
            release_version: Version from GitHub release
            stored_version: Currently stored version (None if first time)
            
        Returns:
            True if release_version is newer
        """
        if not release_version:
            return False
            
        # Check for pre-release exclusion
        if not self.include_prereleases and self._is_prerelease(release_version):
            logger.debug(f"Skipping pre-release: {release_version}")
            return False
        
        if not stored_version:
            # First time seeing this repository, accept if not a filtered pre-release
            return True
        
        comparison = self.compare(release_version, stored_version)
        is_newer = comparison > 0
        
        logger.debug(f"Version comparison: {release_version} vs {stored_version} = {comparison} (newer: {is_newer})")
        return is_newer
    
    def parse_version(self, version_string: str) -> dict:
        """
        Parse version string into components.
        
        Args:
            version_string: Version string to parse
            
        Returns:
            Dictionary with parsed version components and type
        """
        if not version_string:
            return {'type': 'unknown', 'original': version_string}
        
        # Clean the version string
        clean_version = version_string.strip()
        
        # Try SemVer first
        semver_match = self.SEMVER_PATTERN.match(clean_version)
        if semver_match:
            return {
                'type': 'semver',
                'original': version_string,
                'major': int(semver_match.group('major')),
                'minor': int(semver_match.group('minor')),
                'patch': int(semver_match.group('patch')),
                'prerelease': semver_match.group('prerelease'),
                'build': semver_match.group('build')
            }
        
        # Try CalVer
        calver_match = self.CALVER_PATTERN.match(clean_version)
        if calver_match:
            year = int(calver_match.group('year'))
            # Convert 2-digit years to 4-digit
            if year < 100:
                year += 2000 if year < 50 else 1900
            
            return {
                'type': 'calver',
                'original': version_string,
                'year': year,
                'month': int(calver_match.group('month')),
                'day': int(calver_match.group('day')) if calver_match.group('day') else 1,
                'micro': int(calver_match.group('micro')) if calver_match.group('micro') else 0,
                'modifier': calver_match.group('modifier')
            }
        
        # Try simple numeric versioning
        numeric_match = self.SIMPLE_NUMERIC_PATTERN.match(clean_version)
        if numeric_match:
            return {
                'type': 'numeric',
                'original': version_string,
                'major': int(numeric_match.group('major')),
                'minor': int(numeric_match.group('minor')) if numeric_match.group('minor') else 0,
                'patch': int(numeric_match.group('patch')) if numeric_match.group('patch') else 0,
                'build': int(numeric_match.group('build')) if numeric_match.group('build') else 0,
                'suffix': numeric_match.group('suffix')
            }
        
        # Couldn't parse - return as unknown
        logger.debug(f"Could not parse version format: {version_string}")
        return {
            'type': 'unknown',
            'original': version_string,
            'normalized': self._normalize_string_version(clean_version)
        }
    
    def _compare_parsed_versions(self, v1: dict, v2: dict) -> int:
        """Compare two parsed version dictionaries."""
        version_type = v1['type']
        
        if version_type == 'semver':
            return self._compare_semver(v1, v2)
        elif version_type == 'calver':
            return self._compare_calver(v1, v2)
        elif version_type == 'numeric':
            return self._compare_numeric(v1, v2)
        else:
            return self._string_compare(v1['original'], v2['original'])
    
    def _compare_semver(self, v1: dict, v2: dict) -> int:
        """Compare two SemVer versions."""
        # Compare major.minor.patch
        for component in ['major', 'minor', 'patch']:
            diff = v1[component] - v2[component]
            if diff != 0:
                return 1 if diff > 0 else -1
        
        # Handle pre-release versions
        pre1 = v1['prerelease']
        pre2 = v2['prerelease']
        
        if pre1 is None and pre2 is None:
            return 0
        elif pre1 is None:  # v1 is release, v2 is pre-release
            return 1
        elif pre2 is None:  # v1 is pre-release, v2 is release
            return -1
        else:  # Both are pre-releases
            return self._compare_prerelease_identifiers(pre1, pre2)
    
    def _compare_calver(self, v1: dict, v2: dict) -> int:
        """Compare two CalVer versions."""
        # Compare year, month, day, micro
        for component in ['year', 'month', 'day', 'micro']:
            diff = v1[component] - v2[component]
            if diff != 0:
                return 1 if diff > 0 else -1
        
        # Compare modifiers if present
        mod1 = v1['modifier']
        mod2 = v2['modifier']
        
        if mod1 is None and mod2 is None:
            return 0
        elif mod1 is None:
            return 1  # No modifier is "newer" than with modifier
        elif mod2 is None:
            return -1
        else:
            return self._string_compare(mod1, mod2)
    
    def _compare_numeric(self, v1: dict, v2: dict) -> int:
        """Compare two numeric versions."""
        # Compare major.minor.patch.build
        for component in ['major', 'minor', 'patch', 'build']:
            diff = v1[component] - v2[component]
            if diff != 0:
                return 1 if diff > 0 else -1
        
        # Compare suffixes
        suf1 = v1['suffix']
        suf2 = v2['suffix']
        
        if suf1 is None and suf2 is None:
            return 0
        elif suf1 is None:
            return 1  # No suffix is "newer"
        elif suf2 is None:
            return -1
        else:
            return self._string_compare(suf1, suf2)
    
    def _compare_prerelease_identifiers(self, pre1: str, pre2: str) -> int:
        """Compare pre-release version identifiers."""
        # Split by dots and compare each part
        parts1 = pre1.split('.')
        parts2 = pre2.split('.')
        
        for i in range(max(len(parts1), len(parts2))):
            p1 = parts1[i] if i < len(parts1) else ''
            p2 = parts2[i] if i < len(parts2) else ''
            
            # Try numeric comparison first
            try:
                n1 = int(p1) if p1 else 0
                n2 = int(p2) if p2 else 0
                diff = n1 - n2
                if diff != 0:
                    return 1 if diff > 0 else -1
            except ValueError:
                # Fall back to string comparison
                result = self._string_compare(p1, p2)
                if result != 0:
                    return result
        
        return 0
    
    def _string_compare(self, s1: str, s2: str) -> int:
        """Simple string comparison with numeric awareness."""
        if s1 == s2:
            return 0
        
        # Try to extract and compare numeric parts
        import re
        num_pattern = re.compile(r'(\d+)')
        
        s1_parts = num_pattern.split(s1.lower())
        s2_parts = num_pattern.split(s2.lower())
        
        for i in range(max(len(s1_parts), len(s2_parts))):
            p1 = s1_parts[i] if i < len(s1_parts) else ''
            p2 = s2_parts[i] if i < len(s2_parts) else ''
            
            # Try numeric comparison first
            if p1.isdigit() and p2.isdigit():
                diff = int(p1) - int(p2)
                if diff != 0:
                    return 1 if diff > 0 else -1
            else:
                # String comparison
                if p1 != p2:
                    return 1 if p1 > p2 else -1
        
        return 0
    
    def _normalize_string_version(self, version: str) -> str:
        """Normalize version string for comparison."""
        # Remove common prefixes and clean up
        normalized = re.sub(r'^v(?=\d)', '', version.lower())
        normalized = re.sub(r'^release[_\-]?', '', normalized)
        normalized = re.sub(r'^version[_\-]?', '', normalized)
        return normalized
    
    def _is_prerelease(self, version: str) -> bool:
        """Check if version appears to be a pre-release."""
        version_lower = version.lower()
        prerelease_indicators = [
            'alpha', 'beta', 'rc', 'pre', 'preview', 'snapshot',
            'dev', 'nightly', 'canary', 'experimental'
        ]
        
        return any(indicator in version_lower for indicator in prerelease_indicators)
    
    def get_version_info(self, version: str) -> dict:
        """
        Get detailed information about a version string.
        
        Args:
            version: Version string to analyze
            
        Returns:
            Dictionary with version analysis
        """
        parsed = self.parse_version(version)
        
        return {
            'original': version,
            'type': parsed['type'],
            'is_prerelease': self._is_prerelease(version),
            'parsed': parsed,
            'normalized': parsed.get('normalized', version)
        }