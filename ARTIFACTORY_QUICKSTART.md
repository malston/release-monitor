# JFrog Artifactory Quick Start Guide

## 🚀 Get Artifactory Running in 2 Minutes

### 1. Start Artifactory

```bash
# Option A: Fast development setup (recommended for testing)
docker-compose -f docker-compose-artifactory-dev.yml up -d

# Option B: Full production setup
docker-compose -f docker-compose-artifactory.yml up -d

# Wait for it to be ready
./scripts/wait-for-artifactory.sh

# Check status anytime
./scripts/artifactory-status.sh
```

### 2. Complete Setup Wizard

1. **Open Artifactory**: http://localhost:8081
2. **Login**: `admin` / `password`  
3. **Set New Password**: Choose a secure password
4. **Base URL**: Set to `http://localhost:8081/artifactory`
5. **Proxy**: Skip proxy configuration
6. **Create Repository**: 
   - Go to Administration → Repositories → Repositories
   - New Repository → Generic → Repository Key: `generic-releases`
   - Save & Finish

### 3. Generate API Key

1. **User Menu** → Generate API Key
2. **Copy** the generated key
3. **Save** it securely

### 4. Configure Release Monitor

```bash
# Using API Key (recommended)
export ARTIFACTORY_URL="http://localhost:8081/artifactory"
export ARTIFACTORY_REPOSITORY="generic-releases"  
export ARTIFACTORY_API_KEY="your-generated-api-key"

# OR using username/password
export ARTIFACTORY_URL="http://localhost:8081/artifactory"
export ARTIFACTORY_REPOSITORY="generic-releases"
export ARTIFACTORY_USERNAME="admin"
export ARTIFACTORY_PASSWORD="your-new-password"

# GitHub token (required)
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"
```

### 5. Test the Integration

```bash
# Test connection
python3 -c "
from github_version_artifactory import ArtifactoryVersionDatabase
import os
db = ArtifactoryVersionDatabase(
    base_url=os.environ['ARTIFACTORY_URL'],
    repository=os.environ['ARTIFACTORY_REPOSITORY']
)
print('✅ Connection successful!')
print('Version database:', db.load_versions())
"

# Run release monitor
python3 github_monitor.py

# Download releases  
python3 download_releases.py
```

## 🛠 Troubleshooting

### Artifactory Not Starting
- **Check logs**: `docker-compose -f docker-compose-artifactory.yml logs artifactory`
- **Wait longer**: First startup takes 5-10 minutes
- **Check memory**: Artifactory needs at least 2GB RAM

### Setup Wizard Not Loading
- **Clear browser cache** and try again
- **Try**: http://localhost:8081/ui/
- **Wait**: API might still be initializing

### Connection Errors
- **Repository exists**: Make sure `generic-releases` repository is created
- **Credentials**: Verify API key or username/password
- **URL format**: Should end with `/artifactory` (no trailing slash)

## 🔧 Useful Commands

```bash
# Check container status
docker-compose -f docker-compose-artifactory.yml ps

# View logs
docker-compose -f docker-compose-artifactory.yml logs -f artifactory

# Restart Artifactory
docker-compose -f docker-compose-artifactory.yml restart artifactory

# Stop and remove (keeps data)
docker-compose -f docker-compose-artifactory.yml down

# Stop and remove ALL data (⚠️  Destructive!)
docker-compose -f docker-compose-artifactory.yml down -v
```

## 🎯 Quick Test

Once setup is complete, test with a simple repository:

```bash
# Add test repository to config
export REPOSITORIES_OVERRIDE='[{"owner": "etcd-io", "repo": "etcd", "description": "etcd test"}]'

# Run monitor (should detect latest etcd release)
python3 github_monitor.py

# Check Artifactory for version database
curl -u admin:your-password http://localhost:8081/artifactory/generic-releases/release-monitor/version_db.json
```

## 📋 What's Next?

- **Pipeline Setup**: Deploy Concourse pipeline with Artifactory backend
- **Production**: Use PostgreSQL instead of embedded Derby database  
- **SSL**: Configure HTTPS for production deployments
- **Backup**: Set up automated backups for Artifactory data

For detailed configuration options, see [docs/ARTIFACTORY_SETUP.md](docs/ARTIFACTORY_SETUP.md).