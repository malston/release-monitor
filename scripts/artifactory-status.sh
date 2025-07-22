#!/bin/bash
# Check Artifactory status and provide troubleshooting information

set -e

ARTIFACTORY_URL="${1:-http://localhost:8081}"

echo "🔍 Artifactory Status Check"
echo "=========================="
echo ""

# Check if container is running
echo "📦 Container Status:"
if command -v docker &> /dev/null; then
    if docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(artifactory|release-monitor-artifactory)"; then
        echo "   ✅ Container is running"
    else
        echo "   ❌ Container not found or not running"
        echo ""
        echo "🔧 Troubleshooting:"
        echo "   - Start: docker-compose -f docker-compose-artifactory.yml up -d"
        echo "   - Logs:  docker-compose -f docker-compose-artifactory.yml logs artifactory"
        exit 1
    fi
else
    echo "   ⚠️  Docker command not available"
fi

echo ""

# Check UI accessibility
echo "🌐 UI Accessibility:"
if curl -s -f "$ARTIFACTORY_URL/" > /dev/null 2>&1; then
    echo "   ✅ UI is accessible at $ARTIFACTORY_URL"
else
    echo "   ❌ UI not accessible"
    echo "   🔧 Try: curl -v $ARTIFACTORY_URL"
fi

echo ""

# Check API status
echo "🔌 API Status:"
if curl -s -f "$ARTIFACTORY_URL/artifactory/api/system/ping" > /dev/null 2>&1; then
    echo "   ✅ API is responding"
    
    # Get system version
    version=$(curl -s "$ARTIFACTORY_URL/artifactory/api/system/version" | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
    if [ -n "$version" ]; then
        echo "   📊 Version: $version"
    fi
else
    echo "   ⏳ API not ready yet (normal during startup)"
fi

echo ""

# Check setup wizard status
echo "⚙️  Setup Status:"
setup_response=$(curl -s "$ARTIFACTORY_URL/artifactory/ui/")
if echo "$setup_response" | grep -q "setup"; then
    echo "   📋 Setup wizard is available"
    echo "   🔗 Visit: $ARTIFACTORY_URL"
    echo "   🔑 Default login: admin / password"
elif echo "$setup_response" | grep -q "login"; then
    echo "   ✅ Setup completed, login page available"
else
    echo "   ⏳ Setup wizard not ready yet"
fi

echo ""

# Show memory usage if container is running
echo "💾 Resource Usage:"
if command -v docker &> /dev/null; then
    container_id=$(docker ps -q --filter name=artifactory)
    if [ -n "$container_id" ]; then
        echo "   📊 Memory usage:"
        docker stats --no-stream --format "   {{.MemUsage}} ({{.MemPerc}})" "$container_id"
        echo "   📊 CPU usage:"
        docker stats --no-stream --format "   {{.CPUPerc}}" "$container_id"
    fi
fi

echo ""

# Check logs for common issues
echo "📋 Recent Log Analysis:"
if command -v docker &> /dev/null; then
    container_id=$(docker ps -q --filter name=artifactory)
    if [ -n "$container_id" ]; then
        # Check for common startup messages
        recent_logs=$(docker logs --tail 50 "$container_id" 2>&1)
        
        if echo "$recent_logs" | grep -q "Master key is missing"; then
            echo "   ⏳ Still initializing master key (normal)"
        fi
        
        if echo "$recent_logs" | grep -q "Connection refused"; then
            echo "   ⏳ Internal services still starting (normal)"
        fi
        
        if echo "$recent_logs" | grep -q "Started Artifactory"; then
            echo "   ✅ Artifactory has started successfully"
        fi
        
        if echo "$recent_logs" | grep -q "OutOfMemoryError"; then
            echo "   ❌ Out of memory error detected!"
            echo "   🔧 Try: docker-compose -f docker-compose-artifactory-dev.yml up -d"
        fi
        
        if echo "$recent_logs" | grep -q "ERROR"; then
            echo "   ⚠️  Errors detected in logs"
            echo "   🔧 Check: docker-compose -f docker-compose-artifactory.yml logs artifactory"
        fi
    fi
fi

echo ""

# Provide recommendations
echo "💡 Recommendations:"
if ! curl -s -f "$ARTIFACTORY_URL/artifactory/api/system/ping" > /dev/null 2>&1; then
    echo "   ⏰ Artifactory typically takes 5-10 minutes to fully start"
    echo "   📊 Monitor progress: docker-compose -f docker-compose-artifactory.yml logs -f artifactory"
    echo "   ⚡ For faster startup: docker-compose -f docker-compose-artifactory-dev.yml up -d"
fi

if curl -s -f "$ARTIFACTORY_URL/" > /dev/null 2>&1; then
    echo "   🎯 UI is ready - you can proceed with setup!"
    echo "   📋 Next: Complete setup wizard at $ARTIFACTORY_URL"
fi

echo ""
echo "🆘 Need Help?"
echo "   📚 Quick Start: cat ARTIFACTORY_QUICKSTART.md"
echo "   📖 Full Guide: cat docs/ARTIFACTORY_SETUP.md"
echo "   🔧 Wait Script: ./scripts/wait-for-artifactory.sh"