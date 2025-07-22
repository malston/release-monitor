#!/bin/bash
# Simple Artifactory startup with minimal configuration

set -e

echo "🚀 Starting Artifactory with minimal configuration..."
echo ""

# Stop any existing containers
echo "🧹 Cleaning up existing containers..."
docker-compose -f docker-compose-artifactory-quick.yml down -v 2>/dev/null || true
docker-compose -f docker-compose-artifactory-dev.yml down -v 2>/dev/null || true
docker-compose -f docker-compose-artifactory.yml down -v 2>/dev/null || true

# Remove any stopped containers
docker rm -f $(docker ps -aq --filter name=artifactory) 2>/dev/null || true

echo "✅ Cleanup complete"
echo ""

echo "🏃 Starting minimal Artifactory..."

# Start with the most basic configuration
docker run -d \
  --name artifactory-simple \
  -p 8081:8081 \
  -e JF_SHARED_JAVA_XMX=1g \
  -e JF_SHARED_DATABASE_TYPE=derby \
  -e JF_SHARED_NODE_HAENABLED=false \
  -e JF_ROUTER_LOGGING_LEVEL=WARN \
  --restart unless-stopped \
  releases-docker.jfrog.io/jfrog/artifactory-oss:latest

echo "✅ Container started"
echo ""

echo "⏳ Waiting for Artifactory to initialize..."
echo "   This will take 3-5 minutes..."
echo ""

# Monitor startup
max_wait=300  # 5 minutes
wait_interval=15
elapsed=0

while [ $elapsed -lt $max_wait ]; do
    if curl -s -f "http://localhost:8081/" > /dev/null 2>&1; then
        echo "✅ Web server responding!"
        
        # Check if we can access the setup
        if curl -s "http://localhost:8081/artifactory/webapp/" | grep -q -E "(setup|login|artifactory)"; then
            echo "🎉 Artifactory is ready!"
            echo ""
            echo "📋 Next steps:"
            echo "1. Visit: http://localhost:8081"
            echo "2. Login: admin / password"
            echo "3. Complete setup wizard"
            echo "4. Create repository: generic-releases"
            echo ""
            break
        else
            echo "⏳ Still initializing... (${elapsed}s elapsed)"
        fi
    else
        echo "⏳ Starting up... (${elapsed}s elapsed)"
    fi
    
    sleep $wait_interval
    elapsed=$((elapsed + wait_interval))
done

if [ $elapsed -ge $max_wait ]; then
    echo "⚠️  Startup taking longer than expected"
    echo "📊 Check logs: docker logs artifactory-simple"
    echo "🔧 Status: docker ps"
fi

echo ""
echo "🆘 Useful commands:"
echo "  Check status: docker ps"
echo "  View logs:    docker logs -f artifactory-simple"
echo "  Stop:         docker stop artifactory-simple"
echo "  Remove:       docker rm -f artifactory-simple"