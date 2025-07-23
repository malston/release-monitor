# JFrog Artifactory Integration

The GitHub Release Monitor supports JFrog Artifactory as a storage backend for release artifacts and version tracking.

## 📖 Complete Documentation

**→ See [docs/ARTIFACTORY.md](docs/ARTIFACTORY.md) for the complete integration guide**

This single document covers everything you need:

- **Quick Start**: Get running in 5 minutes with Docker
- **Configuration**: Environment variables and settings
- **Download Scripts**: Retrieve releases from Artifactory
- **Pipeline Setup**: Concourse CI/CD integration
- **Troubleshooting**: Common issues and solutions

## 🚀 Quick Start

```bash
# 1. Start Artifactory
docker-compose -f docker-compose-artifactory.yml up -d
./scripts/wait-for-artifactory.sh

# 2. Complete setup at http://localhost:8081
# 3. Set environment variables
export ARTIFACTORY_URL="http://localhost:8081/artifactory"
export ARTIFACTORY_REPOSITORY="generic-releases"
export ARTIFACTORY_API_KEY="your-api-key"
export GITHUB_TOKEN="your-github-token"

# 4. Test the integration
python github_monitor.py --config ./config.yaml --download
./scripts/download-from-artifactory.sh --list
```

## 📂 Key Files

- `docs/ARTIFACTORY.md` - Complete integration guide
- `docker-compose-artifactory.yml` - Local development setup
- `scripts/download-from-artifactory.sh` - Download script (shell wrapper)
- `scripts/download-from-artifactory.py` - Download script (Python)
- `params/global-artifactory.yml` - Pipeline parameters
- `ci/pipeline-artifactory.yml` - Concourse pipeline

## 🔗 Alternative Storage

This project also supports:
- **AWS S3** - See main README.md
- **S3-Compatible** - MinIO, etc. (see S3 documentation)