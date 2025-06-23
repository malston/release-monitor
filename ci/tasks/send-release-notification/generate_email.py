#!/usr/bin/env python3
"""
Generate email notification for new GitHub releases
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


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
    new_releases = releases_data.get('new_releases', [])
    
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
Timestamp: {datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

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
    # Read the releases data
    releases_file = Path('/release-output/releases.json')
    if not releases_file.exists():
        print("No releases.json file found, skipping email notification")
        sys.exit(0)
    
    try:
        with open(releases_file, 'r') as f:
            releases_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error parsing releases.json: {e}")
        sys.exit(1)
    
    # Check if we have any new releases
    new_releases = releases_data.get('new_releases', [])
    if not new_releases:
        print("No new releases found, skipping email notification")
        sys.exit(0)
    
    # Generate email content
    subject, body = generate_email_content(releases_data)
    
    if not subject or not body:
        print("Failed to generate email content")
        sys.exit(1)
    
    # Write email content for Concourse email resource
    email_dir = Path('/email')
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
<li>Timestamp: {datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</li>
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
    
    print(f"Email notification prepared for {len(new_releases)} new releases")
    print(f"Subject: {subject}")


if __name__ == '__main__':
    main()