#!/usr/bin/env python3
"""
Generate email notification for new GitHub releases

Environment Variables:
    RELEASES_INPUT_DIR: Directory containing releases.json (default: ../release-output)
    EMAIL_OUTPUT_DIR: Directory to write email files (default: ../email)
    EMAIL_SUBJECT_PREFIX: Prefix for email subject line (default: [GitHub Release Monitor])
    INCLUDE_ASSET_DETAILS: Include asset details in email (default: true)
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

# Add the repository root to Python path so we can import the version database modules
# Since the task runs from release-monitor-repo/, we need to add current directory to path
sys.path.insert(0, '.')

# Import the unified version database utilities
try:
    from version_database_utils import get_version_database as get_unified_version_db
    USE_UNIFIED_DB = True
except ImportError:
    USE_UNIFIED_DB = False


def get_version_database():
    """
    Get version database instance based on environment configuration.
    Returns None if version database is disabled or unavailable.
    """
    # Try unified version database first if available
    if USE_UNIFIED_DB:
        try:
            version_db = get_unified_version_db(verbose=True)
            if version_db:
                return version_db
        except Exception as e:
            print(f"Unified version database failed: {e}, falling back to legacy S3 approach")

    # Legacy behavior for backward compatibility
    # Check if version database is disabled
    if os.getenv('DISABLE_S3_VERSION_DB', '').lower() == 'true':
        print("Version database disabled, will not filter releases")
        return None

    # Check if we should use S3 version database
    if not os.getenv('USE_S3_VERSION_DB', '').lower() == 'true':
        print("S3 version database not enabled, will not filter releases")
        return None

    # Try to import and initialize S3 version database
    try:
        # Check if we should use MinIO client
        use_mc_s3 = os.getenv('S3_USE_MC', '').lower() == 'true'

        if use_mc_s3:
            try:
                # First check if mc command is available
                import subprocess
                mc_check = subprocess.run(['which', 'mc'], capture_output=True, text=True)
                if mc_check.returncode != 0:
                    print("MinIO client (mc) not found in PATH, falling back to boto3")
                    use_mc_s3 = False
                else:
                    from github_version_s3_mc import S3VersionDatabase
                    print("Using MinIO client for version database")
            except (ImportError, Exception) as e:
                print(f"MinIO client version not available ({e}), falling back to boto3")
                use_mc_s3 = False

        if not use_mc_s3:
            from github_version_s3 import S3VersionStorage as S3VersionDatabase
            print("Using boto3 for version database")

        # Get S3 configuration
        bucket = os.getenv('VERSION_DB_S3_BUCKET', os.getenv('S3_BUCKET'))
        prefix = os.getenv('VERSION_DB_S3_PREFIX', 'version-db/')

        if not bucket:
            print("No S3 bucket configured for version database")
            return None

        # Initialize version database
        try:
            version_db = S3VersionDatabase(bucket=bucket, key_prefix=prefix)
            print(f"Initialized version database with bucket: {bucket}, prefix: {prefix}")
            return version_db
        except Exception as init_error:
            print(f"Failed to initialize version database: {init_error}")
            # If mc initialization failed, try boto3 as final fallback
            if use_mc_s3:
                print("Attempting final fallback to boto3...")
                from github_version_s3 import S3VersionStorage as S3VersionDatabase
                version_db = S3VersionDatabase(bucket=bucket, key_prefix=prefix)
                print(f"Successfully initialized boto3 version database")
                return version_db
            else:
                raise

    except ImportError as e:
        print(f"Version database modules not available: {e}")
        return None
    except Exception as e:
        print(f"Failed to initialize version database: {e}")
        return None


def filter_undownloaded_releases(releases: List[Dict[str, Any]], version_db) -> List[Dict[str, Any]]:
    """
    Filter releases to only include those not already in the version database.

    Args:
        releases: List of release information dictionaries
        version_db: Version database instance (can be None)

    Returns:
        List of releases that are not yet in the version database
    """
    if not version_db:
        print("No version database available, including all releases")
        return releases

    filtered_releases = []

    for release in releases:
        repo_name = release.get('repository', '')
        tag_name = release.get('tag_name', '')

        if not repo_name or not tag_name:
            print(f"Skipping release with missing repository or tag: {release}")
            continue

        try:
            # Parse owner/repo from repository name
            if '/' in repo_name:
                owner, repo = repo_name.split('/', 1)
            else:
                print(f"Invalid repository format: {repo_name}")
                continue

            # Check if this version is already in the database
            current_version = version_db.get_current_version(owner, repo)

            if current_version == tag_name:
                print(f"Release {repo_name} {tag_name} already downloaded, skipping email notification")
                continue
            elif current_version:
                print(f"Release {repo_name} {tag_name} is new (current: {current_version}), including in email")
            else:
                print(f"Release {repo_name} {tag_name} is first release, including in email")

            filtered_releases.append(release)

        except Exception as e:
            print(f"Error checking version database for {repo_name}: {e}")
            # Include the release if we can't check the database
            filtered_releases.append(release)

    return filtered_releases


def format_release_details(release):
    """Format a single release for email display"""
    repo_name = release.get('repository', 'Unknown')
    tag_name = release.get('tag_name', 'Unknown')
    release_name = release.get('name', tag_name)
    author = release.get('author', {}).get('login', 'Unknown')
    published_at = release.get('published_at', 'Unknown')
    html_url = release.get('html_url', '#')

    # Format published date
    if published_at != 'Unknown':
        try:
            dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            published_at = dt.strftime('%Y-%m-%d %H:%M UTC')
        except:
            pass

    # Format assets if requested
    assets_text = ""
    if os.getenv('INCLUDE_ASSET_DETAILS', 'true').lower() == 'true':
        assets = release.get('assets', [])
        if assets:
            assets_text = "\n    Assets:\n"
            for asset in assets[:5]:  # Show max 5 assets
                asset_name = asset.get('name', 'Unknown')
                asset_size = asset.get('size', 0)
                size_mb = asset_size / (1024 * 1024)
                assets_text += f"      - {asset_name} ({size_mb:.1f} MB)\n"
            if len(assets) > 5:
                assets_text += f"      ... and {len(assets) - 5} more\n"

    return f"""
  Repository: {repo_name}
  Release: {release_name}
  Tag: {tag_name}
  Author: {author}
  Published: {published_at}
  URL: {html_url}{assets_text}
