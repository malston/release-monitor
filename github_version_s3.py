#!/usr/bin/env python3
"""
S3-based Version Storage for GitHub Release Monitor

Stores version information in S3 instead of local file system,
enabling cloud-native deployments and shared state across multiple instances.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class S3VersionStorage:
    """
    S3-based version storage for tracking downloaded GitHub releases.
    
    Provides the same interface as VersionDatabase but uses S3 for storage.
    """
    
    def __init__(self, bucket: str, key_prefix: str = 'release-monitor/', 
                 region: Optional[str] = None, profile: Optional[str] = None):
        """
        Initialize S3 version storage.
        
        Args:
            bucket: S3 bucket name
            key_prefix: Prefix for all version keys in S3
            region: AWS region (optional, uses default if not specified)
            profile: AWS profile name (optional)
        """
        self.bucket = bucket
        self.key_prefix = key_prefix.rstrip('/') + '/'
        self.versions_key = f"{self.key_prefix}version_db.json"
        
        # Initialize S3 client
        session_kwargs = {}
        if profile:
            session_kwargs['profile_name'] = profile
            
        session = boto3.Session(**session_kwargs)
        
        client_kwargs = {}
        if region:
            client_kwargs['region_name'] = region
            
        self.s3_client = session.client('s3', **client_kwargs)
        
        # Initialize local cache
        self._cache = None
        self._cache_etag = None
        
        logger.info(f"S3 version storage initialized: s3://{bucket}/{self.versions_key}")
    
    def _load_from_s3(self) -> Dict[str, Any]:
        """Load version data from S3."""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key=self.versions_key
            )
            
            # Check if we can use cached version
            etag = response.get('ETag', '').strip('"')
            if self._cache is not None and self._cache_etag == etag:
                logger.debug("Using cached version data")
                return self._cache
            
            # Load and parse JSON
            content = response['Body'].read().decode('utf-8')
            data = json.loads(content)
            
            # Update cache
            self._cache = data
            self._cache_etag = etag
            
            logger.debug(f"Loaded version data from S3 (ETag: {etag})")
            return data
            
        except self.s3_client.exceptions.NoSuchKey:
            # File doesn't exist yet, return empty structure
            logger.info("Version database not found in S3, creating new one")
            return {"repositories": {}, "metadata": {"created_at": datetime.now(timezone.utc).isoformat()}}
        except ClientError as e:
            logger.error(f"Error loading from S3: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in S3 version database: {e}")
            raise
    
    def _save_to_s3(self, data: Dict[str, Any]) -> bool:
        """Save version data to S3."""
        try:
            # Add metadata
            data['metadata']['last_updated'] = datetime.now(timezone.utc).isoformat()
            data['metadata']['version'] = '2.0'  # S3-based version
            
            # Convert to JSON
            json_content = json.dumps(data, indent=2, sort_keys=True)
            
            # Upload to S3
            response = self.s3_client.put_object(
                Bucket=self.bucket,
                Key=self.versions_key,
                Body=json_content.encode('utf-8'),
                ContentType='application/json',
                Metadata={
                    'purpose': 'github-release-monitor-versions',
                    'format': 'json'
                }
            )
            
            # Update cache
            self._cache = data
            self._cache_etag = response.get('ETag', '').strip('"')
            
            logger.info(f"Saved version data to S3 (ETag: {self._cache_etag})")
            return True
            
        except ClientError as e:
            logger.error(f"Error saving to S3: {e}")
            raise
    
    def get_current_version(self, owner: str, repo: str) -> Optional[str]:
        """
        Get the current version for a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Current version string or None if not found
        """
        data = self._load_from_s3()
        repo_key = f"{owner}/{repo}"
        
        repo_data = data.get('repositories', {}).get(repo_key, {})
        return repo_data.get('current_version')
    
    def update_version(self, owner: str, repo: str, version: str, 
                      metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update the version for a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            version: New version string
            metadata: Optional metadata about the version
            
        Returns:
            True if successful
        """
        data = self._load_from_s3()
        repo_key = f"{owner}/{repo}"
        
        # Ensure structure exists
        if 'repositories' not in data:
            data['repositories'] = {}
        if repo_key not in data['repositories']:
            data['repositories'][repo_key] = {
                'created_at': datetime.now(timezone.utc).isoformat()
            }
        
        # Update repository data
        repo_data = data['repositories'][repo_key]
        old_version = repo_data.get('current_version')
        
        repo_data['current_version'] = version
        repo_data['last_updated'] = datetime.now(timezone.utc).isoformat()
        
        # Add to version history
        if 'version_history' not in repo_data:
            repo_data['version_history'] = []
        
        history_entry = {
            'version': version,
            'previous_version': old_version,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        if metadata:
            history_entry['metadata'] = metadata
        
        repo_data['version_history'].append(history_entry)
        
        # Keep only last 10 history entries
        if len(repo_data['version_history']) > 10:
            repo_data['version_history'] = repo_data['version_history'][-10:]
        
        # Save back to S3
        success = self._save_to_s3(data)
        
        if success:
            logger.info(f"Updated {owner}/{repo}: {old_version} → {version}")
        
        return success
    
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
        data = self._load_from_s3()
        repo_key = f"{owner}/{repo}"
        
        repo_data = data.get('repositories', {}).get(repo_key, {})
        history = repo_data.get('version_history', [])
        
        # Return most recent entries first
        return list(reversed(history[-limit:]))
    
    def get_all_versions(self) -> Dict[str, str]:
        """
        Get all current versions.
        
        Returns:
            Dictionary mapping repository to current version
        """
        data = self._load_from_s3()
        versions = {}
        
        for repo_key, repo_data in data.get('repositories', {}).items():
            if 'current_version' in repo_data:
                versions[repo_key] = repo_data['current_version']
        
        return versions
    
    def add_download_record(self, owner: str, repo: str, version: str, 
                           assets: List[str], metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add a download record for tracking.
        
        Args:
            owner: Repository owner
            repo: Repository name
            version: Version that was downloaded
            assets: List of asset names that were downloaded
            metadata: Optional metadata about the download
            
        Returns:
            True if successful
        """
        data = self._load_from_s3()
        repo_key = f"{owner}/{repo}"
        
        # Ensure structure exists
        if 'repositories' not in data:
            data['repositories'] = {}
        if repo_key not in data['repositories']:
            data['repositories'][repo_key] = {}
        
        repo_data = data['repositories'][repo_key]
        
        # Add to download history
        if 'download_history' not in repo_data:
            repo_data['download_history'] = []
        
        download_entry = {
            'version': version,
            'downloaded_at': datetime.now(timezone.utc).isoformat(),
            'assets': assets,
            'asset_count': len(assets)
        }
        
        if metadata:
            download_entry['metadata'] = metadata
        
        repo_data['download_history'].append(download_entry)
        
        # Keep only last 50 download entries
        if len(repo_data['download_history']) > 50:
            repo_data['download_history'] = repo_data['download_history'][-50:]
        
        # Update download statistics
        if 'statistics' not in repo_data:
            repo_data['statistics'] = {}
        
        stats = repo_data['statistics']
        stats['total_downloads'] = stats.get('total_downloads', 0) + 1
        stats['total_assets_downloaded'] = stats.get('total_assets_downloaded', 0) + len(assets)
        stats['last_download'] = datetime.now(timezone.utc).isoformat()
        
        # Save back to S3
        return self._save_to_s3(data)
    
    def export_to_file(self, file_path: str) -> bool:
        """
        Export version database to a local file.
        
        Args:
            file_path: Path to export file
            
        Returns:
            True if successful
        """
        try:
            data = self._load_from_s3()
            
            # Ensure directory exists
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Exported version database to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to file: {e}")
            return False
    
    def import_from_file(self, file_path: str, merge: bool = False) -> bool:
        """
        Import version database from a local file.
        
        Args:
            file_path: Path to import file
            merge: If True, merge with existing data; if False, replace
            
        Returns:
            True if successful
        """
        try:
            with open(file_path, 'r') as f:
                import_data = json.load(f)
            
            if merge:
                # Load existing data and merge
                existing_data = self._load_from_s3()
                
                # Merge repositories
                for repo_key, repo_data in import_data.get('repositories', {}).items():
                    if repo_key not in existing_data.get('repositories', {}):
                        existing_data.setdefault('repositories', {})[repo_key] = repo_data
                    else:
                        # Merge carefully, keeping newer data
                        existing_repo = existing_data['repositories'][repo_key]
                        
                        # Update version if import is newer
                        import_updated = repo_data.get('last_updated', '')
                        existing_updated = existing_repo.get('last_updated', '')
                        
                        if import_updated > existing_updated:
                            existing_repo['current_version'] = repo_data.get('current_version')
                            existing_repo['last_updated'] = import_updated
                
                data = existing_data
            else:
                # Replace entirely
                data = import_data
            
            # Save to S3
            success = self._save_to_s3(data)
            
            if success:
                logger.info(f"Imported version database from {file_path} (merge={merge})")
            
            return success
            
        except Exception as e:
            logger.error(f"Error importing from file: {e}")
            return False
    
    def clear_cache(self):
        """Clear the local cache to force reload from S3."""
        self._cache = None
        self._cache_etag = None
        logger.debug("Cleared local cache")
    
    def test_connection(self) -> bool:
        """
        Test S3 connection and permissions.
        
        Returns:
            True if connection is successful and bucket is accessible
        """
        try:
            # Try to read the bucket
            self.s3_client.head_bucket(Bucket=self.bucket)
            
            # Try to read our key (might not exist)
            try:
                self.s3_client.head_object(Bucket=self.bucket, Key=self.versions_key)
                logger.info("S3 connection test successful - version database exists")
            except self.s3_client.exceptions.NoSuchKey:
                logger.info("S3 connection test successful - version database will be created")
            
            return True
            
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            return False
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"S3 bucket '{self.bucket}' not found")
            else:
                logger.error(f"S3 connection test failed: {e}")
            return False


# Compatibility wrapper to use S3 storage with existing code
class VersionDatabase(S3VersionStorage):
    """
    Compatibility wrapper that provides VersionDatabase interface using S3 storage.
    
    This allows existing code to work with S3 storage without modification.
    """
    
    def __init__(self, db_path: str = 'version_db.json', use_s3: bool = True,
                 s3_bucket: Optional[str] = None, s3_prefix: Optional[str] = None,
                 aws_region: Optional[str] = None, aws_profile: Optional[str] = None):
        """
        Initialize version database with S3 or local file storage.
        
        Args:
            db_path: Local file path (used only if use_s3=False)
            use_s3: Whether to use S3 storage (default: True)
            s3_bucket: S3 bucket name (required if use_s3=True)
            s3_prefix: S3 key prefix (default: 'release-monitor/')
            aws_region: AWS region
            aws_profile: AWS profile name
        """
        if use_s3:
            if not s3_bucket:
                # Try to get from environment
                s3_bucket = os.environ.get('VERSION_DB_S3_BUCKET')
                if not s3_bucket:
                    raise ValueError("S3 bucket must be specified when use_s3=True")
            
            s3_prefix = s3_prefix or os.environ.get('VERSION_DB_S3_PREFIX', 'release-monitor/')
            
            super().__init__(
                bucket=s3_bucket,
                key_prefix=s3_prefix,
                region=aws_region,
                profile=aws_profile
            )
            
            self.db_path = f"s3://{s3_bucket}/{s3_prefix}version_db.json"
            self.use_s3 = True
        else:
            # Fall back to local file storage (original implementation)
            from github_version_db import VersionDatabase as LocalVersionDatabase
            self._local_db = LocalVersionDatabase(db_path)
            self.db_path = db_path
            self.use_s3 = False
    
    def __getattribute__(self, name):
        """Delegate to local database if not using S3."""
        if object.__getattribute__(self, 'use_s3') is False and hasattr(object.__getattribute__(self, '_local_db'), name):
            return getattr(object.__getattribute__(self, '_local_db'), name)
        return object.__getattribute__(self, name)


if __name__ == '__main__':
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='S3 Version Storage Testing')
    parser.add_argument('--bucket', required=True, help='S3 bucket name')
    parser.add_argument('--prefix', default='release-monitor/', help='S3 key prefix')
    parser.add_argument('--region', help='AWS region')
    parser.add_argument('--profile', help='AWS profile')
    parser.add_argument('--test', action='store_true', help='Test connection')
    parser.add_argument('--export', help='Export to local file')
    parser.add_argument('--import-file', help='Import from local file')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Create storage instance
    storage = S3VersionStorage(
        bucket=args.bucket,
        key_prefix=args.prefix,
        region=args.region,
        profile=args.profile
    )
    
    if args.test:
        if storage.test_connection():
            print("✓ S3 connection successful")
            
            # Try to read versions
            versions = storage.get_all_versions()
            print(f"\nFound {len(versions)} repositories:")
            for repo, version in versions.items():
                print(f"  {repo}: {version}")
        else:
            print("✗ S3 connection failed")
            exit(1)
    
    if args.export:
        if storage.export_to_file(args.export):
            print(f"✓ Exported to {args.export}")
        else:
            print("✗ Export failed")
            exit(1)
    
    if args.import_file:
        if storage.import_from_file(args.import_file, merge=True):
            print(f"✓ Imported from {args.import_file}")
        else:
            print("✗ Import failed")
            exit(1)