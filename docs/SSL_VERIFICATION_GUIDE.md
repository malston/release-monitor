# SSL Verification Configuration Guide

This guide explains how SSL verification is handled throughout the GitHub Release Monitor when using S3-compatible storage like MinIO with self-signed certificates.

## Environment Variable

All SSL verification is controlled by a single environment variable:

```bash
S3_SKIP_SSL_VERIFICATION=true  # Disable SSL verification
S3_SKIP_SSL_VERIFICATION=false # Enable SSL verification (default)
```

## Components Updated for SSL Verification

### 1. **Core S3 Storage Classes**

#### `github_version_s3_compatible.py`

- Main S3-compatible storage class
- Automatically configures SSL verification based on environment
- Used for version database operations

#### `github_version_s3.py`

- Original AWS S3 storage class
- Now supports SSL verification settings
- Backward compatible

### 2. **Utility Scripts**

All scripts in the `scripts/` directory now support SSL verification:

#### `scripts/upload-to-s3.py`

- Uploads release files to S3 storage
- Respects `S3_SKIP_SSL_VERIFICATION` setting

#### `scripts/clear-version-db.py`

- Clears entire version database
- SSL verification configurable

#### `scripts/clear-version-entry.py`

- Clears specific repository from database
- SSL verification configurable

#### `scripts/view-version-db.py`

- Views version database contents
- SSL verification configurable

### 3. **Concourse Pipeline Tasks**

#### `ci/tasks/download-releases/task.yml` and `task.sh`

- Download task supports SSL verification
- Environment variable passed through pipeline

#### `ci/pipeline-s3-compatible.yml`

- All inline boto3 tasks updated
- SSL verification passed to all S3 operations

## Usage Examples

### 1. **Local Development with MinIO**

```bash
export S3_ENDPOINT=https://minio.local:9000
export S3_SKIP_SSL_VERIFICATION=true
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin

# Run any script
python3 scripts/view-version-db.py
```

### 2. **Concourse Pipeline with Self-Signed Certificates**

In your pipeline parameters file:

```yaml
# Pipeline parameters
s3_endpoint: https://minio.company.com:9000
s3_skip_ssl_verification: true
s3_access_key: your-access-key
s3_secret_key: your-secret-key
```

### 3. **AWS S3 (Production)**

```yaml
# Pipeline parameters
s3_endpoint: ""  # Empty for AWS S3
s3_skip_ssl_verification: false  # Always verify SSL for AWS
s3_access_key: your-aws-key
s3_secret_key: your-aws-secret
```

## Technical Implementation

### SSL Configuration Method

All boto3 clients are configured using the same pattern:

```python
from botocore.config import Config

# Configure SSL verification
skip_ssl_verification = os.environ.get('S3_SKIP_SSL_VERIFICATION', 'false').lower() == 'true'

client_config = Config(
    signature_version='s3v4',
    s3={'addressing_style': 'path'}
)

if skip_ssl_verification:
    client_config.merge(Config(
        use_ssl=True,     # Still use HTTPS
        verify=False      # Don't verify certificates
    ))

s3 = boto3.client('s3', config=client_config, ...)
```

### Key Points

1. **Still uses HTTPS**: SSL verification is disabled, but HTTPS is still used
2. **Certificate validation bypassed**: Self-signed certificates are accepted
3. **Consistent across all components**: All boto3 clients use the same configuration
4. **Environment-driven**: Single variable controls all SSL behavior

## Troubleshooting

### Common SSL Errors Before Fix

```
SSLError: HTTPSConnectionPool(host='minio.local', port=9000): 
Max retries exceeded with url: / 
(Caused by SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED]')))
```

### After SSL Verification Fix

```
WARNING: Skipping SSL verification for S3 endpoint
Connection successful! Found 2 buckets
```

### Testing SSL Configuration

Use the provided test script to verify SSL settings:

```bash
S3_SKIP_SSL_VERIFICATION=true python3 scripts/view-version-db.py
```

### Pipeline Testing

Run the authentication test in your pipeline:

```bash
fly -t your-target execute -c - <<EOF
platform: linux
image_resource:
  type: registry-image
  source: {repository: python, tag: 3.11-slim}
params:
  S3_ENDPOINT: https://your-minio:9000
  S3_SKIP_SSL_VERIFICATION: "true"
  AWS_ACCESS_KEY_ID: your-key
  AWS_SECRET_ACCESS_KEY: your-secret
run:
  path: bash
  args:
    - -c
    - |
      pip install boto3
      python3 -c "
      import boto3, os
      from botocore.config import Config
      
      config = Config()
      client_kwargs = {'endpoint_url': os.getenv('S3_ENDPOINT'), 'config': config}
      if os.getenv('S3_SKIP_SSL_VERIFICATION') == 'true':
          client_kwargs['verify'] = False
      s3 = boto3.client('s3', **client_kwargs)
      print('Buckets:', [b['Name'] for b in s3.list_buckets()['Buckets']])
      "
EOF
```

## Security Considerations

⚠️ **Warning**: Disabling SSL verification reduces security by accepting invalid certificates.

**Only use `S3_SKIP_SSL_VERIFICATION=true` when:**

- Using development/testing environments
- Using MinIO with self-signed certificates
- Working in secure internal networks

**Never use for:**

- Production AWS S3
- Public internet endpoints
- Environments with sensitive data

## Migration Notes

### From Previous Versions

If you were previously experiencing SSL errors:

1. **Add to your pipeline parameters**:

   ```yaml
   s3_skip_ssl_verification: true
   ```

2. **No code changes needed**: All components automatically respect this setting

3. **Test thoroughly**: Verify all S3 operations work with your endpoint

### Backward Compatibility

- Default behavior unchanged (SSL verification enabled)
- Existing AWS S3 deployments unaffected
- New environment variable is optional