"""


def generate_email_content(releases_data):
    """Generate email body and subject from releases data"""
    new_releases = releases_data.get('releases', [])

    if not new_releases:
        return None, None

    # Generate subject
    subject_prefix = os.getenv('EMAIL_SUBJECT_PREFIX', '[GitHub Release Monitor]')
    if len(new_releases) == 1:
        release = new_releases[0]
        subject = f"{subject_prefix} New release: {release.get('repository', 'Unknown')} {release.get('tag_name', 'Unknown')}"
    else:
        subject = f"{subject_prefix} {len(new_releases)} new releases detected"

    # Generate body
    body = f"""New GitHub releases have been detected by the release monitor.

Summary:
========
Total new releases: {len(new_releases)}
Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

Release Details:
================
"""

    for release in new_releases:
        body += format_release_details(release)
        body += "\n" + "-" * 60 + "\n"

    body += """
This is an automated notification from the GitHub Release Monitor pipeline.
"""

    return subject, body


def main():
    """Main function to generate email notification"""
    # Get configurable paths from environment variables
    # Default to Concourse structure if not specified
    releases_input_dir = os.getenv('RELEASES_INPUT_DIR', '../release-output')
    email_output_dir = os.getenv('EMAIL_OUTPUT_DIR', '../email')

    # Read the releases data
    releases_file = Path(releases_input_dir) / 'releases.json'
    if not releases_file.exists():
        print("No releases.json file found, creating empty email notification")
        # Create empty email files so the S3 resource doesn't fail
        email_dir = Path(email_output_dir)
        email_dir.mkdir(exist_ok=True)

        # Write empty body file
        with open(email_dir / 'body', 'w') as f:
            f.write('')

        # Write empty subject file
        with open(email_dir / 'subject', 'w') as f:
            f.write('')

        # Write empty HTML body file
        with open(email_dir / 'body.html', 'w') as f:
            f.write('')

        # Write empty headers file
        with open(email_dir / 'headers', 'w') as f:
            f.write('')

        print("Empty email files created for Concourse resource")
        sys.exit(0)

    try:
        with open(releases_file, 'r') as f:
            releases_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error parsing releases.json: {e}")
        sys.exit(1)

    # Get all releases from the data
    all_releases = releases_data.get('releases', [])
    if not all_releases:
        print("No releases found in releases.json, creating empty email notification")
        # Create empty email files so the S3 resource doesn't fail
        email_dir = Path(email_output_dir)
        email_dir.mkdir(exist_ok=True)

        # Write empty body file
        with open(email_dir / 'body', 'w') as f:
            f.write('')

        # Write empty subject file
        with open(email_dir / 'subject', 'w') as f:
            f.write('')

        # Write empty HTML body file
        with open(email_dir / 'body.html', 'w') as f:
            f.write('')

        # Write empty headers file
        with open(email_dir / 'headers', 'w') as f:
            f.write('')

        print("Empty email files created for Concourse resource")
        sys.exit(0)

    # Initialize version database for filtering
    version_db = get_version_database()

    # Filter to only include releases not already downloaded
    new_releases = filter_undownloaded_releases(all_releases, version_db)

    if not new_releases:
        print("All releases have already been downloaded, creating empty email notification")
        # Create empty email files so the S3 resource doesn't fail
        email_dir = Path(email_output_dir)
        email_dir.mkdir(exist_ok=True)

        # Write empty body file
        with open(email_dir / 'body', 'w') as f:
            f.write('')

        # Write empty subject file
        with open(email_dir / 'subject', 'w') as f:
            f.write('')

        # Write empty HTML body file
        with open(email_dir / 'body.html', 'w') as f:
            f.write('')

        # Write empty headers file
        with open(email_dir / 'headers', 'w') as f:
            f.write('')

        print("Empty email files created for Concourse resource")
        sys.exit(0)

    print(f"Found {len(new_releases)} releases that need email notification (out of {len(all_releases)} total)")

    # Create filtered releases data for email generation
    filtered_releases_data = releases_data.copy()
    filtered_releases_data['releases'] = new_releases
    filtered_releases_data['new_releases_found'] = len(new_releases)

    # Generate email content
    subject, body = generate_email_content(filtered_releases_data)

    if not subject or not body:
        print("Failed to generate email content")
        sys.exit(1)

    # Write email content for Concourse email resource
    # Use configurable output directory
    email_dir = Path(email_output_dir)
    email_dir.mkdir(exist_ok=True)

    # Write subject
    with open(email_dir / 'subject', 'w') as f:
        f.write(subject)

    # Write body
    with open(email_dir / 'body', 'w') as f:
        f.write(body)

    # Also write HTML version (email resource supports both)
    html_body = f"""<html>
