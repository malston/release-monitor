# Email Notification Setup Guide

This guide explains how to configure email notifications for the GitHub Release Monitor pipeline.

## Overview

The pipeline sends email notifications whenever new releases are detected. The emails include:
- Release details (repository, tag, author, published date)
- Download links
- Asset information (optional)

## Configuration

### 1. Email Resource Parameters

Add these parameters to your pipeline parameters file:

```yaml
# SMTP Configuration
smtp_host: smtp.gmail.com
smtp_port: "587"
smtp_username: your-email@example.com
smtp_password: ((smtp_password))  # Store in Concourse secrets
smtp_anonymous: false
smtp_skip_ssl_validation: false
smtp_ca_cert: ""
smtp_host_origin: ""
smtp_login_auth: true

# Email addresses
email_from: release-monitor@example.com
email_to: 
  - devops-team@example.com
  - platform-team@example.com

# Email options
email_subject_prefix: "[GitHub Release Monitor]"
email_include_asset_details: true
```

### 2. SMTP Provider Settings

#### Gmail
- Enable 2-factor authentication
- Generate an app-specific password
- Use the app password as `smtp_password`

#### Office 365
```yaml
smtp_host: smtp.office365.com
smtp_port: "587"
smtp_login_auth: true
```

#### SendGrid
```yaml
smtp_host: smtp.sendgrid.net
smtp_port: "587"
smtp_username: apikey
smtp_password: your-sendgrid-api-key
```

## Pipeline Behavior

1. **New Releases**: When new releases are detected, an HTML email is sent with release details
2. **No New Releases**: When no new releases are found, the email task exits cleanly without sending
3. **Errors**: If the email task fails, the pipeline continues (email is non-critical)

## Email Format

### Subject Line
- Single release: `[GitHub Release Monitor] New release: owner/repo v1.0.0`
- Multiple releases: `[GitHub Release Monitor] 3 new releases detected`

### Body Content
- Summary with timestamp and count
- Detailed information for each release
- Clickable links to GitHub release pages
- Asset download links (if enabled)

## Troubleshooting

### Common Issues

1. **"no such file or directory" error**
   - This occurs when no new releases are found
   - The email task should exit with code 0 (success)
   - Check that the task is properly creating output files

2. **SMTP Authentication Failed**
   - Verify SMTP credentials
   - Check if app-specific passwords are required
   - Ensure the from address is authorized

3. **Email Not Received**
   - Check spam/junk folders
   - Verify email addresses in parameters
   - Check Concourse logs for SMTP errors

### Debug Mode

To debug email generation, you can run the task locally:

```bash
# Create test data
mkdir -p release-output
cat > release-output/releases.json << EOF
{
  "timestamp": "2024-01-01T12:00:00Z",
  "total_repositories_checked": 1,
  "new_releases_found": 1,
  "releases": [{
    "repository": "test/repo",
    "tag_name": "v1.0.0",
    "name": "Test Release",
    "published_at": "2024-01-01T10:00:00Z",
    "html_url": "https://github.com/test/repo/releases/tag/v1.0.0",
    "author": {"login": "testuser"},
    "assets": []
  }]
}
EOF

# Run the email generation script
export EMAIL_SUBJECT_PREFIX="[Test]"
export INCLUDE_ASSET_DETAILS="true"
python ci/tasks/send-release-notification/generate_email.py

# Check output
cat email/subject
cat email/body.html
```

## Email Resource Details

The pipeline uses the `pcfseceng/email-resource` which expects:
- `subject`: Path to file containing email subject line
- `body`: Path to file containing email body (HTML supported)

The task outputs these files to the `email` directory which is then consumed by the email resource.