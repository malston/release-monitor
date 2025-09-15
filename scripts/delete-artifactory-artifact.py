#!/usr/bin/env python3
"""
Delete a specific artifact from the Artifactory repository.

This script allows you to delete individual artifacts from Artifactory
without affecting other files in the repository.

Usage:
    python3 delete-artifactory-artifact.py <artifact-path> [options]

Arguments:
    artifact-path     Path to the artifact to delete (relative to repository root)

Options:
    --dry-run         Show what would be deleted without actually deleting
    --force           Skip confirmation prompt
    --help            Show this help message

Examples:
    # Delete a specific release file (with confirmation)
    python3 delete-artifactory-artifact.py releases/acme-app/v1.0.0/acme-app.tar.gz

    # Delete with dry run to see what would happen
    python3 delete-artifactory-artifact.py releases/acme-app/v1.0.0/acme-app.tar.gz --dry-run

    # Delete without confirmation prompt
    python3 delete-artifactory-artifact.py releases/acme-app/v1.0.0/acme-app.tar.gz --force

    # Delete a version database file
    python3 delete-artifactory-artifact.py version-database/acme-app-versions.json

Environment Variables:
    ARTIFACTORY_URL           URL to Artifactory instance (required)
    ARTIFACTORY_REPOSITORY    Repository name (required)
    ARTIFACTORY_API_KEY       API key for authentication (preferred)
    ARTIFACTORY_USERNAME      Username for basic auth (if no API key)
    ARTIFACTORY_PASSWORD      Password for basic auth (if no API key)
    ARTIFACTORY_SKIP_SSL_VERIFICATION  Set to 'true' to skip SSL verification
"""

import os
import sys
import json
import argparse
import requests
from requests.auth import HTTPBasicAuth


def get_artifact_info(artifactory_url, repository, auth_headers, auth, verify_ssl, artifact_path):
    """Get information about a specific artifact."""

    url = f"{artifactory_url.rstrip('/')}/api/storage/{repository}/{artifact_path}"

    try:
        response = requests.get(url, headers=auth_headers, auth=auth, verify=verify_ssl)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return None
        raise
    except requests.exceptions.RequestException as e:
        print(f'Error getting artifact info: {e}')
        if hasattr(e, 'response') and e.response:
            print(f'Response status: {e.response.status_code}')
            print(f'Response text: {e.response.text}')
        return None


def delete_artifact(artifactory_url, repository, auth_headers, auth, verify_ssl, artifact_path):
    """Delete a specific artifact from Artifactory."""

    url = f"{artifactory_url.rstrip('/')}/{repository}/{artifact_path}"

    try:
        response = requests.delete(url, headers=auth_headers, auth=auth, verify=verify_ssl)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f'Error deleting {artifact_path}: {e}')
        if hasattr(e, 'response') and e.response:
            print(f'Response status: {e.response.status_code}')
            print(f'Response text: {e.response.text}')
        return False


