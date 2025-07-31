#!/usr/bin/env python3
"""
Upload release files to S3 using MinIO client (mc).
This wrapper uses mc instead of boto3 for better S3-compatible service support.
"""

import os
import sys
import subprocess
from pathlib import Path


def run_command(cmd, check=True):
    """Run a shell command and return the result."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}")

    return result


def main():
    """Upload release files to S3 using mc."""

    # Get configuration from environment
    s3_endpoint = os.environ.get('S3_ENDPOINT', 'https://s3.example.com:443')
    s3_bucket = os.environ.get('S3_BUCKET', 'release-monitor-artifacts')
    access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    skip_ssl = os.environ.get('S3_SKIP_SSL_VERIFICATION', 'false').lower() == 'true'

    if not access_key or not secret_key:
        print("ERROR: AWS credentials not found in environment")
        sys.exit(1)

    # SSL flag
    insecure_flag = "--insecure" if skip_ssl else ""

    print(f"Configuring mc for S3-compatible endpoint...")
    print(f"Endpoint: {s3_endpoint}")
    print(f"Bucket: {s3_bucket}")
    if skip_ssl:
        print("WARNING: Skipping SSL verification")

    # Configure mc alias
    alias = "s3upload"
    cmd = f"mc alias set {alias} {s3_endpoint} {access_key} {secret_key} {insecure_flag}"
    run_command(cmd)

    # Find downloads directory
    downloads_dir = None
    for path in [Path('/tmp/downloads'), Path('../downloads'), Path('downloads')]:
        if path.exists():
            downloads_dir = path
            print(f"\nFound downloads directory at: {downloads_dir}")
            break

    if not downloads_dir:
        print("ERROR: Could not find downloads directory!")
        sys.exit(1)

    # Count files to upload
    files_to_upload = list(downloads_dir.rglob('*.gz')) + list(downloads_dir.rglob('*.zip'))
    total_files = len(files_to_upload)

    if total_files == 0:
        print("\nINFO: No release files found to upload.")
        print("This is normal when all monitored releases are already at their latest versions.")
        return

    print(f"\nFound {total_files} files to upload")

    # Upload files
    uploaded = 0
    failed = 0

    for file_path in files_to_upload:
        relative_path = file_path.relative_to(downloads_dir)
        target_path = f"{alias}/{s3_bucket}/release-downloads/{relative_path}"

        print(f"\nUploading: {relative_path}")
        print(f"  Size: {file_path.stat().st_size:,} bytes")

        cmd = f"mc cp {insecure_flag} '{file_path}' '{target_path}'"
        try:
            run_command(cmd)
            uploaded += 1
            print("  ✓ Success")
        except RuntimeError as e:
            failed += 1
            print(f"  ✗ Failed: {e}")

    # Summary
    print("\n" + "="*50)
    print("Upload Summary:")
    print(f"  Total files: {total_files}")
    print(f"  Uploaded: {uploaded}")
    print(f"  Failed: {failed}")
    print("="*50)

    # List recent uploads
    print("\nRecent uploads:")
    cmd = f"mc ls {insecure_flag} {alias}/{s3_bucket}/release-downloads/ --recursive | tail -10"
    run_command(cmd, check=False)

    # Clean up alias
    run_command(f"mc alias rm {alias}", check=False)

    # Exit with error if any uploads failed
    if failed > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
