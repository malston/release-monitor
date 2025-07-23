#!/bin/bash
set -e

# =============================================================================
# JFrog Artifactory OSS Local Setup Script
# =============================================================================
# This script helps set up a local JFrog Artifactory OSS instance for
# testing the GitHub Release Monitor with Artifactory backend.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose-artifactory.yml"
ARTIFACTORY_URL="http://localhost:8081"
REPOSITORY_NAME="generic-local"

echo_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

echo_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

echo_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

echo_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_prerequisites() {
    echo_info "Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        echo_error "Docker is required but not installed."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo_error "Docker Compose is required but not installed."
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        echo_error "Docker daemon is not running."
        exit 1
    fi
    
    echo_success "Prerequisites check passed"
}

start_artifactory() {
    echo_info "Starting JFrog Artifactory OSS..."
    
    cd "$PROJECT_ROOT"
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        echo_error "Docker compose file not found: $COMPOSE_FILE"
        exit 1
    fi
    
    # Start Artifactory
    docker-compose -f "$COMPOSE_FILE" up -d artifactory
    
    echo_info "Waiting for Artifactory to start (this may take 2-3 minutes)..."
    
    # Wait for Artifactory to be ready
    max_attempts=60
    attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "$ARTIFACTORY_URL/artifactory/api/system/ping" > /dev/null 2>&1; then
            break
        fi
        
        echo -n "."
        sleep 5
        attempt=$((attempt + 1))
    done
    echo ""
    
    if [ $attempt -gt $max_attempts ]; then
        echo_error "Artifactory failed to start within expected time"
        echo_info "Check logs: docker-compose -f $COMPOSE_FILE logs artifactory"
        exit 1
    fi
    
    echo_success "Artifactory is running!"
}

show_setup_instructions() {
    echo ""
    echo_info "=== JFrog Artifactory Setup Instructions ==="
    echo ""
    echo "1. 🌐 Access Artifactory Web UI:"
    echo "   ${BLUE}$ARTIFACTORY_URL${NC}"
    echo ""
    echo "2. 🔑 Login with default credentials:"
    echo "   Username: ${YELLOW}admin${NC}"
    echo "   Password: ${YELLOW}password${NC}"
    echo ""
    echo "3. 🛠️  Complete the setup wizard:"
    echo "   - Set a new admin password"
    echo "   - Configure base URL: $ARTIFACTORY_URL/artifactory"
    echo "   - Skip proxy settings for local development"
    echo ""
    echo "4. 📦 Create a Generic repository:"
    echo "   - Go to Administration > Repositories > Repositories"
    echo "   - Click 'New Repository' > 'Generic'"
    echo "   - Repository Key: ${YELLOW}$REPOSITORY_NAME${NC}"
    echo "   - Click 'Save & Finish'"
    echo ""
    echo "5. 🔐 Generate an API Key (Recommended):"
    echo "   - Go to User Profile > Generate API Key"
    echo "   - Copy the generated key"
    echo ""
}

show_configuration() {
    echo_info "=== Release Monitor Configuration ==="
    echo ""
    echo "Add these environment variables:"
    echo ""
    echo "export ARTIFACTORY_URL=\"$ARTIFACTORY_URL/artifactory\""
    echo "export ARTIFACTORY_REPOSITORY=\"$REPOSITORY_NAME\""
    echo ""
    echo "Option 1 - API Key (Recommended):"
    echo "export ARTIFACTORY_API_KEY=\"your-generated-api-key\""
    echo ""
    echo "Option 2 - Username/Password:"
    echo "export ARTIFACTORY_USERNAME=\"admin\""
    echo "export ARTIFACTORY_PASSWORD=\"your-password\""
    echo ""
}

