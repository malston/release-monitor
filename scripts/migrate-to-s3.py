#!/usr/bin/env python3
"""
Migration Script: Local Version Database to S3

Helps migrate existing local version database files to S3 storage.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from github_version_s3 import S3VersionStorage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_to_s3(local_file: str, bucket: str, prefix: str = 'release-monitor/',
                  region: str = None, profile: str = None,
                  backup: bool = True) -> bool:
    """
    Migrate local version database to S3.

    Args:
        local_file: Path to local version database file
        bucket: S3 bucket name
        prefix: S3 key prefix
        region: AWS region (optional)
        profile: AWS profile (optional)
        backup: Create backup of S3 data before migration

    Returns:
        True if successful
    """
    logger.info("Starting migration to S3...")
    logger.info(f"Local file: {local_file}")
    logger.info(f"Target: s3://{bucket}/{prefix}version_db.json")

    # Check local file exists
    if not Path(local_file).exists():
        logger.error(f"Local file not found: {local_file}")
        return False

    # Create S3 storage instance
    try:
        s3_storage = S3VersionStorage(
            bucket=bucket,
            key_prefix=prefix,
            region=region,
            profile=profile
        )
    except Exception as e:
        logger.error(f"Failed to initialize S3 storage: {e}")
        return False

    # Test S3 connection
    logger.info("Testing S3 connection...")
    if not s3_storage.test_connection():
        logger.error("Failed to connect to S3")
        return False

    # Check if S3 version already exists
    existing_versions = s3_storage.get_all_versions()
    if existing_versions and backup:
        logger.info(f"Found existing S3 data with {len(existing_versions)} repositories")

        # Create backup
        backup_file = f"{local_file}.s3-backup"
        logger.info(f"Creating backup: {backup_file}")

        if not s3_storage.export_to_file(backup_file):
            logger.error("Failed to create backup")
            return False

        logger.info("Backup created successfully")

    # Load local data
    logger.info("Loading local version database...")
    try:
        with open(local_file, 'r') as f:
            local_data = json.load(f)

        logger.info(f"Loaded {len(local_data.get('repositories', {}))} repositories from local file")
    except Exception as e:
        logger.error(f"Failed to load local file: {e}")
        return False

    # Import to S3
    logger.info("Importing data to S3...")
    try:
        # Create temporary file with local data
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
            json.dump(local_data, tf)
            temp_file = tf.name

        # Import using merge to preserve any existing S3 data
        success = s3_storage.import_from_file(temp_file, merge=True)

        # Clean up temp file
        Path(temp_file).unlink()

        if not success:
            logger.error("Failed to import data to S3")
            return False

    except Exception as e:
        logger.error(f"Import failed: {e}")
        return False

    # Verify migration
    logger.info("Verifying migration...")
    s3_versions = s3_storage.get_all_versions()

    local_versions = {}
    for repo_key, repo_data in local_data.get('repositories', {}).items():
        if 'current_version' in repo_data:
            local_versions[repo_key] = repo_data['current_version']

    # Check all local versions are in S3
    missing = []
    for repo, version in local_versions.items():
        if repo not in s3_versions or s3_versions[repo] != version:
            missing.append(f"{repo}: {version}")

    if missing:
        logger.error(f"Migration verification failed. Missing/incorrect versions:")
        for m in missing:
            logger.error(f"  - {m}")
        return False

    logger.info("✓ Migration completed successfully!")
    logger.info(f"  - Migrated {len(local_versions)} repositories")
    logger.info(f"  - Total repositories in S3: {len(s3_versions)}")

    # Show sample configuration
    logger.info("\nUpdate your configuration to use S3:")
    logger.info("```yaml")
    logger.info("download:")
    logger.info("  s3_storage:")
    logger.info("    enabled: true")
    logger.info(f"    bucket: {bucket}")
    logger.info(f"    prefix: {prefix}")
    if region:
        logger.info(f"    region: {region}")
    logger.info("```")

    return True


def main():
    parser = argparse.ArgumentParser(
        description='Migrate local version database to S3',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic migration
  %(prog)s version_db.json --bucket my-bucket

  # With custom prefix and region
  %(prog)s version_db.json --bucket my-bucket --prefix prod/monitor/ --region us-east-1

  # Using AWS profile
  %(prog)s version_db.json --bucket my-bucket --profile production

  # Skip backup of existing S3 data
  %(prog)s version_db.json --bucket my-bucket --no-backup
"""
    )

    parser.add_argument('local_file', help='Path to local version database file')
    parser.add_argument('--bucket', '-b', required=True, help='S3 bucket name')
    parser.add_argument('--prefix', '-p', default='release-monitor/',
                       help='S3 key prefix (default: release-monitor/)')
    parser.add_argument('--region', '-r', help='AWS region')
    parser.add_argument('--profile', help='AWS profile to use')
    parser.add_argument('--no-backup', dest='backup', action='store_false',
                       help='Skip backup of existing S3 data')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run migration
    success = migrate_to_s3(
        local_file=args.local_file,
        bucket=args.bucket,
        prefix=args.prefix,
        region=args.region,
        profile=args.profile,
        backup=args.backup
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
