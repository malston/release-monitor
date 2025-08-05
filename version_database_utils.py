#!/usr/bin/env python3
"""
Unified version database utilities for GitHub Release Monitor.

Provides auto-detection and initialization of version databases across
multiple storage backends: Artifactory, S3/MinIO, and local file.
"""

import os
import sys
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


def get_version_database(verbose: bool = False) -> Optional[Any]:
    """
    Get version database instance based on environment configuration.
    Auto-detects the appropriate storage backend.

    Returns:
        Version database instance or None if unavailable/disabled
    """
    # Check if version database is disabled
    if os.getenv('DISABLE_VERSION_DB', '').lower() == 'true':
        if verbose:
            print("Version database disabled via DISABLE_VERSION_DB")
        return None

    # Priority order: Artifactory -> S3 -> Local

    # Try Artifactory first
    if os.environ.get('ARTIFACTORY_URL') and os.environ.get('ARTIFACTORY_REPOSITORY'):
        version_db = _get_artifactory_version_db(verbose)
        if version_db:
            return version_db

    # Try S3/MinIO
    if os.environ.get('VERSION_DB_S3_BUCKET') or os.environ.get('USE_S3_VERSION_DB', '').lower() == 'true':
        version_db = _get_s3_version_db(verbose)
        if version_db:
            return version_db

    # Try local file
    version_db = _get_local_version_db(verbose)
    if version_db:
        return version_db

    if verbose:
        print("No version database backend configured or available")
    return None


def _get_artifactory_version_db(verbose: bool = False) -> Optional[Any]:
    """Initialize Artifactory version database."""
    try:
        from github_version_artifactory import ArtifactoryVersionStorage

        url = os.environ.get('ARTIFACTORY_URL')
        repository = os.environ.get('ARTIFACTORY_REPOSITORY')
        path_prefix = os.environ.get('ARTIFACTORY_PATH_PREFIX', 'release-monitor/')

        if not url or not repository:
            if verbose:
                print("Artifactory URL or repository not configured")
            return None

        # Authentication - prefer API key
        api_key = os.environ.get('ARTIFACTORY_API_KEY')
        username = os.environ.get('ARTIFACTORY_USERNAME')
        password = os.environ.get('ARTIFACTORY_PASSWORD')

        if not api_key and not (username and password):
            if verbose:
                print("Artifactory authentication not configured")
            return None

        if verbose:
            print(f"Initializing Artifactory version database at {url}/{repository}")

        version_db = ArtifactoryVersionStorage(
            base_url=url,
            repository=repository,
            path_prefix=path_prefix,
            api_key=api_key,
            username=username,
            password=password
        )

        if verbose:
            print("Successfully initialized Artifactory version database")
        return version_db

    except ImportError as e:
        if verbose:
            print(f"Artifactory version module not available: {e}")
        return None
    except Exception as e:
        if verbose:
            print(f"Failed to initialize Artifactory version database: {e}")
        return None


def _get_s3_version_db(verbose: bool = False) -> Optional[Any]:
    """Initialize S3/MinIO version database."""
    try:
        # Check if we should use MinIO client
        use_mc = os.getenv('S3_USE_MC', '').lower() == 'true'

        if use_mc:
            # Check if mc command is available before trying to use it
            try:
                import subprocess
                mc_check = subprocess.run(['which', 'mc'], capture_output=True, text=True)
                if mc_check.returncode != 0:
                    if verbose:
                        print("MinIO client (mc) not found in PATH, falling back to boto3")
                    use_mc = False
            except Exception:
                use_mc = False

        # Import appropriate module
        if use_mc:
            try:
                from github_version_s3_mc import S3VersionStorageMC as S3VersionDatabase
                if verbose:
                    print("Using MinIO client for S3 version database")
            except (ImportError, Exception) as e:
                if verbose:
                    print(f"MinIO client module error ({e}), falling back to boto3")
                use_mc = False

        if not use_mc:
            from github_version_s3 import S3VersionStorage as S3VersionDatabase
            if verbose:
                print("Using boto3 for S3 version database")

        # Get S3 configuration
        bucket = os.getenv('VERSION_DB_S3_BUCKET', os.getenv('S3_BUCKET'))
        prefix = os.getenv('VERSION_DB_S3_PREFIX', 'release-monitor/')

        if not bucket:
            if verbose:
                print("No S3 bucket configured for version database")
            return None

        # Initialize version database
        try:
            version_db = S3VersionDatabase(bucket=bucket, key_prefix=prefix)
            if verbose:
                print(f"Initialized S3 version database with bucket: {bucket}, prefix: {prefix}")
            return version_db
        except Exception as init_error:
            if verbose:
                print(f"Failed to initialize S3 version database: {init_error}")

            # If mc initialization failed, try boto3 as fallback
            if use_mc:
                if verbose:
                    print("Attempting fallback to boto3...")
                try:
                    from github_version_s3 import S3VersionStorage as S3VersionDatabase
                    version_db = S3VersionDatabase(bucket=bucket, key_prefix=prefix)
                    if verbose:
                        print("Successfully initialized boto3 version database as fallback")
                    return version_db
                except Exception as fallback_error:
                    if verbose:
                        print(f"Fallback to boto3 also failed: {fallback_error}")

            return None

    except ImportError as e:
        if verbose:
            print(f"S3 version modules not available: {e}")
        return None
    except Exception as e:
        if verbose:
            print(f"Failed to initialize S3 version database: {e}")
        return None


def _get_local_version_db(verbose: bool = False) -> Optional[Any]:
    """Initialize local file version database."""
    try:
        from github_version import VersionDatabase

        # Check common locations for version database
        possible_paths = [
            os.environ.get('VERSION_DB_PATH'),
            os.environ.get('DOWNLOAD_DIR', '.') + '/version_db.json',
            './downloads/version_db.json',
            './version_db.json'
        ]

        version_db_path = None
        for path in possible_paths:
            if path:
                # For local version DB, we'll create it if it doesn't exist
                version_db_path = path
                break

        if not version_db_path:
            version_db_path = './version_db.json'  # Default fallback

        if verbose:
            print(f"Initializing local version database at: {version_db_path}")

        version_db = VersionDatabase(version_db_path)

        if verbose:
            print("Successfully initialized local version database")
        return version_db

    except ImportError as e:
        if verbose:
            print(f"Local version module not available: {e}")
        return None
    except Exception as e:
        if verbose:
            print(f"Failed to initialize local version database: {e}")
        return None


# Alias for backward compatibility
def get_s3_version_database():
    """Backward compatibility wrapper that only tries S3."""
    return _get_s3_version_db(verbose=True)