<body>
<h2>New GitHub Releases Detected</h2>
<p>New GitHub releases have been detected by the release monitor.</p>

<h3>Summary</h3>
<ul>
<li>Total new releases: {len(new_releases)}</li>
<li>Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</li>
</ul>

<h3>Release Details</h3>
"""

    for release in new_releases:
        repo_name = release.get('repository', 'Unknown')
        tag_name = release.get('tag_name', 'Unknown')
        release_name = release.get('name', tag_name)
        html_url = release.get('html_url', '#')
        author = release.get('author', {}).get('login', 'Unknown')
        published_at = release.get('published_at', 'Unknown')

        html_body += f"""
<hr>
<h4><a href="{html_url}">{repo_name} - {release_name}</a></h4>
<ul>
<li><strong>Tag:</strong> {tag_name}</li>
<li><strong>Author:</strong> {author}</li>
<li><strong>Published:</strong> {published_at}</li>
"""

        if os.getenv('INCLUDE_ASSET_DETAILS', 'true').lower() == 'true':
            assets = release.get('assets', [])
            if assets:
                html_body += "<li><strong>Assets:</strong><ul>"
                for asset in assets[:5]:
                    asset_name = asset.get('name', 'Unknown')
                    asset_size = asset.get('size', 0)
                    size_mb = asset_size / (1024 * 1024)
                    download_url = asset.get('browser_download_url', '#')
                    html_body += f'<li><a href="{download_url}">{asset_name}</a> ({size_mb:.1f} MB)</li>'
                if len(assets) > 5:
                    html_body += f"<li>... and {len(assets) - 5} more</li>"
                html_body += "</ul></li>"

        html_body += "</ul>"

    html_body += """
<hr>
<p><em>This is an automated notification from the GitHub Release Monitor pipeline.</em></p>
</body>
</html>"""

    with open(email_dir / 'body.html', 'w') as f:
        f.write(html_body)

    # Write headers file for proper content type
    headers = 'MIME-Version: 1.0\nContent-Type: text/html; charset="UTF-8"'
    with open(email_dir / 'headers', 'w') as f:
        f.write(headers)

    print(f"Email notification prepared for {len(new_releases)} new releases")
    print(f"Subject: {subject}")

    sys.exit(0)


if __name__ == '__main__':
    main()
