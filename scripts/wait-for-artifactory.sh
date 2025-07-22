#!/bin/bash
# Wait for Artifactory to be ready

set -e

ARTIFACTORY_URL="${1:-http://localhost:8081}"
MAX_WAIT="${2:-600}"  # 10 minutes
WAIT_INTERVAL=10

echo "⏳ Waiting for Artifactory to be ready at $ARTIFACTORY_URL..."
echo "   This can take 5-10 minutes on first startup..."

start_time=$(date +%s)
while true; do
    current_time=$(date +%s)
    elapsed=$((current_time - start_time))
    
    if [ $elapsed -gt $MAX_WAIT ]; then
        echo "❌ Timeout: Artifactory not ready after $MAX_WAIT seconds"
        echo "   Check logs: docker-compose -f docker-compose-artifactory.yml logs artifactory"
        exit 1
    fi
    
    # Try to connect to Artifactory
    if curl -s -f "$ARTIFACTORY_URL/" > /dev/null 2>&1; then
        echo "✅ Artifactory UI is responding!"
        
        # Try the API ping endpoint
        if curl -s -f "$ARTIFACTORY_URL/artifactory/api/system/ping" > /dev/null 2>&1; then
            echo "✅ Artifactory API is ready!"
            break
        else
            echo "⏳ UI ready, waiting for API... (${elapsed}s elapsed)"
        fi
    else
        echo "⏳ Waiting for Artifactory... (${elapsed}s elapsed)"
    fi
    
    sleep $WAIT_INTERVAL
done

echo ""
echo "🎉 Artifactory is ready!"
echo ""
echo "Next steps:"
echo "1. Visit: $ARTIFACTORY_URL"
echo "2. Login: admin / password"
echo "3. Complete setup wizard"
echo "4. Create 'generic-releases' repository"
echo "5. Generate API key"
echo ""