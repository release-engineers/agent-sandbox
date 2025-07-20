#!/usr/bin/env bash

set -euo pipefail

# Configuration
IMAGE_NAME="claude-code-agent"
PROXY_IMAGE_NAME="claude-code-proxy"
PROXY_CONTAINER_NAME="container-proxy.local"
NETWORK_NAME="agent-network"
CONTAINER_NAME="${1:-claude-code-agent}"

# Validate git project and set workspace to git root
validate_git_project() {
    local git_root
    git_root="$(git rev-parse --show-toplevel 2>/dev/null)"
    
    if [[ -z "$git_root" ]]; then
        echo "Not a git repository" >&2
        exit 1
    fi
    
    WORKSPACE_DIR="$git_root"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Docker is not running" >&2
    exit 1
fi

# Build the Docker images
build_images() {
    local script_dir
    script_dir="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
    local dockerfile_agent_path="$script_dir/../Dockerfile.agent"
    local dockerfile_proxy_path="$script_dir/../Dockerfile.proxy"
    
    if [[ ! -f "$dockerfile_agent_path" ]]; then
        echo "Error: Dockerfile.agent not found at $dockerfile_agent_path" >&2
        exit 1
    fi
    
    if [[ ! -f "$dockerfile_proxy_path" ]]; then
        echo "Error: Dockerfile.proxy not found at $dockerfile_proxy_path" >&2
        exit 1
    fi
    
    # Build proxy image
    echo "Building proxy image..."
    docker build -t "$PROXY_IMAGE_NAME" -f "$dockerfile_proxy_path" "$script_dir/.."
    
    # Build agent image
    echo "Building agent image..."
    docker build -t "$IMAGE_NAME" -f "$dockerfile_agent_path" "$script_dir/.."
}

# Create restricted network
create_network() {
    # Skip if network already exists
    if docker network inspect "$NETWORK_NAME" > /dev/null 2>&1; then
        echo "Network $NETWORK_NAME already exists"
        return 0
    fi
    
    echo "Creating network $NETWORK_NAME..."
    # Create isolated network (internal - no external access)
    docker network create "$NETWORK_NAME" \
        --internal \
        --driver bridge \
        --subnet 172.20.0.0/16 \
        --gateway 172.20.0.1
}

# Start the proxy container
start_proxy_container() {
    # Skip if proxy container already exists
    if docker ps -a --filter "name=$PROXY_CONTAINER_NAME" --format "{{.Names}}" | grep -q "^$PROXY_CONTAINER_NAME$"; then
        if ! docker ps --filter "name=$PROXY_CONTAINER_NAME" --format "{{.Names}}" | grep -q "^$PROXY_CONTAINER_NAME$"; then
            echo "Starting existing proxy container..."
            docker start "$PROXY_CONTAINER_NAME"
        else
            echo "Proxy container already running"
        fi
        return 0
    fi
    
    echo "Starting proxy container..."
    # Start proxy on default bridge network (has external access)
    docker run -d \
        --name "$PROXY_CONTAINER_NAME" \
        -p 3128:3128 \
        "$PROXY_IMAGE_NAME"
    
    # Connect proxy to internal network so agent can reach it
    docker network connect "$NETWORK_NAME" "$PROXY_CONTAINER_NAME" --ip 172.20.0.10
}

# Start the agent container
start_container() {
    local goal="${2:-}"
    
    # Remove existing container if it exists
    if docker ps -a --filter "name=$CONTAINER_NAME" --format "{{.Names}}" | grep -q "^$CONTAINER_NAME$"; then
        echo "Removing existing container $CONTAINER_NAME..."
        docker stop "$CONTAINER_NAME" || true
        docker rm "$CONTAINER_NAME" || true
    fi
    
    docker volume create claude-code-bashhistory || true
    docker volume create claude-code-config || true
    docker volume create claude-code-credentials || true
    docker volume create claude-code-json || true
    
    echo "Starting container $CONTAINER_NAME..."
    docker run -d \
        --name "$CONTAINER_NAME" \
        --network "$NETWORK_NAME" \
        --mount "type=bind,source=$(realpath "$WORKSPACE_DIR"),target=/workspace" \
        --mount "type=volume,source=claude-code-bashhistory,target=/commandhistory" \
        --mount "type=volume,source=claude-code-credentials,target=/home/node/.claude" \
        --mount "type=volume,source=claude-code-json,target=/home/node/.claude.json" \
        --env "HTTPS_PROXY=http://172.20.0.10:3128" \
        --env "HTTP_PROXY=http://172.20.0.10:3128" \
        --env "SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt" \
        --env "NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt" \
        --env "CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt" \
        --env "REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt" \
        --env "CLAUDE_GOAL=$goal" \
        --user node \
        --workdir /workspace \
        "$IMAGE_NAME"
    
    echo "Container $CONTAINER_NAME started successfully"
}

# Main execution
main() {
    local goal="${2:-}"
    validate_git_project
    build_images
    create_network
    start_proxy_container
    start_container "$1" "$goal"
}

# Parse command line arguments
case "${1:-}" in
    -h|--help)
        echo "Usage: $0 [container-name]"
        echo "Sets up a Docker container for Claude Code"
        echo "  container-name: Name for the container (default: claude-code-agent)"
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac
