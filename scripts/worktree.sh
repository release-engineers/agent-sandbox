#!/usr/bin/env bash

set -euo pipefail

# Create a git worktree for the current project
create_worktree() {
    local worktree_name="$1"
    local git_root
    
    # Validate we're in a git repository
    git_root="$(git rev-parse --show-toplevel 2>/dev/null)"
    if [[ -z "$git_root" ]]; then
        echo "Not a git repository" >&2
        exit 1
    fi
    
    # Create worktrees directory if it doesn't exist
    local worktrees_dir="$git_root/../worktrees"
    mkdir -p "$worktrees_dir"
    
    # Path for the new worktree
    local worktree_path="$worktrees_dir/$worktree_name"
    
    # Check if worktree already exists
    if [[ -d "$worktree_path" ]]; then
        echo "Worktree '$worktree_name' already exists at $worktree_path" >&2
        exit 1
    fi
    
    # Get current branch
    local current_branch
    current_branch="$(git branch --show-current)"
    
    # Create worktree
    git worktree add "$worktree_path" "$current_branch"
    
    echo "$worktree_path"
}

# Remove a git worktree
remove_worktree() {
    local worktree_name="$1"
    local git_root
    
    git_root="$(git rev-parse --show-toplevel 2>/dev/null)"
    if [[ -z "$git_root" ]]; then
        echo "Not a git repository" >&2
        exit 1
    fi
    
    local worktrees_dir="$git_root/../worktrees"
    local worktree_path="$worktrees_dir/$worktree_name"
    
    if [[ ! -d "$worktree_path" ]]; then
        echo "Worktree '$worktree_name' does not exist" >&2
        exit 1
    fi
    
    git worktree remove "$worktree_path"
    echo "Removed worktree '$worktree_name'"
}

# List existing worktrees
list_worktrees() {
    git worktree list
}

# Parse command line arguments
case "${1:-}" in
    create)
        if [[ -z "${2:-}" ]]; then
            echo "Usage: $0 create <worktree-name>" >&2
            exit 1
        fi
        create_worktree "$2"
        ;;
    remove)
        if [[ -z "${2:-}" ]]; then
            echo "Usage: $0 remove <worktree-name>" >&2
            exit 1
        fi
        remove_worktree "$2"
        ;;
    list)
        list_worktrees
        ;;
    -h|--help)
        echo "Usage: $0 <command> [args]"
        echo "Commands:"
        echo "  create <name>  Create a new worktree"
        echo "  remove <name>  Remove an existing worktree"
        echo "  list          List all worktrees"
        exit 0
        ;;
    *)
        echo "Usage: $0 <command> [args]" >&2
        echo "Run '$0 --help' for more information" >&2
        exit 1
        ;;
esac