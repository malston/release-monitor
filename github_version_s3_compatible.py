#!/usr/bin/env python3
"""
S3-Compatible Version Storage for GitHub Release Monitor

This module provides version storage using S3-compatible APIs,
supporting both AWS S3 and alternatives like Minio.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.client import Config
import warnings
import urllib3

logger = logging.getLogger(__name__)


class S3CompatibleVersionStorage:
    """
    Version storage implementation using S3-compatible object storage.
    Supports AWS S3, Minio, and other S3-compatible services.
    """

    def __init__(self,
                 bucket: str,
                 key_prefix: str = 'release-monitor/',
                 region: Optional[str] = None,
                 profile: Optional[str] = None,
                 endpoint_url: Optional[str] = None,
                 access_key: Optional[str] = None,
                 secret_key: Optional[str] = None,
                 use_ssl: bool = True,
                 verify_ssl: bool = True):
        """
        Initialize S3-compatible version storage.

        Args:
            bucket: S3 bucket name
            key_prefix: Prefix for all keys in the bucket
            region: AWS region (optional, defaults to us-east-1 for Minio)
            profile: AWS profile name (optional)
            endpoint_url: S3-compatible endpoint URL (e.g., http://localhost:9000 for Minio)
            access_key: Access key ID (optional, uses environment/profile if not provided)
            secret_key: Secret access key (optional, uses environment/profile if not provided)
            use_ssl: Whether to use SSL (ignored if endpoint_url has protocol)
            verify_ssl: Whether to verify SSL certificates
        """
        self.bucket = bucket
        self.key_prefix = key_prefix.rstrip('/') + '/'
        self.endpoint_url = endpoint_url

        # Configure boto3 client
        client_config = Config(
            signature_version='s3v4',  # Required for Minio
            s3={'addressing_style': 'path'}  # Use path-style addressing for compatibility
        )

        # Configure SSL verification
        if not verify_ssl:
            logger.warning("SSL verification disabled for S3 connection")
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Build client arguments
        client_args = {
            'service_name': 's3',
            'config': client_config
        }
        
        # Add verify parameter if SSL verification is disabled
        if not verify_ssl:
            client_args['verify'] = False

        # Add endpoint URL if provided
        if endpoint_url:
            client_args['endpoint_url'] = endpoint_url
            logger.info(f"Using S3-compatible endpoint: {endpoint_url}")

        # Add region
        if region:
            client_args['region_name'] = region
        elif endpoint_url:  # Default region for S3-compatible services
            client_args['region_name'] = 'us-east-1'

        # Add credentials if provided
        if access_key and secret_key:
            client_args['aws_access_key_id'] = access_key
            client_args['aws_secret_access_key'] = secret_key
        elif profile:
            # Use boto3 session with profile
            session = boto3.Session(profile_name=profile)
            self.s3_client = session.client(**client_args)
        else:
            # Use default credentials chain
            self.s3_client = boto3.client(**client_args)

        # If we haven't created client yet (not using profile)
        if not hasattr(self, 's3_client'):
            self.s3_client = boto3.client(**client_args)

        # Verify bucket access
        self._verify_bucket_access()

    def _verify_bucket_access(self):
        """Verify we can access the bucket."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket)
            logger.info(f"Successfully verified access to bucket: {self.bucket}")
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                logger.error(f"Bucket does not exist: {self.bucket}")
                raise ValueError(f"Bucket not found: {self.bucket}")
            elif error_code == 403:
                logger.error(f"Access denied to bucket: {self.bucket}")
                raise PermissionError(f"Access denied to bucket: {self.bucket}")
            else:
                logger.error(f"Error accessing bucket: {e}")
                raise
        except NoCredentialsError:
            logger.error("No credentials found for S3 access")
            raise

    def _get_version_key(self, repo_key: str) -> str:
        """Get the S3 key for a repository's version info."""
        return f"{self.key_prefix}versions/{repo_key}.json"

    def _get_metadata_key(self) -> str:
        """Get the S3 key for storage metadata."""
        return f"{self.key_prefix}metadata.json"

    def load_database(self) -> Dict[str, Any]:
        """
        Load the entire version database from S3.

        Returns:
            Dictionary containing all version information
        """
        database = {
            'versions': {},
            'metadata': {
                'last_updated': None,
                'storage_type': 's3-compatible',
                'endpoint': self.endpoint_url or 'aws-s3'
            }
        }

        # Load metadata
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key=self._get_metadata_key()
            )
            metadata = json.loads(response['Body'].read())
            database['metadata'].update(metadata)
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchKey':
                logger.error(f"Error loading metadata: {e}")

        # List all version files
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            prefix = f"{self.key_prefix}versions/"

            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    key = obj['Key']
                    if key.endswith('.json'):
                        # Extract repository key from S3 key
                        repo_key = key[len(prefix):-5]  # Remove prefix and .json

                        try:
                            response = self.s3_client.get_object(
                                Bucket=self.bucket,
                                Key=key
                            )
                            version_data = json.loads(response['Body'].read())
                            database['versions'][repo_key] = version_data
                        except Exception as e:
                            logger.error(f"Error loading version data for {repo_key}: {e}")

        except ClientError as e:
            logger.error(f"Error listing version files: {e}")

        return database

    def save_database(self, database: Dict[str, Any]):
        """
        Save the entire version database to S3.

        Args:
            database: Complete database dictionary
        """
        # Update metadata
        metadata = database.get('metadata', {})
        metadata['last_updated'] = datetime.now(timezone.utc).isoformat()
        metadata['storage_type'] = 's3-compatible'
        metadata['endpoint'] = self.endpoint_url or 'aws-s3'

        # Save metadata
        try:
            json_bytes = json.dumps(metadata, indent=2).encode('utf-8')
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=self._get_metadata_key(),
                Body=json_bytes,
                ContentType='application/json',
                ContentLength=len(json_bytes)
            )
        except ClientError as e:
            logger.error(f"Error saving metadata: {e}")
            raise

        # Save each repository's version data
        versions = database.get('versions', {})
        for repo_key, version_data in versions.items():
            try:
                json_bytes = json.dumps(version_data, indent=2).encode('utf-8')
                self.s3_client.put_object(
                    Bucket=self.bucket,
                    Key=self._get_version_key(repo_key),
                    Body=json_bytes,
                    ContentType='application/json',
                    ContentLength=len(json_bytes)
                )
            except ClientError as e:
                logger.error(f"Error saving version data for {repo_key}: {e}")
                raise

    def get_stored_version(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """
        Get stored version information for a repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Version information or None if not found
        """
        repo_key = f"{owner}_{repo}"

        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key=self._get_version_key(repo_key)
            )
            return json.loads(response['Body'].read())
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return None
            logger.error(f"Error getting version for {repo_key}: {e}")
            raise

    def update_version(self, owner: str, repo: str, version_info: Dict[str, Any]):
        """
        Update version information for a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            version_info: Version information to store
        """
        repo_key = f"{owner}_{repo}"

        # Add timestamp
        version_info['last_updated'] = datetime.now(timezone.utc).isoformat()

        try:
            json_bytes = json.dumps(version_info, indent=2).encode('utf-8')
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=self._get_version_key(repo_key),
                Body=json_bytes,
                ContentType='application/json',
                ContentLength=len(json_bytes)
            )

            # Update metadata to reflect change
            self._update_metadata()

        except ClientError as e:
            logger.error(f"Error updating version for {repo_key}: {e}")
            raise

    def _update_metadata(self):
        """Update storage metadata."""
        metadata = {
            'last_updated': datetime.now(timezone.utc).isoformat(),
            'storage_type': 's3-compatible',
            'endpoint': self.endpoint_url or 'aws-s3',
            'bucket': self.bucket,
            'key_prefix': self.key_prefix
        }

        try:
            json_bytes = json.dumps(metadata, indent=2).encode('utf-8')
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=self._get_metadata_key(),
                Body=json_bytes,
                ContentType='application/json',
                ContentLength=len(json_bytes)
            )
        except ClientError as e:
            logger.error(f"Error updating metadata: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the version storage.

        Returns:
            Dictionary with storage statistics
        """
        stats = {
            'total_repositories': 0,
            'storage_type': 's3-compatible',
            'endpoint': self.endpoint_url or 'aws-s3',
            'bucket': self.bucket,
            'last_updated': None
        }

        # Get metadata
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key=self._get_metadata_key()
            )
            metadata = json.loads(response['Body'].read())
            stats['last_updated'] = metadata.get('last_updated')
        except ClientError:
            pass

        # Count repositories
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            prefix = f"{self.key_prefix}versions/"

            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                if 'Contents' in page:
                    stats['total_repositories'] = len([
                        obj for obj in page['Contents']
                        if obj['Key'].endswith('.json')
                    ])
        except ClientError as e:
            logger.error(f"Error getting statistics: {e}")

        return stats


# Compatibility wrapper for existing code
class S3VersionStorage(S3CompatibleVersionStorage):
    """Alias for backward compatibility."""
    pass


def create_from_environment() -> S3CompatibleVersionStorage:
    """
    Create S3CompatibleVersionStorage from environment variables.

    Environment variables:
        - S3_ENDPOINT: S3-compatible endpoint URL (optional)
        - VERSION_DB_S3_BUCKET or S3_BUCKET: Bucket name
        - VERSION_DB_S3_PREFIX or S3_PREFIX: Key prefix (optional)
        - VERSION_DB_S3_REGION or AWS_REGION: AWS region (optional)
        - AWS_ACCESS_KEY_ID: Access key (optional)
        - AWS_SECRET_ACCESS_KEY: Secret key (optional)
        - S3_USE_SSL: Whether to use SSL (optional, default: true)
        - S3_VERIFY_SSL: Whether to verify SSL (optional, default: true)
    """
    bucket = os.environ.get('VERSION_DB_S3_BUCKET') or os.environ.get('S3_BUCKET')
    if not bucket:
        raise ValueError("VERSION_DB_S3_BUCKET or S3_BUCKET environment variable required")

    return S3CompatibleVersionStorage(
        bucket=bucket,
        key_prefix=os.environ.get('VERSION_DB_S3_PREFIX', 'release-monitor/'),
        region=os.environ.get('VERSION_DB_S3_REGION') or os.environ.get('AWS_REGION'),
        endpoint_url=os.environ.get('S3_ENDPOINT'),
        access_key=os.environ.get('AWS_ACCESS_KEY_ID'),
        secret_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        use_ssl=os.environ.get('S3_USE_SSL', 'true').lower() == 'true',
        verify_ssl=os.environ.get('S3_SKIP_SSL_VERIFICATION', 'false').lower() != 'true'
    )
