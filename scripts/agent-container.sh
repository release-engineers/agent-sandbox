#!/usr/bin/env bash

set -euo pipefail

# Configuration
IMAGE_NAME="claude-code-agent"
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

# Build the agent Docker image
build_agent_image() {
    local script_dir
    script_dir="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
    local dockerfile_agent_path="$script_dir/../Dockerfile.agent"
    
    if [[ ! -f "$dockerfile_agent_path" ]]; then
        echo "Error: Dockerfile.agent not found at $dockerfile_agent_path" >&2
        exit 1
    fi
    
    echo "Building agent image..."
    docker build -t "$IMAGE_NAME" -f "$dockerfile_agent_path" "$script_dir/.."
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
    
    # Create persistent volumes for Claude Code data
    docker volume create claude-code-credentials || true    # Authentication credentials
    docker volume create claude-code-json || true           # Claude JSON config
    
    echo "Starting container $CONTAINER_NAME..."
    docker run --rm \
        --name "$CONTAINER_NAME" \
        --network "$NETWORK_NAME" \
        --mount "type=bind,source=$(realpath "$WORKSPACE_DIR"),target=/workspace" \
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
}

# Main execution
main() {
    local goal="${2:-}"
    local script_dir
    script_dir="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
    
    validate_git_project
    
    # Setup proxy infrastructure
    "$script_dir/agent-proxy.sh" start
    
    # Build agent image and start container
    build_agent_image
    start_container "$1" "$goal"
}

# Parse command line arguments
case "${1:-}" in
    -h|--help)
        echo "Usage: $0 [container-name] [goal]"
        echo "Sets up a Docker container for Claude Code"
        echo "  container-name: Name for the container (default: claude-code-agent)"
        echo "  goal: Goal to pass to Claude Code"
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac