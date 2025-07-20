#!/usr/bin/env bash

set -euo pipefail

# Validate goal is provided
validate_goal() {
    local goal="${1:-}"
    
    if [[ -z "$goal" ]]; then
        echo "No goal provided" >&2
        echo "Usage: $0 start <agent-name> <goal>" >&2
        exit 1
    fi
    
    echo "Using goal: $goal"
}


# Start Claude Code in the container
start_claude_code() {
    local agent_name="$1"
    local goal="$2"
    
    echo "Starting Claude Code with goal: $goal"
    echo "Claude Code will start directly in the container"
    echo "Goal will be passed as environment variable"
}

# Main agent workflow script - creates worktree and container
start_agent() {
    local agent_name="$1"
    local goal="${2:-}"
    local script_dir
    script_dir="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
    
    echo "Starting agent workflow for: $agent_name"
    
    # Validate goal is provided
    validate_goal "$goal"
    
    # Create worktree with Claude settings
    echo "Creating worktree..."
    local worktree_path
    worktree_path="$("$script_dir/agent-workspace.sh" create "$agent_name")"
    
    # Change to worktree directory
    cd "$worktree_path"
    
    # Start container with agent name and goal
    echo "Starting container..."
    "$script_dir/agent-container.sh" "$agent_name" "$goal"
    
    # Claude Code starts automatically with the goal
    start_claude_code "$agent_name" "$goal"
    
    echo "Agent '$agent_name' started successfully"
    echo "Worktree: $worktree_path"
    echo "Container: $agent_name"
    echo "Goal: $goal"
}

# Stop agent workflow - removes container and worktree
stop_agent() {
    local agent_name="$1"
    local script_dir
    script_dir="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
    
    echo "Stopping agent workflow for: $agent_name"
    
    # Stop and remove container
    echo "Stopping container..."
    docker stop "$agent_name" || true
    docker rm "$agent_name" || true
    
    # Remove worktree
    echo "Removing worktree..."
    "$script_dir/agent-workspace.sh" remove "$agent_name"
    
    echo "Agent '$agent_name' stopped and cleaned up"
}

# List active agents
list_agents() {
    local script_dir
    script_dir="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
    
    echo "Active worktrees:"
    "$script_dir/agent-workspace.sh" list
    
    echo ""
    echo "Running containers:"
    docker ps --filter "ancestor=claude-code-agent" --format "table {{.Names}}\t{{.Status}}"
}

# Run Claude Code authentication
auth_claude() {
    local script_dir
    script_dir="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
    
    echo "Starting Claude Code authentication..."
    
    # Create a temporary container for authentication
    local auth_container="claude-auth-temp"
    local git_root
    git_root="$(git rev-parse --show-toplevel 2>/dev/null)"
    
    if [[ -z "$git_root" ]]; then
        echo "Not a git repository" >&2
        exit 1
    fi
    
    # Remove existing auth container if it exists
    if docker ps -a --filter "name=$auth_container" --format "{{.Names}}" | grep -q "^$auth_container$"; then
        echo "Removing existing auth container..."
        docker stop "$auth_container" || true
        docker rm "$auth_container" || true
    fi
    
    # Create volumes if they don't exist
    docker volume create claude-code-credentials || true
    docker volume create claude-code-json || true
    
    # Run temporary container for authentication
    echo "Starting authentication container..."
    echo "This will open an interactive Claude Code authentication session."
    echo "Follow the prompts to authenticate with your Claude account."
    echo ""
    
    docker run -it --rm \
        --name "$auth_container" \
        --mount "type=volume,source=claude-code-credentials,target=/home/node/.claude" \
        --mount "type=volume,source=claude-code-json,target=/home/node/.claude.json" \
        --user node \
        --workdir /workspace \
        claude-code-agent \
        claude
    
    echo "Authentication completed"
}

# Clean up all agents - stop containers and remove worktrees
cleanup_all() {
    local script_dir
    script_dir="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
    
    echo "Cleaning up all agents..."
    
    # Stop and remove all claude-code-agent containers
    local containers
    containers=$(docker ps -a --filter "ancestor=claude-code-agent" --format "{{.Names}}")
    if [[ -n "$containers" ]]; then
        echo "Stopping and removing containers:"
        echo "$containers" | while read -r container; do
            echo "  - $container"
            docker stop "$container" || true
            docker rm "$container" || true
        done
    else
        echo "No containers to clean up"
    fi
    
    # Remove proxy container if it exists
    if docker ps -a --filter "name=container-proxy.local" --format "{{.Names}}" | grep -q "^container-proxy.local$"; then
        echo "Removing proxy container..."
        docker stop container-proxy.local || true
        docker rm container-proxy.local || true
    fi
    
    # Remove network if it exists
    if docker network inspect agent-network > /dev/null 2>&1; then
        echo "Removing network..."
        docker network rm agent-network || true
    fi
    
    # Remove all worktrees
    echo "Removing all worktrees..."
    "$script_dir/agent-workspace.sh" cleanup
    
    # Delete any remaining agent branches
    echo "Cleaning up agent branches..."
    git branch | grep -E '^\s+(test-|agent-)' | sed 's/^[[:space:]]*//' | while read -r branch; do
        if [[ "$branch" != "$(git branch --show-current)" ]]; then
            echo "  - Deleting branch: $branch"
            git branch -D "$branch" || true
        fi
    done
    
    echo "Cleanup completed"
}

# Parse command line arguments
case "${1:-}" in
    start)
        if [[ -z "${2:-}" ]]; then
            echo "Usage: $0 start <agent-name> <goal>" >&2
            exit 1
        fi
        start_agent "$2" "${3:-}"
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
    auth)
        auth_claude
        ;;
    cleanup)
        cleanup_all
        ;;
    -h|--help)
        echo "Usage: $0 <command> [args]"
        echo "Commands:"
        echo "  start <name> <goal>  Create worktree and start container for agent"
        echo "  stop <name>          Stop container and remove worktree for agent"
        echo "  list                 List active agents (worktrees and containers)"
        echo "  auth                 Authenticate Claude Code (run once)"
        echo "  cleanup              Clean up all agents, containers, and worktrees"
        exit 0
        ;;
    *)
        echo "Usage: $0 <command> [args]" >&2
        echo "Run '$0 --help' for more information" >&2
        exit 1
        ;;
esac
