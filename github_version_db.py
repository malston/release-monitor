#!/usr/bin/env python3
"""
GitHub Version Database

Manages a persistent database of repository versions and download history.
Supports tracking current versions, download metadata, and audit trail.
"""

import json
import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import fcntl
import tempfile
import shutil

logger = logging.getLogger(__name__)


class VersionDatabase:
    """
    Manages version tracking and download history for GitHub repositories.

    Uses JSON file storage with file locking for concurrent access safety.
    """

    def __init__(self, db_path: str = 'version_db.json'):
        """
        Initialize version database.

        Args:
            db_path: Path to the JSON database file
        """
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        """Create database file if it doesn't exist."""
        if not os.path.exists(self.db_path):
            self._write_db({
                'metadata': {
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'version': '1.0',
                    'description': 'GitHub Release Monitor Version Database'
                },
                'repositories': {}
            })
            logger.info(f"Created new version database: {self.db_path}")

    def _read_db(self) -> Dict[str, Any]:
        """
        Read database with file locking for concurrent access safety.

        Returns:
            Database content as dictionary
        """
        try:
            with open(self.db_path, 'r') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
                data = json.load(f)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Unlock
                return data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error reading database: {e}")
            # Return empty structure if file is corrupted
            return {
                'metadata': {
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'version': '1.0'
                },
                'repositories': {}
            }

    def _write_db(self, data: Dict[str, Any]):
        """
        Write database with atomic operations and file locking.

        Args:
            data: Database content to write
        """
        # Update metadata
        data['metadata']['last_updated'] = datetime.now(timezone.utc).isoformat()

        # Atomic write using temporary file
        dir_path = os.path.dirname(self.db_path) or '.'
        with tempfile.NamedTemporaryFile(mode='w', dir=dir_path, delete=False) as temp_f:
            try:
                fcntl.flock(temp_f.fileno(), fcntl.LOCK_EX)  # Exclusive lock
                json.dump(data, temp_f, indent=2, ensure_ascii=False)
                temp_f.flush()
                os.fsync(temp_f.fileno())  # Force write to disk
                fcntl.flock(temp_f.fileno(), fcntl.LOCK_UN)  # Unlock

                # Atomically replace the original file
                shutil.move(temp_f.name, self.db_path)
                logger.debug(f"Database updated: {self.db_path}")

            except Exception as e:
                # Clean up temporary file on error
                try:
                    os.unlink(temp_f.name)
                except OSError:
                    pass
                raise e

    def _get_repo_key(self, owner: str, repo: str) -> str:
        """Generate repository key for database storage."""
        return f"{owner}/{repo}"

    def get_current_version(self, owner: str, repo: str) -> Optional[str]:
        """
        Get stored current version for repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Current version string or None if not found
        """
        data = self._read_db()
        repo_key = self._get_repo_key(owner, repo)

        repo_data = data['repositories'].get(repo_key)
        if repo_data:
            return repo_data.get('current_version')

        return None

    def update_version(self, owner: str, repo: str, version: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Update version after successful download.

        Args:
            owner: Repository owner
            repo: Repository name
            version: New version string
            metadata: Optional metadata (download info, file paths, etc.)
        """
        data = self._read_db()
        repo_key = self._get_repo_key(owner, repo)

        # Initialize repository data if it doesn't exist
        if repo_key not in data['repositories']:
            data['repositories'][repo_key] = {
                'owner': owner,
                'repo': repo,
                'current_version': None,
                'download_history': []
            }

        repo_data = data['repositories'][repo_key]
        previous_version = repo_data['current_version']

        # Update current version
        repo_data['current_version'] = version
        repo_data['last_updated'] = datetime.now(timezone.utc).isoformat()

        # Add to download history
        history_entry = {
            'version': version,
            'previous_version': previous_version,
            'downloaded_at': datetime.now(timezone.utc).isoformat(),
            'metadata': metadata or {}
        }

        repo_data['download_history'].append(history_entry)

        # Keep only last 50 history entries to prevent unbounded growth
        if len(repo_data['download_history']) > 50:
            repo_data['download_history'] = repo_data['download_history'][-50:]

        self._write_db(data)
        logger.info(f"Updated {repo_key}: {previous_version} → {version}")

    def get_download_history(self, owner: str, repo: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get download history for repository.

        Args:
            owner: Repository owner
            repo: Repository name
            limit: Maximum number of history entries to return

        Returns:
            List of download history entries (most recent first)
        """
        data = self._read_db()
        repo_key = self._get_repo_key(owner, repo)

        repo_data = data['repositories'].get(repo_key)
        if not repo_data:
            return []

        history = repo_data.get('download_history', [])
        # Return most recent entries first
        return list(reversed(history[-limit:]))

    def get_all_repositories(self) -> List[Dict[str, Any]]:
        """
        Get summary of all tracked repositories.

        Returns:
            List of repository summaries with current versions
        """
        data = self._read_db()
        repositories = []

        for repo_key, repo_data in data['repositories'].items():
            repositories.append({
                'owner': repo_data['owner'],
                'repo': repo_data['repo'],
                'current_version': repo_data['current_version'],
                'last_updated': repo_data.get('last_updated'),
                'download_count': len(repo_data.get('download_history', []))
            })

        return repositories

    def remove_repository(self, owner: str, repo: str) -> bool:
        """
        Remove repository from database.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            True if repository was removed, False if not found
        """
        data = self._read_db()
        repo_key = self._get_repo_key(owner, repo)

        if repo_key in data['repositories']:
            del data['repositories'][repo_key]
            self._write_db(data)
            logger.info(f"Removed {repo_key} from database")
            return True

        return False

    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Statistics about the database content
        """
        data = self._read_db()

        total_repos = len(data['repositories'])
        total_downloads = sum(
            len(repo_data.get('download_history', []))
            for repo_data in data['repositories'].values()
        )

        return {
            'total_repositories': total_repos,
            'total_downloads': total_downloads,
            'database_created': data['metadata'].get('created_at'),
            'last_updated': data['metadata'].get('last_updated'),
            'database_version': data['metadata'].get('version'),
            'database_size_bytes': os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        }