def format_size(size_bytes):
    """Format file size in human-readable format."""

    # Convert to int if it's a string
    if isinstance(size_bytes, str):
        try:
            size_bytes = int(size_bytes)
        except (ValueError, TypeError):
            return "Unknown size"

    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def main():
    """Main function to delete a specific artifact from Artifactory."""

    parser = argparse.ArgumentParser(
        description='Delete a specific artifact from Artifactory repository',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Delete a specific release file (with confirmation)
    python3 delete-artifactory-artifact.py releases/acme-app/v1.0.0/acme-app.tar.gz

    # Delete with dry run to see what would happen
    python3 delete-artifactory-artifact.py releases/acme-app/v1.0.0/acme-app.tar.gz --dry-run

    # Delete without confirmation prompt
    python3 delete-artifactory-artifact.py releases/acme-app/v1.0.0/acme-app.tar.gz --force
"""
    )

    parser.add_argument('artifact_path',
                       help='Path to the artifact to delete (relative to repository root)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be deleted without actually deleting')
    parser.add_argument('--force', action='store_true',
                       help='Skip confirmation prompt')

    args = parser.parse_args()

    # Clean up the artifact path
    artifact_path = args.artifact_path.strip('/')

    # Required environment variables
    artifactory_url = os.environ.get('ARTIFACTORY_URL')
    if not artifactory_url:
        print("ERROR: ARTIFACTORY_URL environment variable not set")
        sys.exit(1)

    repository = os.environ.get('ARTIFACTORY_REPOSITORY')
    if not repository:
        print("ERROR: ARTIFACTORY_REPOSITORY environment variable not set")
        sys.exit(1)

    # Authentication - prefer API key over username/password
    api_key = os.environ.get('ARTIFACTORY_API_KEY')
    username = os.environ.get('ARTIFACTORY_USERNAME')
    password = os.environ.get('ARTIFACTORY_PASSWORD')

    auth_headers = {}
    auth = None

    if api_key:
        auth_headers['Authorization'] = f'Bearer {api_key}'
        print("Using API key authentication")
    elif username and password:
        auth = HTTPBasicAuth(username, password)
        print(f"Using username/password authentication for user: {username}")
    else:
        print("ERROR: No authentication credentials found.")
        print("Set ARTIFACTORY_API_KEY or ARTIFACTORY_USERNAME/ARTIFACTORY_PASSWORD")
        sys.exit(1)

    # SSL verification
    verify_ssl = os.environ.get('ARTIFACTORY_SKIP_SSL_VERIFICATION', 'false').lower() != 'true'
    if not verify_ssl:
        print("WARNING: Skipping SSL verification for Artifactory endpoint")
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    print(f'Connecting to Artifactory: {artifactory_url}')
    print(f'Repository: {repository}')
    print(f'Artifact path: {artifact_path}')

    if args.dry_run:
        print("\nDRY RUN MODE - No files will actually be deleted")

    # Get artifact information
    print("\nFetching artifact information...")
    artifact_info = get_artifact_info(artifactory_url, repository, auth_headers, auth, verify_ssl, artifact_path)

    if not artifact_info:
        print(f"\nERROR: Artifact not found: {artifact_path}")
        print("Please check the path and try again.")
        sys.exit(1)

    # Check if it's a folder
    if artifact_info.get('folder'):
        print(f"\nERROR: {artifact_path} is a folder, not a file.")
        print("This script can only delete individual files.")
        print("To delete folders and their contents, use clean-artifactory-repository.py")
        sys.exit(1)

    # Display artifact information
    size = artifact_info.get('size', 0)
    created = artifact_info.get('created', 'unknown')
    last_modified = artifact_info.get('lastModified', 'unknown')

    print(f"\nArtifact details:")
    print(f"  Path: {artifact_path}")
    print(f"  Size: {format_size(size)}")
    print(f"  Created: {created}")
    print(f"  Last Modified: {last_modified}")

    if 'checksums' in artifact_info:
        checksums = artifact_info['checksums']
        if 'sha256' in checksums:
            print(f"  SHA256: {checksums['sha256']}")
        elif 'sha1' in checksums:
            print(f"  SHA1: {checksums['sha1']}")

    if args.dry_run:
        print(f"\nDRY RUN: Would delete artifact: {artifact_path} ({format_size(size)})")
        return

    # Confirm deletion unless --force is used
    if not args.force:
        print(f"\nThis will permanently delete: {artifact_path} ({format_size(size)})")
        confirmation = input("Are you sure? Type 'yes' to continue: ")

        if confirmation.lower() != 'yes':
            print("Deletion cancelled")
            return

    # Delete the artifact
    print(f"\nDeleting artifact: {artifact_path}")

    if delete_artifact(artifactory_url, repository, auth_headers, auth, verify_ssl, artifact_path):
        print(f"Successfully deleted: {artifact_path}")
    else:
        print(f"Failed to delete: {artifact_path}")
        sys.exit(1)


if __name__ == '__main__':
    main()
