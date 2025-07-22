#!/bin/bash
# Fix Artifactory master key generation issues

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Default to dev compose file
COMPOSE_FILE="docker-compose-artifactory-dev.yml"
CONTAINER_NAME="release-monitor-artifactory-dev"

# Check which container is running
if docker ps --format "{{.Names}}" | grep -q "release-monitor-artifactory-dev"; then
    COMPOSE_FILE="docker-compose-artifactory-dev.yml"
    CONTAINER_NAME="release-monitor-artifactory-dev"
elif docker ps --format "{{.Names}}" | grep -q "release-monitor-artifactory"; then
    COMPOSE_FILE="docker-compose-artifactory.yml"
    CONTAINER_NAME="release-monitor-artifactory"
else
    echo_error "No Artifactory container found running"
    echo_info "Start one with: docker-compose -f docker-compose-artifactory-dev.yml up -d"
    exit 1
fi

echo_info "🔧 Artifactory Master Key Fix Tool"
echo_info "=================================="
echo_info "Container: $CONTAINER_NAME"
echo ""

check_master_key_status() {
    echo_info "📊 Checking master key status..."
    
    # Check if master key exists in container
    if docker exec "$CONTAINER_NAME" test -f /var/opt/jfrog/artifactory/etc/security/master.key 2>/dev/null; then
        echo_success "Master key file exists"
        
        # Check if it's valid (not empty)
        key_size=$(docker exec "$CONTAINER_NAME" wc -c < /var/opt/jfrog/artifactory/etc/security/master.key 2>/dev/null || echo "0")
        if [ "$key_size" -gt 10 ]; then
            echo_success "Master key appears valid (${key_size} bytes)"
            return 0
        else
            echo_warning "Master key file exists but appears invalid/empty"
            return 1
        fi
    else
        echo_warning "Master key file not found"
        return 1
    fi
}

check_permissions() {
    echo_info "🔐 Checking permissions..."
    
    # Check if security directory exists
    if docker exec "$CONTAINER_NAME" test -d /var/opt/jfrog/artifactory/etc/security 2>/dev/null; then
        echo_success "Security directory exists"
    else
        echo_warning "Security directory missing, creating..."
        docker exec "$CONTAINER_NAME" mkdir -p /var/opt/jfrog/artifactory/etc/security
    fi
    
    # Check ownership and permissions
    owner=$(docker exec "$CONTAINER_NAME" ls -ld /var/opt/jfrog/artifactory/etc/security | awk '{print $3":"$4}')
    perms=$(docker exec "$CONTAINER_NAME" ls -ld /var/opt/jfrog/artifactory/etc/security | awk '{print $1}')
    
    echo_info "Directory owner: $owner"
    echo_info "Directory permissions: $perms"
    
    # Fix ownership if needed
    echo_info "Setting correct ownership..."
    docker exec "$CONTAINER_NAME" chown -R artifactory:artifactory /var/opt/jfrog/artifactory/etc/security
    docker exec "$CONTAINER_NAME" chmod 750 /var/opt/jfrog/artifactory/etc/security
}

generate_master_key() {
    echo_info "🔑 Generating new master key..."
    
    # Generate a 32-character hexadecimal key (16 bytes)
    master_key=$(openssl rand -hex 16)
    
    if [ -z "$master_key" ]; then
        echo_error "Failed to generate master key"
        return 1
    fi
    
    echo_info "Generated key: ${master_key:0:8}... (truncated for security)"
    
    # Write key to container
    echo "$master_key" | docker exec -i "$CONTAINER_NAME" tee /var/opt/jfrog/artifactory/etc/security/master.key > /dev/null
    
    # Set correct permissions
    docker exec "$CONTAINER_NAME" chown artifactory:artifactory /var/opt/jfrog/artifactory/etc/security/master.key
    docker exec "$CONTAINER_NAME" chmod 640 /var/opt/jfrog/artifactory/etc/security/master.key
    
    echo_success "Master key generated and installed"
}

restart_artifactory() {
    echo_info "🔄 Restarting Artifactory..."
    
    cd "$PROJECT_ROOT"
    
    # Restart the container
    docker-compose -f "$COMPOSE_FILE" restart artifactory
    
    echo_success "Artifactory restarted"
    echo_info "Allow 2-3 minutes for services to initialize"
}

monitor_startup() {
    echo_info "📋 Monitoring startup progress..."
    
    # Wait a moment for restart
    sleep 10
    
    max_wait=180  # 3 minutes
    wait_interval=10
    elapsed=0
    
    while [ $elapsed -lt $max_wait ]; do
        # Check if UI is responding
        if curl -s -f "http://localhost:8081/" > /dev/null 2>&1; then
            echo_success "UI is responding!"
            
            # Check if setup wizard is available
            if curl -s "http://localhost:8081/artifactory/webapp/" | grep -q "setup\|login"; then
                echo_success "Setup wizard is ready!"
                echo_info "🎉 Visit: http://localhost:8081"
                return 0
            fi
        fi
        
        echo_info "⏳ Still starting... (${elapsed}s elapsed)"
        sleep $wait_interval
        elapsed=$((elapsed + wait_interval))
    done
    
    echo_warning "Startup taking longer than expected"
    echo_info "Check logs: docker-compose -f $COMPOSE_FILE logs artifactory"
}

show_logs() {
    echo_info "📝 Recent logs (last 20 lines):"
    echo ""
    docker-compose -f "$COMPOSE_FILE" logs --tail 20 artifactory
}

main() {
    # Check if container is running
    if ! docker ps --format "{{.Names}}" | grep -q "$CONTAINER_NAME"; then
        echo_error "Container $CONTAINER_NAME is not running"
        echo_info "Start it with: docker-compose -f $COMPOSE_FILE up -d"
        exit 1
    fi
    
    # Check current status
    if check_master_key_status; then
        echo_info "Master key looks good. The issue might be elsewhere."
        echo_info "Check current status:"
        ./check-artifactory-ready.sh
        return
    fi
    
    echo_warning "Master key issue detected. Attempting fix..."
    echo ""
    
    # Fix permissions first
    check_permissions
    
    # Generate new master key
    generate_master_key
    
    # Restart Artifactory
    restart_artifactory
    
    # Monitor startup
    monitor_startup
    
    echo ""
    echo_success "🎉 Master key fix completed!"
    echo_info "If issues persist, check logs:"
    echo_info "  docker-compose -f $COMPOSE_FILE logs artifactory"
}

# Handle command line arguments
case "${1:-}" in
    check)
        check_master_key_status
        ;;
    generate)
        check_permissions
        generate_master_key
        echo_info "Master key generated. Restart Artifactory to use it:"
        echo_info "  docker-compose -f $COMPOSE_FILE restart artifactory"
        ;;
    restart)
        restart_artifactory
        monitor_startup
        ;;
    logs)
        show_logs
        ;;
    help|--help|-h)
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  (none)    Full fix process"
        echo "  check     Check master key status"
        echo "  generate  Generate new master key only"
        echo "  restart   Restart and monitor"
        echo "  logs      Show recent logs"
        echo "  help      Show this help"
        ;;
    *)
        main
        ;;
esac