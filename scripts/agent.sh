#!/usr/bin/env bash

set -euo pipefail

# Main agent workflow script - creates worktree and container
start_agent() {
    local agent_name="$1"
    local script_dir
    script_dir="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
    
    echo "Starting agent workflow for: $agent_name"
    
    # Create worktree
    echo "Creating worktree..."
    local worktree_path
    worktree_path="$("$script_dir/worktree.sh" create "$agent_name")"
    
    # Change to worktree directory
    cd "$worktree_path"
    
    # Start container with agent name
    echo "Starting container..."
    "$script_dir/container.sh" "$agent_name"
    
    echo "Agent '$agent_name' started successfully"
    echo "Worktree: $worktree_path"
    echo "Container: $agent_name"
}

# Stop agent workflow - removes container and worktree
stop_agent() {
    local agent_name="$1"
    local script_dir
    script_dir="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
    
    echo "Stopping agent workflow for: $agent_name"
    
    # Stop and remove container
    echo "Stopping container..."
    docker stop "$agent_name" 2>/dev/null || true
    docker rm "$agent_name" 2>/dev/null || true
    
    # Remove worktree
    echo "Removing worktree..."
    "$script_dir/worktree.sh" remove "$agent_name"
    
    echo "Agent '$agent_name' stopped and cleaned up"
}

# List active agents
list_agents() {
    local script_dir
    script_dir="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
    
    echo "Active worktrees:"
    "$script_dir/worktree.sh" list
    
    echo ""
    echo "Running containers:"
    docker ps --filter "ancestor=claude-code-agent" --format "table {{.Names}}\t{{.Status}}"
}

# Parse command line arguments
case "${1:-}" in
    start)
        if [[ -z "${2:-}" ]]; then
            echo "Usage: $0 start <agent-name>" >&2
            exit 1
        fi
        start_agent "$2"
        ;;
    stop)
        if [[ -z "${2:-}" ]]; then
            echo "Usage: $0 stop <agent-name>" >&2
            exit 1
        fi
        stop_agent "$2"
        ;;
    list)
        list_agents
        ;;
    -h|--help)
        echo "Usage: $0 <command> [args]"
        echo "Commands:"
        echo "  start <name>  Create worktree and start container for agent"
        echo "  stop <name>   Stop container and remove worktree for agent"
        echo "  list         List active agents (worktrees and containers)"
        exit 0
        ;;
    *)
        echo "Usage: $0 <command> [args]" >&2
        echo "Run '$0 --help' for more information" >&2
        exit 1
        ;;
esac