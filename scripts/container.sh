#!/usr/bin/env bash

set -euo pipefail

# Configuration
IMAGE_NAME="claude-code-agent"
PROXY_IMAGE_NAME="claude-code-proxy"
PROXY_CONTAINER_NAME="container-proxy.local"
NETWORK_NAME="agent-network"

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
        echo "Dockerfile.agent not found" >&2
        exit 1
    fi
    
    if [[ ! -f "$dockerfile_proxy_path" ]]; then
        echo "Dockerfile.proxy not found" >&2
        exit 1
    fi
    
    # Build proxy image
    docker build -t "$PROXY_IMAGE_NAME" -f "$dockerfile_proxy_path" "$script_dir/.."
    
    # Build agent image
    docker build -t "$IMAGE_NAME" -f "$dockerfile_agent_path" "$script_dir/.."
}

# Create restricted network
create_network() {
    # Remove existing network if it exists
    docker network rm "$NETWORK_NAME" 2>/dev/null || true
    
    # Create isolated network (internal - no external access)
    docker network create "$NETWORK_NAME" \
        --internal \
        --driver bridge \
        --subnet 172.20.0.0/16 \
        --gateway 172.20.0.1
}

# Start the proxy container
start_proxy_container() {
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
    docker volume create claude-code-bashhistory > /dev/null 2>&1 || true
    docker volume create claude-code-config > /dev/null 2>&1 || true
    
    docker run -d \
        --name "claude-code-agent" \
        --network "$NETWORK_NAME" \
        --ip 172.20.0.20 \
        --mount "type=bind,source=$(realpath "$WORKSPACE_DIR"),target=/workspace" \
        --mount "type=volume,source=claude-code-bashhistory,target=/commandhistory" \
        --mount "type=volume,source=claude-code-config,target=/home/node/.claude" \
        --env "HTTPS_PROXY=http://172.20.0.10:3128" \
        --env "HTTP_PROXY=http://172.20.0.10:3128" \
        --env "SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt" \
        --env "NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt" \
        --env "CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt" \
        --env "REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt" \
        --user node \
        --workdir /workspace \
        "$IMAGE_NAME"
}

# Main execution
main() {
    validate_git_project
    build_images
    create_network
    start_proxy_container
    start_container
}

# Parse command line arguments
case "${1:-}" in
    -h|--help)
        echo "Usage: $0"
        echo "Sets up a Docker container for Claude Code"
        exit 0
        ;;
    *)
        main
        ;;
esac
