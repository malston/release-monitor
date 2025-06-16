# S3 ContentLength Workaround

## Problem
The S3-compatible service requires explicit `Content-Length` headers for all PUT operations, but boto3's automatic header handling conflicts with this requirement, causing "MissingContentLength" errors.

## Temporary Workaround
To allow the pipeline to work while we resolve the S3 compatibility issues, you can disable S3 version tracking by setting this environment variable:

```bash
export DISABLE_S3_VERSION_DB=true
```

## What This Does
- Disables S3 version database storage
- Falls back to local file-based version tracking
- Allows downloads to complete successfully
- Files will still be downloaded but version state won't be saved to S3

## Pipeline Configuration
Add this environment variable to your Concourse pipeline or CI configuration:

```yaml
- name: DISABLE_S3_VERSION_DB
  value: "true"
```

## Long-term Solution
We're working on a direct HTTP upload solution that bypasses boto3's automatic header management to properly work with your S3-compatible service. This will allow proper S3 version tracking to resume.

## Files Affected
- `download_releases.py` - Main download coordinator
- `github_version_s3.py` - S3 version database wrapper
- Both files now check for `DISABLE_S3_VERSION_DB` environment variable

## Impact
- ✅ Downloads will work
- ✅ Files will be saved locally 
- ❌ Version tracking won't persist between pipeline runs
- ❌ May re-download files that were already downloaded

## Re-enabling S3
Once the S3 compatibility issues are resolved, simply remove or set the environment variable to `false`:

```bash
unset DISABLE_S3_VERSION_DB
# or
export DISABLE_S3_VERSION_DB=false
```