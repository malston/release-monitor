#!/bin/bash
# Simple check script to see if Artifactory web interface is ready

URL="http://localhost:8081"

echo "🔍 Checking Artifactory readiness..."
echo ""

# Test different endpoints to determine status
echo "📊 Endpoint Tests:"

# Test root
if curl -s "$URL/" | grep -q "html"; then
    echo "   ✅ Web server responding"
else
    echo "   ❌ Web server not responding"
    exit 1
fi

# Test if we get redirect to /artifactory
response=$(curl -s -w "%{http_code}" -o /dev/null "$URL/")
if [ "$response" = "200" ]; then
    echo "   ✅ Main page loads"
elif [ "$response" = "302" ] || [ "$response" = "301" ]; then
    echo "   ⏳ Redirecting (still initializing)"
else
    echo "   ⚠️  Unexpected response: $response"
fi

# Test artifactory endpoint directly
artifactory_response=$(curl -s -w "%{http_code}" -o /dev/null "$URL/artifactory/")
if [ "$artifactory_response" = "200" ]; then
    echo "   ✅ Artifactory app responding"
elif [ "$artifactory_response" = "404" ]; then
    echo "   ⏳ Artifactory app still loading (404 - normal)"
else
    echo "   ⚠️  Artifactory response: $artifactory_response"
fi

# Check for setup wizard
if curl -s "$URL/ui/" | grep -q "setup\|login\|artifactory"; then
    echo "   ✅ UI framework loaded"
else
    echo "   ⏳ UI still loading"
fi

echo ""

# Provide status summary
if [ "$artifactory_response" = "404" ]; then
    echo "📋 Status: Master key generation in progress"
    echo "⏰ Expected: 2-5 more minutes"
    echo "🔗 Try again: $URL"
    echo ""
    echo "💡 What's happening:"
    echo "   - Master encryption key being generated"
    echo "   - Security services initializing"
    echo "   - Database being prepared"
    echo ""
    echo "🆘 If this persists after 10 minutes:"
    echo "   docker-compose -f docker-compose-artifactory-dev.yml logs artifactory"
else
    echo "🎉 Artifactory should be ready!"
    echo "🔗 Visit: $URL"
fi