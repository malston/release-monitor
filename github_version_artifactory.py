#!/usr/bin/env python3
"""
JFrog Artifactory-based Version Storage for GitHub Release Monitor

Stores version information in Artifactory instead of local file system or S3,
enabling enterprise deployments with centralized artifact management.
"""

import json
import logging
import os
import base64
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import urljoin, quote

logger = logging.getLogger(__name__)


class ArtifactoryVersionStorage:
    """
    Artifactory-based version storage for tracking downloaded GitHub releases.
    
    Provides the same interface as VersionDatabase but uses Artifactory for storage.
    """
    
    def __init__(self, base_url: str, repository: str, path_prefix: str = 'release-monitor/',
                 username: Optional[str] = None, password: Optional[str] = None,
                 api_key: Optional[str] = None, verify_ssl: bool = True):
        """
        Initialize Artifactory version storage.
        
        Args:
            base_url: Artifactory base URL (e.g., https://artifactory.example.com/artifactory)
            repository: Artifactory repository name
            path_prefix: Path prefix within the repository
            username: Artifactory username (optional if using API key)
            password: Artifactory password (optional if using API key)
            api_key: Artifactory API key (alternative to username/password)
            verify_ssl: Verify SSL certificates
        """
        self.base_url = base_url.rstrip('/')
        self.repository = repository
        self.path_prefix = path_prefix.rstrip('/') + '/'
        self.versions_path = f"{self.path_prefix}version_db.json"
        self.verify_ssl = verify_ssl
        
        # Set up authentication
        self.auth = None
        self.headers = {'Content-Type': 'application/json'}
        
        if api_key:
            self.headers['X-JFrog-Art-Api'] = api_key
        elif username and password:
            self.auth = HTTPBasicAuth(username, password)
        else:
            # Try to get credentials from environment
            env_api_key = os.environ.get('ARTIFACTORY_API_KEY')
            env_username = os.environ.get('ARTIFACTORY_USERNAME')
            env_password = os.environ.get('ARTIFACTORY_PASSWORD')
            
            if env_api_key:
                self.headers['X-JFrog-Art-Api'] = env_api_key
            elif env_username and env_password:
                self.auth = HTTPBasicAuth(env_username, env_password)
            else:
                raise ValueError("No Artifactory credentials provided. Set ARTIFACTORY_API_KEY or ARTIFACTORY_USERNAME/PASSWORD")
        
        # Disable SSL warnings if requested
        if not verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            logger.warning("SSL verification disabled for Artifactory connection")
        
        # Initialize cache
        self._cache = None
        self._cache_etag = None
        
        logger.info(f"Artifactory version storage initialized: {self.base_url}/{repository}/{self.versions_path}")
    
    def _get_artifact_url(self, path: str) -> str:
        """Build full Artifactory URL for an artifact."""
        return f"{self.base_url}/{self.repository}/{path}"
    
    def _load_from_artifactory(self) -> Dict[str, Any]:
        """Load version data from Artifactory."""
        try:
            url = self._get_artifact_url(self.versions_path)
            
            # Add ETag header if we have cached data
            headers = self.headers.copy()
            if self._cache_etag:
                headers['If-None-Match'] = self._cache_etag
            
            response = requests.get(
                url,
                auth=self.auth,
                headers=headers,
                verify=self.verify_ssl
            )
            
            if response.status_code == 304:
                # Not modified, use cache
                logger.debug("Using cached version data (ETag matched)")
                return self._cache
            
            if response.status_code == 404:
                # File doesn't exist yet, return empty structure
                logger.info("Version database not found in Artifactory, creating new one")
                return {
                    "repositories": {},
                    "metadata": {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "version": "2.0",
                        "storage": "artifactory"
                    }
                }
            
            response.raise_for_status()
            
            # Parse JSON content
            data = response.json()
            
            # Update cache
            self._cache = data
            self._cache_etag = response.headers.get('ETag')
            
            logger.debug(f"Loaded version data from Artifactory")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error loading from Artifactory: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in Artifactory version database: {e}")
            raise
    
    def _save_to_artifactory(self, data: Dict[str, Any]) -> bool:
        """Save version data to Artifactory."""
        try:
            # Add metadata
            data['metadata']['last_updated'] = datetime.now(timezone.utc).isoformat()
            data['metadata']['version'] = '2.0'
            data['metadata']['storage'] = 'artifactory'
            
            # Convert to JSON
            json_content = json.dumps(data, indent=2, sort_keys=True)
            
            url = self._get_artifact_url(self.versions_path)
            
            # Upload to Artifactory
            response = requests.put(
                url,
                data=json_content,
                auth=self.auth,
                headers=self.headers,
                verify=self.verify_ssl
            )
            
            response.raise_for_status()
            
            # Update cache
            self._cache = data
            self._cache_etag = response.headers.get('ETag')
            
            logger.info(f"Saved version data to Artifactory")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error saving to Artifactory: {e}")
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
        data = self._load_from_artifactory()
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
        data = self._load_from_artifactory()
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
        repo_data['current_version'] = version
        repo_data['last_updated'] = datetime.now(timezone.utc).isoformat()
        
        # Add to download history
        if 'download_history' not in repo_data:
            repo_data['download_history'] = []
        
        history_entry = {
            'version': version,
            'downloaded_at': datetime.now(timezone.utc).isoformat()
        }
        
        if metadata:
            history_entry['metadata'] = metadata
        
        repo_data['download_history'].append(history_entry)
        
        # Keep only last 100 entries in history
        if len(repo_data['download_history']) > 100:
            repo_data['download_history'] = repo_data['download_history'][-100:]
        
        # Save to Artifactory
        return self._save_to_artifactory(data)
    
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
        data = self._load_from_artifactory()
        repo_key = f"{owner}/{repo}"
        
        repo_data = data.get('repositories', {}).get(repo_key, {})
        history = repo_data.get('download_history', [])
        
        # Return most recent entries first
        return history[-limit:][::-1]
    
    def load_versions(self) -> Dict[str, Any]:
        """
        Load all version data.
        
        Returns:
            Complete version database
        """
        return self._load_from_artifactory()
    
    def save_versions(self, data: Dict[str, Any]) -> bool:
        """
        Save complete version database.
        
        Args:
            data: Complete version database to save
            
        Returns:
            True if successful
        """
        return self._save_to_artifactory(data)


# Alias for compatibility with S3 implementations
ArtifactoryVersionDatabase = ArtifactoryVersionStorage