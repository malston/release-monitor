# 🚀 Artifactory Startup Guide

## ❓ Getting 404 Error at http://localhost:8081?

**This is completely normal!** Here's what's happening:

### 🔐 Phase 1: Master Key Generation (Current)
- **What**: Artifactory is generating encryption keys for security
- **Time**: 2-5 minutes (can be longer on slower systems)  
- **Browser**: Shows 404 or redirects to /artifactory
- **Status**: Master key generation in progress

### 🏗️ Phase 2: Service Initialization  
- **What**: Internal services (access, metadata, frontend) start
- **Time**: 1-2 minutes
- **Browser**: May show loading screens or partial UI

### ✅ Phase 3: Ready!
- **What**: Full Artifactory UI loads
- **Browser**: Setup wizard appears
- **URL**: http://localhost:8081
- **Login**: admin / password

## 📊 Check Current Status

```bash
# Quick status check
./scripts/check-artifactory-ready.sh

# Detailed status with troubleshooting
./scripts/artifactory-status.sh

# Wait automatically (with progress)
./scripts/wait-for-artifactory.sh
```

## ⏱️ Timeline Expectations

| Time | Status | Browser Behavior |
|------|--------|------------------|
| 0-2 min | Container starting | Connection refused |
| 2-5 min | Master key generation | 404 or redirect ← **You are here** |
| 5-7 min | Services initializing | Loading screens |
| 7-10 min | Ready! | Setup wizard |

## 🔍 What to Do Right Now

### Option 1: Wait (Recommended)
```bash
# Just wait - it's working fine!
./scripts/wait-for-artifactory.sh
```

### Option 2: Monitor Progress
```bash
# Watch the logs in real-time
docker-compose -f docker-compose-artifactory-dev.yml logs -f artifactory

# Look for: "Started Artifactory" or "Setup wizard"
```

### Option 3: Check Status
```bash
# Quick status check
./scripts/check-artifactory-ready.sh

# When ready, you'll see: "Artifactory should be ready!"
```

## 🚨 Only Worry If...

- **10+ minutes** with no progress
- **Out of memory** errors in logs  
- **Container stops** or restarts

## ⚡ Faster Alternative

If you're impatient, you can restart with an even more minimal setup:

```bash
# Stop current
docker-compose -f docker-compose-artifactory-dev.yml down

# Try with less memory (if system is limited)
docker run -d --name artifactory-minimal \
  -p 8081:8081 \
  -e JF_SHARED_JAVA_XMX=1g \
  -e JF_SHARED_DATABASE_TYPE=derby \
  releases-docker.jfrog.io/jfrog/artifactory-oss:latest
```

## 🎯 Bottom Line

**Your Artifactory is starting normally!** The 404 is expected during master key generation. Give it 2-5 more minutes and you'll see the setup wizard.

☕ Perfect time for a coffee break!