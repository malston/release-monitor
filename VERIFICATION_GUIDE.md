# Verification Guide: S3 Upload Fix for YAML Files

This guide explains how to verify that the upload script fix is working correctly and that YAML files like `wavefront-operator.yaml` are being uploaded to S3.

## 1. Quick Test (Just Run)

Run the test script to verify the logic:
```bash
python test_upload_fix.py
```

Expected output: `✅ TEST PASSED: YAML files would be uploaded correctly`

## 1.1. Test All Upload Scripts

Verify all upload scripts support YAML:
```bash
python test_all_upload_scripts.py
```

Expected output: `🎉 ALL UPLOAD SCRIPTS SUPPORT YAML FILES!`

## 2. Check Upload Script Logic

Verify all upload scripts include YAML extensions:
```bash
# Check boto3 version
grep -A 3 "supported_extensions" scripts/upload-to-s3.py

# Check MinIO client version  
grep -A 3 "supported_extensions" scripts/upload-to-s3-mc.py

# Check no-proxy version
grep -A 3 "supported_extensions" scripts/upload-to-s3-no-proxy.py
```

Expected output should include `.yaml` and `.yml` in the extensions list for all scripts.

### Upload Script Selection

The pipeline uses different upload scripts based on configuration:
- **`upload-to-s3.py`** - Default boto3 implementation 
- **`upload-to-s3-mc.py`** - MinIO client (mc) implementation for better S3-compatible service support
- **`upload-to-s3-no-proxy.py`** - Proxy bypass version for corporate environments

All three scripts now support the same file types including YAML manifests.

## 3. Test with Real Downloads (Dry Run)

If you have downloads already:
```bash
# Set environment variables (replace with your values)
export S3_ENDPOINT="your-s3-endpoint"
export S3_BUCKET="your-bucket"
export GITHUB_SKIP_SSL_VERIFICATION="true"
export S3_SKIP_SSL_VERIFICATION="true"

# Run upload script to see what would be uploaded
python scripts/upload-to-s3.py
```

Look for output like:
- `Scanning for files with extensions: ['.deb', '.dmg', '.exe', '.gz', '.json', '.msi', '.rpm', '.tar', '.toml', '.xml', '.yaml', '.yml', '.zip']`
- `Uploading wavefrontHQ_observability-for-kubernetes/v2.30.0/wavefront-operator.yaml to s3://...`

## 4. End-to-End Pipeline Test

Test the complete pipeline with YAML downloads:

### Step 1: Monitor for new releases
```bash
python github_monitor.py --config config.yaml --output releases.json
```

### Step 2: Download releases (including YAML files)
```bash
python download_releases.py --config config.yaml --input releases.json
```

### Step 3: Check what was downloaded
```bash
find downloads/ -name "*.yaml" -o -name "*.yml"
```

### Step 4: Upload to S3
```bash
python scripts/upload-to-s3.py
```

## 5. Verify in S3 Storage

Check your S3 bucket for the uploaded files:

### Using AWS CLI
```bash
aws s3 ls s3://your-bucket/release-downloads/ --recursive | grep -E "\.(yaml|yml)$"
```

### Using MinIO Client (mc)
```bash
mc ls your-alias/your-bucket/release-downloads/ --recursive | grep -E "\.(yaml|yml)$"
```

### Using S3 Console/Web UI
Navigate to your bucket and look for files under `release-downloads/` with `.yaml` extensions.

## 6. Specific Wavefront Test

To specifically test the Wavefront operator YAML:

### Set up repository override
```bash
export REPOSITORIES_OVERRIDE='[{"owner": "wavefrontHQ", "repo": "observability-for-kubernetes"}]'
```

### Run with YAML-specific patterns
```bash
export REPOSITORY_OVERRIDES='{"wavefrontHQ/observability-for-kubernetes": {"asset_patterns": ["*.yaml", "*.yml"]}}'
```

### Monitor and download
```bash
python github_monitor.py --config config.yaml --download
```

## 7. Debug Output Verification

The upload script now provides detailed debug output. Look for:

```
Scanning for files with extensions: ['.deb', '.dmg', '.exe', '.gz', '.json', '.msi', '.rpm', '.tar', '.toml', '.xml', '.yaml', '.yml', '.zip']
Also including files ending with: .tar.gz

Uploading wavefrontHQ_observability-for-kubernetes/v2.30.0/wavefront-operator.yaml to s3://bucket/release-downloads/...
  File size: 56535 bytes
  Content-Length: 56535
  Upload response: 200
  Success: Uploaded 56535 bytes

=== UPLOAD SUMMARY ===
Files uploaded: 1
Files skipped: 0
```

## Expected Results

✅ **Before the fix**: Only `.gz` and `.zip` files were uploaded
✅ **After the fix**: YAML, JSON, XML, TOML, and other manifest files are uploaded

## Troubleshooting

### If YAML files are still not uploaded:
1. Check that the files were actually downloaded to the downloads directory
2. Verify the file extensions match exactly (`.yaml` not `.yml` or vice versa)
3. Check the upload script debug output for skip messages
4. Ensure S3 credentials and permissions are correct

### If download fails:
1. Check SSL and proxy settings using `python test_proxy_ssl.py`
2. Verify `GITHUB_SKIP_SSL_VERIFICATION=true` is set
3. Check GitHub token permissions

### If upload fails:
1. Verify S3 endpoint and credentials
2. Check `S3_SKIP_SSL_VERIFICATION=true` for corporate environments
3. Ensure bucket exists and has write permissions

## Integration with CI/CD

In your Concourse pipeline, you should now see output like:
```
Uploading wavefront-operator.yaml to s3://bucket/release-downloads/...
Success: Uploaded 56535 bytes
```

Instead of:
```
Skipping wavefront-operator.yaml (extension: .yaml)
```