test_connection() {
    echo_info "Testing connection to Artifactory..."
    
    if curl -s -f "$ARTIFACTORY_URL/artifactory/api/system/ping" > /dev/null; then
        echo_success "Artifactory is responding to API calls"
    else
        echo_error "Cannot connect to Artifactory API"
        return 1
    fi
    
    # Test with Python if available
    if command -v python3 &> /dev/null; then
        echo_info "Testing Python integration..."
        
        cat > /tmp/test_artifactory.py << 'EOF'
import sys
import os
sys.path.insert(0, '.')

try:
    from github_version_artifactory import ArtifactoryVersionDatabase
    
    # Use dummy credentials for connection test
    db = ArtifactoryVersionDatabase(
        base_url=os.environ.get('ARTIFACTORY_URL', 'http://localhost:8081/artifactory'),
        repository=os.environ.get('ARTIFACTORY_REPOSITORY', 'generic-local'),
        username='admin',
        password='password',
        verify_ssl=False
    )
    
    # This will fail if repository doesn't exist, but connection should work
    try:
        data = db.load_versions()
        print("✅ Python integration test successful")
    except Exception as e:
        if "404" in str(e):
            print("⚠️  Connection works, but repository 'generic-local' not found")
            print("   Please create the repository as described above")
        else:
            print(f"❌ Python test failed: {e}")
            
except ImportError:
    print("⚠️  Python integration test skipped (github_version_artifactory not available)")
except Exception as e:
    print(f"❌ Python test failed: {e}")
EOF
        
        cd "$PROJECT_ROOT"
        python3 /tmp/test_artifactory.py 2>/dev/null || echo_warning "Python test encountered issues"
        rm -f /tmp/test_artifactory.py
    fi
}

show_status() {
    echo_info "=== Service Status ==="
    
    cd "$PROJECT_ROOT"
    docker-compose -f "$COMPOSE_FILE" ps
    
    echo ""
    echo_info "=== Useful Commands ==="
    echo ""
    echo "View logs:"
    echo "  docker-compose -f $COMPOSE_FILE logs -f artifactory"
    echo ""
    echo "Stop Artifactory:"
    echo "  docker-compose -f $COMPOSE_FILE down"
    echo ""
    echo "Remove all data:"
    echo "  docker-compose -f $COMPOSE_FILE down -v"
    echo ""
    echo "Access container:"
    echo "  docker exec -it release-monitor-artifactory bash"
    echo ""
}

main() {
    echo_info "🏺 JFrog Artifactory OSS Local Setup"
    echo_info "===================================="
    echo ""
    
    check_prerequisites
    start_artifactory
    show_setup_instructions
    show_configuration
    test_connection
    show_status
    
    echo ""
    echo_success "Setup complete! Artifactory is ready for use."
    echo_info "Visit $ARTIFACTORY_URL to complete the initial setup."
}

# Handle command line arguments
case "${1:-}" in
    start)
        check_prerequisites
        start_artifactory
        echo_success "Artifactory started"
        ;;
    stop)
        cd "$PROJECT_ROOT"
        docker-compose -f "$COMPOSE_FILE" down
        echo_success "Artifactory stopped"
        ;;
    restart)
        cd "$PROJECT_ROOT"
        docker-compose -f "$COMPOSE_FILE" restart artifactory
        echo_success "Artifactory restarted"
        ;;
    logs)
        cd "$PROJECT_ROOT"
        docker-compose -f "$COMPOSE_FILE" logs -f artifactory
        ;;
    status)
        cd "$PROJECT_ROOT"
        docker-compose -f "$COMPOSE_FILE" ps
        test_connection
        ;;
    clean)
        cd "$PROJECT_ROOT"
        docker-compose -f "$COMPOSE_FILE" down -v
        echo_success "Artifactory stopped and data removed"
        ;;
    help|--help|-h)
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  (none)    Full setup with instructions"
        echo "  start     Start Artifactory"
        echo "  stop      Stop Artifactory"
        echo "  restart   Restart Artifactory"
        echo "  logs      Show Artifactory logs"
        echo "  status    Show status and test connection"
        echo "  clean     Stop and remove all data"
        echo "  help      Show this help"
        ;;
    *)
        main
        ;;
esac