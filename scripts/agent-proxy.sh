#!/usr/bin/env bash

set -euo pipefail

# Configuration
PROXY_IMAGE_NAME="claude-code-proxy"
PROXY_CONTAINER_NAME="container-proxy.local"
NETWORK_NAME="agent-network"

# Build the proxy Docker image
build_proxy_image() {
    local script_dir
    script_dir="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
    local dockerfile_proxy_path="$script_dir/../Dockerfile.proxy"
    
    if [[ ! -f "$dockerfile_proxy_path" ]]; then
        echo "Error: Dockerfile.proxy not found at $dockerfile_proxy_path" >&2
        exit 1
    fi
    
    echo "Building proxy image..."
    docker build -t "$PROXY_IMAGE_NAME" -f "$dockerfile_proxy_path" "$script_dir/.."
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

# Stop the proxy container
stop_proxy_container() {
    if docker ps -a --filter "name=$PROXY_CONTAINER_NAME" --format "{{.Names}}" | grep -q "^$PROXY_CONTAINER_NAME$"; then
        echo "Stopping proxy container..."
        docker stop "$PROXY_CONTAINER_NAME" || true
        docker rm "$PROXY_CONTAINER_NAME" || true
    fi
}

# Remove the network
remove_network() {
    if docker network inspect "$NETWORK_NAME" > /dev/null 2>&1; then
        echo "Removing network $NETWORK_NAME..."
        docker network rm "$NETWORK_NAME" || true
    fi
}

# Parse command line arguments
case "${1:-}" in
    build)
        build_proxy_image
        ;;
    start)
        build_proxy_image
        create_network
        start_proxy_container
        ;;
    stop)
        stop_proxy_container
        ;;
    cleanup)
        stop_proxy_container
        remove_network
        ;;
    -h|--help)
        echo "Usage: $0 <command>"
        echo "Commands:"
        echo "  build     Build proxy Docker image"
        echo "  start     Setup proxy infrastructure (build, network, start)"
        echo "  stop      Stop proxy container"
        echo "  cleanup   Stop proxy and remove network"
        exit 0
        ;;
    *)
        echo "Usage: $0 <command>" >&2
        echo "Run '$0 --help' for more information" >&2
        exit 1
        ;;
esac