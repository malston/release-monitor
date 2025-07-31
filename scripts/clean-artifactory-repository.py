#!/usr/bin/env python3
"""
Clean up artifacts in the Artifactory repository.

This script can delete downloaded release files, version database, and other artifacts
from the Artifactory repository to start fresh or free up space.

Usage:
    python3 clean-artifactory-repository.py [options]

Options:
    --releases-only    Delete only downloaded release artifacts, keep database and monitor output
    --all             Delete everything including version database and monitor output
    --dry-run         Show what would be deleted without actually deleting
    --help            Show this help message

Examples:
    # Show what release files would be deleted (dry run)
    python3 clean-artifactory-repository.py --releases-only --dry-run

    # Delete all downloaded release files but keep database
    python3 clean-artifactory-repository.py --releases-only

    # Delete everything in the repository
    python3 clean-artifactory-repository.py --all
"""

import os
import sys
import json
import requests
import argparse
from urllib.parse import quote


def get_repository_contents(artifactory_url, repository, auth_headers, auth, verify_ssl, path=""):
    """Get list of files and folders in the Artifactory repository."""

    # Use Artifactory REST API to list repository contents
    api_url = f"{artifactory_url.rstrip('/')}/api/storage/{repository}"
    if path:
        api_url += f"/{path.strip('/')}"

    headers = auth_headers.copy()
    headers['Accept'] = 'application/json'

    try:
        response = requests.get(api_url, headers=headers, auth=auth, verify=verify_ssl)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f'Error listing repository contents: {e}')
        if hasattr(e, 'response') and e.response:
            print(f'Response status: {e.response.status_code}')
            print(f'Response text: {e.response.text}')
        return None


def collect_artifacts(artifactory_url, repository, auth_headers, auth, verify_ssl, path="", files_list=None):
    """Recursively collect all artifacts in the repository."""

    if files_list is None:
        files_list = []

    contents = get_repository_contents(artifactory_url, repository, auth_headers, auth, verify_ssl, path)
    if not contents:
        return files_list

    # Process children (files and folders)
    for child in contents.get('children', []):
        child_path = f"{path}/{child['uri'].lstrip('/')}" if path else child['uri'].lstrip('/')

        if child.get('folder'):
            # Recursively process folder
            collect_artifacts(artifactory_url, repository, auth_headers, auth, verify_ssl, child_path, files_list)
        else:
            # Add file to list
            files_list.append({
                'path': child_path,
                'size': child.get('size', 0),
                'lastModified': child.get('lastModified', 'unknown')
            })

    return files_list


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


def delete_empty_folders(artifactory_url, repository, auth_headers, auth, verify_ssl, deleted_files):
    """Delete empty folders left behind after file deletion."""

    if not deleted_files:
        return 0

    # Collect all unique folder paths from deleted files
    folder_paths = set()
    for file_path in deleted_files:
        # Get all parent directories
        parts = file_path.split('/')
        for i in range(1, len(parts)):
            folder_path = '/'.join(parts[:i])
            if folder_path:
                folder_paths.add(folder_path)

    # Sort folders by depth (deepest first) so we delete child folders before parents
    sorted_folders = sorted(folder_paths, key=lambda x: x.count('/'), reverse=True)

    deleted_folders = 0

    for folder_path in sorted_folders:
        # Check if folder is empty
        contents = get_repository_contents(artifactory_url, repository, auth_headers, auth, verify_ssl, folder_path)
        if contents and len(contents.get('children', [])) == 0:
            # Folder is empty, delete it
            url = f"{artifactory_url.rstrip('/')}/{repository}/{folder_path}"

            try:
                response = requests.delete(url, headers=auth_headers, auth=auth, verify=verify_ssl)
                response.raise_for_status()
                print(f"Deleted empty folder: {folder_path}/")
                deleted_folders += 1
            except requests.exceptions.RequestException as e:
                # Don't fail the whole operation for folder cleanup issues
                print(f'Warning: Could not delete empty folder {folder_path}: {e}')

    return deleted_folders


def categorize_artifacts(artifacts):
    """Categorize artifacts into different types."""

    categories = {
        'version_db': [],
        'monitor_output': [],
        'release_downloads': [],
        'other': []
    }

    for artifact in artifacts:
        path = artifact['path']

        if path.endswith('version_db.json'):
            categories['version_db'].append(artifact)
        elif path.endswith('latest-releases.json'):
            categories['monitor_output'].append(artifact)
        elif path.startswith('release-downloads/'):
            categories['release_downloads'].append(artifact)
        else:
            categories['other'].append(artifact)

    return categories


