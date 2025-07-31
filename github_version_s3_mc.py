#!/usr/bin/env python3
"""
S3-based Version Storage using MinIO client (mc) for GitHub Release Monitor

This is an alternative to the boto3-based S3VersionStorage that uses
MinIO client (mc) for better compatibility with S3-compatible services.
"""

import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class S3VersionStorageMC:
    """
    S3-based version storage using MinIO client (mc) for tracking downloaded GitHub releases.

    Provides the same interface as VersionDatabase but uses mc for S3 operations.
    """

    def __init__(self, bucket: str, key_prefix: str = 'release-monitor/',
                 endpoint_url: Optional[str] = None, skip_ssl_verification: bool = False):
        """
        Initialize S3 version storage using mc.

        Args:
            bucket: S3 bucket name
            key_prefix: Prefix for all version keys in S3
            endpoint_url: S3 endpoint URL (optional, defaults to environment)
            skip_ssl_verification: Skip SSL verification for S3 endpoint
        """
        self.bucket = bucket
        self.key_prefix = key_prefix.rstrip('/') + '/'
        self.versions_key = f"{self.key_prefix}version_db.json"

        # Get S3 configuration from environment
        self.endpoint_url = endpoint_url or os.environ.get('S3_ENDPOINT', 'https://s3.example.com:443')
        self.access_key = os.environ.get('AWS_ACCESS_KEY_ID')
        self.secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        self.skip_ssl = skip_ssl_verification or os.environ.get('S3_SKIP_SSL_VERIFICATION', 'false').lower() == 'true'

        if not self.access_key or not self.secret_key:
            raise ValueError("AWS credentials not found in environment")

        # Configure mc alias
        self.alias = f"s3versiondb_{id(self)}"
        self._setup_mc_alias()

        # Cache for version data
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_etag: Optional[str] = None

    def _setup_mc_alias(self):
        """Set up mc alias for S3 endpoint."""
        insecure_flag = "--insecure" if self.skip_ssl else ""
        cmd = f"mc alias set {self.alias} {self.endpoint_url} {self.access_key} {self.secret_key} {insecure_flag}"

        logger.debug(f"Setting up mc alias: {self.alias}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Failed to setup mc alias: {result.stderr}")

    def _cleanup_mc_alias(self):
        """Clean up mc alias."""
        try:
            subprocess.run(f"mc alias rm {self.alias}", shell=True, capture_output=True)
        except Exception:
            pass  # Ignore cleanup errors

    def __del__(self):
        """Clean up mc alias when object is destroyed."""
        self._cleanup_mc_alias()

    def _run_mc_command(self, cmd: str, check: bool = True) -> subprocess.CompletedProcess:
        """Run an mc command and return the result."""
        logger.debug(f"Running mc command: {cmd}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if check and result.returncode != 0:
            logger.error(f"MC command failed: {result.stderr}")
            raise RuntimeError(f"MC command failed: {result.stderr}")

        return result

    def load_versions(self) -> Dict[str, Any]:
        """
        Load version data from S3 using mc.

        Returns:
            Dictionary containing version data
        """
        try:
            # Try to download the version file
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as temp_file:
                temp_path = temp_file.name

            insecure_flag = "--insecure" if self.skip_ssl else ""
            s3_path = f"{self.alias}/{self.bucket}/{self.versions_key}"
            cmd = f"mc cp {insecure_flag} '{s3_path}' '{temp_path}'"

            result = self._run_mc_command(cmd, check=False)

            if result.returncode != 0:
                # File doesn't exist, return empty structure
                logger.info("Version database not found in S3, creating new one")
                return self._create_empty_database()

            # Read the downloaded file
            try:
                with open(temp_path, 'r') as f:
                    data = json.load(f)

                # Validate structure
                if not isinstance(data, dict) or 'versions' not in data:
                    logger.warning("Invalid version data structure, creating new database")
                    return self._create_empty_database()

                self._cache = data
                logger.info(f"Loaded {len(data.get('versions', {}))} versions from S3")
                return data

            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error loading versions from S3: {e}")
            logger.info("Creating new version database")
            return self._create_empty_database()

    def _create_empty_database(self) -> Dict[str, Any]:
        """Create an empty version database structure."""
        return {
            'versions': {},
            'metadata': {
                'version': '2.0',
                'created': datetime.now(timezone.utc).isoformat(),
                'last_updated': datetime.now(timezone.utc).isoformat(),
                'storage_backend': 'S3-mc'
            }
        }

    def save_versions(self, data: Dict[str, Any]) -> bool:
        """
        Save version data to S3 using mc.

        Args:
            data: Version data dictionary to save

        Returns:
            True if save was successful, False otherwise
        """
        try:
            # Update metadata
            if 'metadata' not in data:
                data['metadata'] = {}

            data['metadata']['last_updated'] = datetime.now(timezone.utc).isoformat()
            data['metadata']['storage_backend'] = 'S3-mc'
            data['metadata']['version'] = '2.0'

            # Write to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                json.dump(data, temp_file, indent=2, sort_keys=True)
                temp_path = temp_file.name

            try:
                # Upload using mc
                insecure_flag = "--insecure" if self.skip_ssl else ""
                s3_path = f"{self.alias}/{self.bucket}/{self.versions_key}"
                cmd = f"mc cp {insecure_flag} '{temp_path}' '{s3_path}'"

                self._run_mc_command(cmd)

                # Update cache
                self._cache = data

                logger.info("Saved version data to S3 using mc")
                return True

            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error saving to S3 using mc: {e}")
            return False

    def get_version(self, repo: str) -> Optional[str]:
        """
        Get the current version for a repository.

        Args:
            repo: Repository name in format 'owner/repo'

        Returns:
            Current version string or None if not found
        """
        if self._cache is None:
            self._cache = self.load_versions()

        return self._cache.get('versions', {}).get(repo)

    def set_version(self, repo: str, version: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Set the version for a repository.

        Args:
            repo: Repository name in format 'owner/repo'
            version: Version string to set
            metadata: Optional metadata to store with the version

        Returns:
            True if successful, False otherwise
        """
        if self._cache is None:
            self._cache = self.load_versions()

        if 'versions' not in self._cache:
            self._cache['versions'] = {}

        # Store version with metadata
        version_data = {
            'version': version,
            'updated': datetime.now(timezone.utc).isoformat()
        }

        if metadata:
            version_data['metadata'] = metadata

        self._cache['versions'][repo] = version_data

        return self.save_versions(self._cache)

    def list_repos(self) -> List[str]:
        """
        List all repositories being tracked.

        Returns:
            List of repository names
        """
        if self._cache is None:
            self._cache = self.load_versions()

        return list(self._cache.get('versions', {}).keys())

    def get_all_versions(self) -> Dict[str, str]:
        """
        Get all repository versions.

        Returns:
            Dictionary mapping repo names to version strings
        """
        if self._cache is None:
            self._cache = self.load_versions()

        versions = {}
        for repo, data in self._cache.get('versions', {}).items():
            if isinstance(data, dict):
                versions[repo] = data.get('version', '')
            else:
                # Handle legacy format
                versions[repo] = str(data)

        return versions

    def get_current_version(self, owner: str, repo: str) -> Optional[str]:
        """
        Get the current version for a repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Current version string or None if not found
        """
        if self._cache is None:
            self._cache = self.load_versions()

        repo_key = f"{owner}/{repo}"
        repo_data = self._cache.get('repositories', {}).get(repo_key, {})
        return repo_data.get('current_version')

    def update_version(self, owner: str, repo: str, version: str,
                      metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update the version for a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            version: New version string
            metadata: Optional metadata to store with the version

        Returns:
            True if successful, False otherwise
        """
        if self._cache is None:
            self._cache = self.load_versions()

        if 'repositories' not in self._cache:
            self._cache['repositories'] = {}

        repo_key = f"{owner}/{repo}"

        # Update repository data
        repo_data = {
            'current_version': version,
            'last_updated': datetime.now(timezone.utc).isoformat()
        }

        if metadata:
            repo_data['metadata'] = metadata

        self._cache['repositories'][repo_key] = repo_data

        return self.save_versions(self._cache)

    def get_download_history(self, owner: str, repo: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get download history for a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            limit: Maximum number of history entries to return

        Returns:
            List of download history entries
        """
        if self._cache is None:
            self._cache = self.load_versions()

        repo_key = f"{owner}/{repo}"
        repo_data = self._cache.get('repositories', {}).get(repo_key, {})
        history = repo_data.get('download_history', [])

        return history[-limit:] if limit > 0 else history

    def add_download_record(self, owner: str, repo: str, version: str,
                           assets: List[Dict[str, Any]],
                           metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add a download record to the history.

        Args:
            owner: Repository owner
            repo: Repository name
            version: Version that was downloaded
            assets: List of assets that were downloaded
            metadata: Optional metadata

        Returns:
            True if successful, False otherwise
        """
        if self._cache is None:
            self._cache = self.load_versions()

        if 'repositories' not in self._cache:
            self._cache['repositories'] = {}

        repo_key = f"{owner}/{repo}"

        if repo_key not in self._cache['repositories']:
            self._cache['repositories'][repo_key] = {}

        if 'download_history' not in self._cache['repositories'][repo_key]:
            self._cache['repositories'][repo_key]['download_history'] = []

        # Create download record
        record = {
            'version': version,
            'downloaded_at': datetime.now(timezone.utc).isoformat(),
            'assets': assets
        }

        if metadata:
            record['metadata'] = metadata

        self._cache['repositories'][repo_key]['download_history'].append(record)

        return self.save_versions(self._cache)

    def export_to_file(self, file_path: str) -> bool:
        """
        Export version data to a local file.

        Args:
            file_path: Path to export file

        Returns:
            True if successful, False otherwise
        """
        try:
            if self._cache is None:
                self._cache = self.load_versions()

            with open(file_path, 'w') as f:
                json.dump(self._cache, f, indent=2, sort_keys=True)

            logger.info(f"Exported version data to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error exporting to file: {e}")
            return False

    def import_from_file(self, file_path: str, merge: bool = False) -> bool:
        """
        Import version data from a local file.

        Args:
            file_path: Path to import file
            merge: Whether to merge with existing data

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(file_path, 'r') as f:
                file_data = json.load(f)

            if merge and self._cache is not None:
                # Merge repositories
                if 'repositories' in file_data:
                    if 'repositories' not in self._cache:
                        self._cache['repositories'] = {}
                    self._cache['repositories'].update(file_data['repositories'])
            else:
                self._cache = file_data

            success = self.save_versions(self._cache)
            if success:
                logger.info(f"Imported version data from {file_path}")

            return success

        except Exception as e:
            logger.error(f"Error importing from file: {e}")
            return False

    def test_connection(self) -> bool:
        """
        Test the S3 connection.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try to list the bucket contents
            insecure_flag = "--insecure" if self.skip_ssl else ""
            cmd = f"mc ls {insecure_flag} {self.alias}/{self.bucket}/ --limit 1"
            self._run_mc_command(cmd)
            return True

        except Exception as e:
            logger.error(f"S3 connection test failed: {e}")
            return False

    def clear_cache(self):
        """Clear the local cache, forcing a reload on next access."""
        self._cache = None
        self._cache_etag = None


class S3VersionDatabase:
    """
    Compatibility wrapper that automatically chooses between boto3 and mc implementations.
    """

    def __init__(self, bucket: str, key_prefix: str = 'release-monitor/',
                 region: Optional[str] = None, profile: Optional[str] = None):
        """
        Initialize S3 version database with automatic implementation selection.

        Args:
            bucket: S3 bucket name
            key_prefix: Prefix for all version keys in S3
            region: AWS region (optional, ignored for mc implementation)
            profile: AWS profile name (optional, ignored for mc implementation)
        """
        # Check if we should use mc implementation
        use_mc = os.environ.get('S3_USE_MC', 'true').lower() == 'true'

        if use_mc:
            logger.info("Using MinIO client (mc) for S3 operations")
            self._impl = S3VersionStorageMC(bucket, key_prefix)
        else:
            logger.info("Using boto3 for S3 operations")
            # Import the original implementation
            from github_version_s3 import S3VersionStorage
            self._impl = S3VersionStorage(bucket, key_prefix, region, profile)

    def __getattr__(self, name):
        """Delegate all method calls to the underlying implementation."""
        return getattr(self._impl, name)
