# Troubleshooting 401 Unauthorized Errors

## Problem
When running the GitHub Release Monitor from a corporate network or CI/CD environment, you may encounter:
```
Failed to check kubernetes/kubernetes: 401 Client Error: Unauthorized for url: https://api.github.com/repos/kubernetes/kubernetes/releases/latest
```

## Common Causes and Solutions

### 1. Missing or Invalid GitHub Token

**Symptom**: 401 Unauthorized error on all API calls

**Solution**:
1. Verify the token is set in your Concourse pipeline:
   ```bash
   fly -t <target> get-pipeline -p github-release-monitor | grep github_token
   ```

2. Test the token manually:
   ```bash
   export GITHUB_TOKEN="your-token-here"
   ./scripts/test-github-auth.sh
   ```

3. Ensure the token is valid:
   - Go to https://github.com/settings/tokens
   - Verify your token is not expired
   - For public repos only: No special permissions needed
   - For private repos: Token needs `repo` scope

### 2. Token Format Issues

**Common mistakes**:
- Including "Bearer" prefix (use just the token)
- Extra spaces or newlines in the token
- Token being escaped incorrectly in pipeline YAML

**Correct format in Concourse**:
```yaml
# In your pipeline vars file:
github_token: ghp_xxxxxxxxxxxxxxxxxxxx

# NOT:
github_token: "Bearer ghp_xxxxxxxxxxxxxxxxxxxx"
github_token: "ghp_xxxxxxxxxxxxxxxxxxxx\n"
```

### 3. Corporate Proxy Configuration

**Symptom**: 401 or connection errors only in corporate network

**Solution**:
1. Set proxy environment variables in your pipeline:
   ```yaml
   params:
     GITHUB_TOKEN: ((github_token))
     HTTP_PROXY: ((http_proxy))
     HTTPS_PROXY: ((https_proxy))
     NO_PROXY: ((no_proxy))
   ```

2. Common proxy formats:
   ```bash
   HTTP_PROXY=http://proxy.company.com:8080
   HTTPS_PROXY=http://proxy.company.com:8080
   NO_PROXY=localhost,127.0.0.1,.company.com
   ```

### 4. Rate Limiting

**Symptom**: Works initially, then starts failing with 401/403

**Solution**:
1. Check your rate limit:
   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" \
        https://api.github.com/rate_limit
   ```

2. For authenticated requests: 5,000 requests/hour
3. Consider adding delays between API calls in config

### 5. Debugging in Concourse

Add debugging to your pipeline task:

```yaml
run:
  path: bash
  args:
    - -c
    - |
      # Debug environment
      echo "GitHub token length: ${#GITHUB_TOKEN}"
      echo "Proxy settings:"
      env | grep -i proxy || echo "No proxy configured"

      # Test API before running main script
      curl -v -H "Authorization: token $GITHUB_TOKEN" \
           https://api.github.com/user

      # Run main script
      ./scripts/monitor.sh --config config.yaml
```

### 6. Quick Test Script

Run this test script to diagnose issues:

```bash
#!/bin/bash
# Save as test-auth.sh and run

if [ -z "$GITHUB_TOKEN" ]; then
    echo "ERROR: Set GITHUB_TOKEN first"
    exit 1
fi

echo "Testing GitHub API..."
curl -s -f -H "Authorization: token $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github.v3+json" \
     https://api.github.com/user \
     && echo "✓ Authentication successful" \
     || echo "✗ Authentication failed"
```

## If All Else Fails

1. **Use the test script**: Run `./scripts/test-github-auth.sh` for comprehensive diagnostics
2. **Check Concourse worker logs**: Look for proxy or network errors
3. **Verify with IT**: Some corporate networks block GitHub API
4. **Try a different token**: Create a fresh token to rule out token issues
5. **Enable debug logging**: Set `DEBUG=true` in your pipeline

## Example Working Configuration

```yaml
# pipeline.yml
params:
  GITHUB_TOKEN: ((github_token))
  HTTP_PROXY: ((http_proxy))
  HTTPS_PROXY: ((https_proxy))
  NO_PROXY: localhost,127.0.0.1

# vars.yml
github_token: ghp_xxxxxxxxxxxxxxxxxxxx
http_proxy: http://corporate-proxy:8080
https_proxy: http://corporate-proxy:8080
```
