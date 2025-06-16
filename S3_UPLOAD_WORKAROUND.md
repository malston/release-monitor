# S3 Upload Workaround

## Problem
The S3-compatible service at `cml-clfn.s3.cf.example.com` is rejecting all upload attempts with "MissingContentLength" errors, even when ContentLength is explicitly provided. This appears to be a compatibility issue between boto3 and this specific S3 implementation.

## Workarounds

### Option 1: Use AWS CLI Instead
We've created `scripts/upload-to-s3-curl.sh` which uses the AWS CLI instead of boto3:

```bash
# In your pipeline, replace:
python3 scripts/upload-to-s3.py

# With:
bash scripts/upload-to-s3-curl.sh
```

### Option 2: Skip Upload Step
If the S3 upload is not critical (files are already downloaded locally), you can:

1. Comment out the upload step in your pipeline
2. Use the downloaded files from `/tmp/downloads/`
3. Archive them using other methods if needed

### Option 3: Use Different Storage
Consider alternatives:
- Upload to a different S3-compatible service
- Use standard AWS S3 
- Store artifacts in your CI system's artifact storage
- Use a shared filesystem

## What We've Tried
1. ✅ Added explicit ContentLength parameter
2. ✅ Disabled multipart uploads
3. ✅ Used put_object instead of upload_file
4. ✅ Added ContentType and other headers
5. ❌ All approaches still fail with the same error

## Root Cause
The S3-compatible service has very specific requirements for the Content-Length header that boto3 is not meeting, possibly due to:
- Header formatting differences
- Request signing issues
- Incompatible S3 API implementation

## Recommendation
Use the AWS CLI workaround (`upload-to-s3-curl.sh`) or skip the upload step entirely if the downloaded files in `/tmp/downloads/` are sufficient for your needs.