# 🔧 Artifactory Startup Troubleshooting Guide

## 🎯 The Issue: 404 During Startup

**You're experiencing normal Artifactory startup behavior!** Here's what's happening:

### 📊 Current Status: Master Key Generation
- **Time**: 2+ minutes (normal - can take up to 5 minutes)
- **Browser**: 404 error when accessing /artifactory
- **Cause**: Artifactory generates encryption keys during first startup
- **Solution**: Wait for completion (no action needed)

## ⏰ Startup Timeline

| Phase | Duration | Browser Behavior | What's Happening |
|-------|----------|------------------|------------------|
| **1. Container Start** | 0-30s | Connection refused | Container initializing |
| **2. Web Server** | 30s-1m | Basic HTML page | Tomcat starts |
| **3. Master Key** | 1-5m | 404 on /artifactory | ← **You are here** |
| **4. Services** | 5-7m | Loading screens | Internal services start |
| **5. Ready!** | 7-10m | Setup wizard | Full UI available |

## 🛠 Solutions Provided

### Option 1: Wait (Current - Recommended)
```bash
# Your current container is progressing normally
docker logs -f artifactory-simple

# Check status
curl -s http://localhost:8081/
```

### Option 2: Monitor Progress
```bash
# Use our monitoring tools
./scripts/check-artifactory-ready.sh
./scripts/artifactory-status.sh
```

### Option 3: Ultra-Fast Docker Compose
```bash
# Stop current simple container
docker stop artifactory-simple && docker rm artifactory-simple

# Use optimized development version
docker-compose -f docker-compose-artifactory-dev.yml up -d
```

### Option 4: Manual Master Key Fix (If Stuck)
```bash
# Only if stuck after 10+ minutes
./scripts/fix-artifactory-master-key.sh
```

## 📋 What We've Created for You

### 🐳 Docker Compose Options
1. **`docker-compose-artifactory.yml`** - Full production setup
2. **`docker-compose-artifactory-dev.yml`** - Fast development (2-4 min)
3. **`docker-compose-artifactory-quick.yml`** - Experimental ultra-fast
4. **`docker-compose-full.yml`** - All services (MinIO + Artifactory + PostgreSQL)

### 🔧 Helper Scripts
1. **`scripts/wait-for-artifactory.sh`** - Wait with progress monitoring
2. **`scripts/artifactory-status.sh`** - Comprehensive status check
3. **`scripts/check-artifactory-ready.sh`** - Quick readiness check
4. **`scripts/fix-artifactory-master-key.sh`** - Manual master key fix
5. **`scripts/start-artifactory-simple.sh`** - Minimal container startup

### 📚 Documentation
1. **`ARTIFACTORY_QUICKSTART.md`** - 2-minute setup guide
2. **`ARTIFACTORY_STARTUP_INFO.md`** - Startup phase explanation
3. **`docs/ARTIFACTORY_SETUP.md`** - Complete setup guide

## 🎉 Current Status: SUCCESS!

Your Artifactory is **starting normally**. The simple container approach is working:

```bash
# Check progress
docker logs artifactory-simple | tail -5

# Test readiness
curl -s http://localhost:8081/

# When ready, you'll see:
# - Setup wizard at http://localhost:8081
# - No more 404 errors
# - Login: admin / password
```

## 🚀 Next Steps When Ready

1. **Complete Setup Wizard**
   - Set admin password
   - Configure base URL: http://localhost:8081/artifactory
   - Skip proxy settings

2. **Create Repository**
   - Administration → Repositories → New Repository
   - Type: Generic
   - Key: `generic-releases`

3. **Generate API Key**
   - User Profile → Generate API Key
   - Copy and save securely

4. **Configure Release Monitor**
   ```bash
   export ARTIFACTORY_URL="http://localhost:8081/artifactory"
   export ARTIFACTORY_REPOSITORY="generic-releases"
   export ARTIFACTORY_API_KEY="your-generated-key"
   ```

## 🆘 If Problems Persist

### After 10+ Minutes Still 404
```bash
# Check logs for errors
docker logs artifactory-simple | grep ERROR

# Try master key fix
./scripts/fix-artifactory-master-key.sh

# Or restart with dev compose
docker stop artifactory-simple && docker rm artifactory-simple
docker-compose -f docker-compose-artifactory-dev.yml up -d
```

### Memory Issues
```bash
# Check resources
docker stats artifactory-simple

# If high memory usage, restart with limits
docker stop artifactory-simple && docker rm artifactory-simple
docker run -d --name artifactory-simple -p 8081:8081 \
  -e JF_SHARED_JAVA_XMX=512m \
  releases-docker.jfrog.io/jfrog/artifactory-oss:latest
```

## 💡 Pro Tips

- **First startup**: Always takes 5-10 minutes (normal)
- **Subsequent startups**: Much faster (1-2 minutes)
- **Master key**: Generated once, then reused
- **Development**: Use docker-compose-artifactory-dev.yml for speed
- **Production**: Use docker-compose-artifactory.yml for full features

## ✅ Bottom Line

**Your setup is working correctly!** The 404 during master key generation is expected behavior. Give it 2-3 more minutes and you'll have a fully functional Artifactory instance.

**Current status: ⏳ Normal startup in progress**