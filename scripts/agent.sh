#!/usr/bin/env bash

set -euo pipefail

# Run all pre-flight checks at startup
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo "ERROR: Docker is not running" >&2
        echo "" >&2
        echo "Please start Docker Desktop or Docker daemon and try again." >&2
        echo "You can verify Docker is running with: docker info" >&2
        exit 1
    fi
}

check_git_repo() {
    if ! git rev-parse --show-toplevel > /dev/null 2>&1; then
        echo "ERROR: Not in a git repository" >&2
        echo "" >&2
        echo "Please run this command from within a git repository." >&2
        echo "To initialize a git repository, run: git init" >&2
        exit 1
    fi
}

check_port_conflicts() {
    local port=3128
    if command -v lsof > /dev/null && lsof -i :$port > /dev/null 2>&1; then
        echo "WARNING: Port $port is already in use" >&2
        echo "" >&2
        echo "The HTTP proxy uses port $port. If you encounter issues, please:" >&2
        echo "1. Stop any service using port $port" >&2
        echo "2. Or run: $0 cleanup" >&2
        echo "" >&2
    fi
}

check_claude_auth() {
    if ! docker volume inspect claude-code-credentials > /dev/null 2>&1; then
        echo "WARNING: Claude Code authentication may not be set up" >&2
        echo "" >&2
        echo "If you encounter authentication issues, please run:" >&2
        echo "  $0 auth" >&2
        echo "" >&2
        return 1
    fi
    return 0
}

# Run checks for all commands except help
case "${1:-}" in
    ""|-h|--help)
        # Skip checks for help
        ;;
    *)
        check_docker
        check_git_repo
        check_port_conflicts
        check_claude_auth || true  # Don't fail on auth warning
        ;;
esac

# Validate goal is provided
validate_goal() {
    local goal="${1:-}"
    
    if [[ -z "$goal" ]]; then
        echo "ERROR: No goal provided" >&2
        echo "" >&2
        echo "Usage: $0 start <agent-name> <goal>" >&2
        echo "" >&2
        echo "Example:" >&2
        echo "  $0 start my-feature 'Add user authentication to the login page'" >&2
        echo "  $0 start docs 'Add documentation to all functions in main.go'" >&2
        exit 1
    fi
    
    echo "Using goal: $goal"
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
    
    echo "Starting agent for: $agent_name"
    echo "Worktree: $worktree_path"
    echo "Goal: $goal"
    echo ""
    
    # Start container with agent name and goal - this will run synchronously
    "$script_dir/agent-container.sh" "$agent_name" "$goal"
    
    # When this returns, the agent has completed
    echo ""
    echo "Agent completed. Cleaning up..."
    stop_agent "$agent_name"
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
    
    # Remove existing auth container if it exists
    if docker ps -a --filter "name=$auth_container" --format "{{.Names}}" | grep -q "^$auth_container$"; then
        echo "Removing existing auth container..."
        docker stop "$auth_container" || true
        docker rm "$auth_container" || true
    fi
    
    # Volumes are created in agent-container.sh
    
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
    
    # Cleanup proxy infrastructure
    "$script_dir/agent-proxy.sh" cleanup
    
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
    list)
        list_agents
        ;;
    auth)
        auth_claude
        ;;
    cleanup)
        cleanup_all
        ;;
    ""|-h|--help)
        echo "Usage: $0 <command> [args]"
        echo "Commands:"
        echo "  start <name> <goal>  Run agent with goal, wait for completion, then cleanup"
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