def format_size(size_bytes):
    """Format file size in human readable format."""

    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    size = float(size_bytes)

    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1

    return f"{size:.1f} {size_names[i]}"


def main():
    """Main function to clean up Artifactory repository."""

    parser = argparse.ArgumentParser(description='Clean up artifacts in Artifactory repository')
    parser.add_argument('--releases-only', action='store_true',
                       help='Delete only downloaded release artifacts, keep database and monitor output')
    parser.add_argument('--all', action='store_true',
                       help='Delete everything including version database and monitor output')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be deleted without actually deleting')

    args = parser.parse_args()

    if not args.releases_only and not args.all:
        print("Error: You must specify either --releases-only or --all")
        print("Use --help for usage information")
        sys.exit(1)

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
        from requests.auth import HTTPBasicAuth
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

    if args.dry_run:
        print("DRY RUN MODE - No files will actually be deleted")

    print("\nScanning repository for artifacts...")

    # Collect all artifacts
    artifacts = collect_artifacts(artifactory_url, repository, auth_headers, auth, verify_ssl)

    if not artifacts:
        print("No artifacts found in repository")
        return

    # Categorize artifacts
    categories = categorize_artifacts(artifacts)

    print(f"\nFound {len(artifacts)} total artifacts:")
    print(f"  Version database: {len(categories['version_db'])} files")
    print(f"  Monitor output: {len(categories['monitor_output'])} files")
    print(f"  Release downloads: {len(categories['release_downloads'])} files")
    print(f"  Other files: {len(categories['other'])} files")

    # Calculate total sizes
    total_size = sum(artifact['size'] for artifact in artifacts)
    releases_size = sum(artifact['size'] for artifact in categories['release_downloads'])

    print(f"\nTotal repository size: {format_size(total_size)}")
    print(f"Release downloads size: {format_size(releases_size)}")

    # Determine what to delete
    to_delete = []

    if args.all:
        to_delete = artifacts
        print(f"\nPlan: Delete ALL {len(artifacts)} artifacts ({format_size(total_size)})")
    elif args.releases_only:
        to_delete = categories['release_downloads']
        print(f"\nPlan: Delete {len(to_delete)} release download files ({format_size(releases_size)})")
        if categories['version_db']:
            print("  Keeping version database files")
        if categories['monitor_output']:
            print("  Keeping monitor output files")
        if categories['other']:
            print(f"  Keeping {len(categories['other'])} other files")

    if not to_delete:
        print("No files to delete")
        return

    # Show what will be deleted
    print(f"\nFiles to delete:")
    for artifact in sorted(to_delete, key=lambda x: x['path']):
        size_str = format_size(artifact['size'])
        print(f"  - {artifact['path']} ({size_str})")

    if args.dry_run:
        print(f"\nDRY RUN: Would delete {len(to_delete)} files ({format_size(sum(a['size'] for a in to_delete))})")
        return

    # Confirm deletion
    print(f"\nThis will permanently delete {len(to_delete)} files ({format_size(sum(a['size'] for a in to_delete))})!")
    confirmation = input("Are you sure? Type 'yes' to continue: ")

    if confirmation.lower() != 'yes':
        print("Deletion cancelled")
        return

    # Delete artifacts
    print(f"\nDeleting {len(to_delete)} artifacts...")
    deleted_count = 0
    deleted_size = 0
    failed_count = 0
    deleted_file_paths = []

    for artifact in to_delete:
        print(f"Deleting: {artifact['path']} ({format_size(artifact['size'])})")

        if delete_artifact(artifactory_url, repository, auth_headers, auth, verify_ssl, artifact['path']):
            deleted_count += 1
            deleted_size += artifact['size']
            deleted_file_paths.append(artifact['path'])
        else:
            failed_count += 1

    # Clean up empty folders
    deleted_folders = 0
    if deleted_file_paths:
        print(f"\nCleaning up empty folders...")
        deleted_folders = delete_empty_folders(artifactory_url, repository, auth_headers, auth, verify_ssl, deleted_file_paths)

    print(f"\nCleanup complete:")
    print(f"  Successfully deleted: {deleted_count} files ({format_size(deleted_size)})")
    if deleted_folders > 0:
        print(f"  Cleaned up: {deleted_folders} empty folders")
    if failed_count > 0:
        print(f"  Failed to delete: {failed_count} files")

    if args.releases_only and deleted_count > 0:
        print(f"\nNext pipeline run will re-download all releases")


if __name__ == '__main__':
    main()
