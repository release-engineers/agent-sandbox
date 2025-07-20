#!/usr/bin/env bash

set -euo pipefail

# Create Claude Code settings for the agent workspace
setup_claude_settings() {
    local workspace_path="$1"
    local agent_name="$2"
    local settings_dir="$workspace_path/.claude"
    local settings_file="$settings_dir/settings.json"
    
    mkdir -p "$settings_dir"
    
    # Create Claude Code settings with hooks
    cat > "$settings_file" << EOF
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/hooks/pre-bash"
          }
        ]
      },
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "/hooks/pre-writes"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "/hooks/post-writes"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/hooks/post-stop"
          }
        ]
      }
    ]
  }
}
EOF
}

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
    
    # Remove existing worktree if it exists
    if [[ -d "$worktree_path" ]]; then
        git worktree remove --force "$worktree_path" >/dev/null 2>&1 || true
    fi
    
    # Get current branch
    local current_branch
    current_branch="$(git branch --show-current)"
    
    # Delete existing branch if it exists
    git branch -D "$worktree_name" >/dev/null 2>&1 || true
    
    # Create worktree with new branch
    git worktree add -b "$worktree_name" "$worktree_path" "$current_branch" >/dev/null 2>&1
    
    # Setup Claude Code settings in the worktree
    setup_claude_settings "$worktree_path" "$worktree_name"
    
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

# Clean up all worktrees
cleanup_worktrees() {
    local git_root
    git_root="$(git rev-parse --show-toplevel 2>/dev/null)"
    if [[ -z "$git_root" ]]; then
        echo "Not a git repository" >&2
        exit 1
    fi
    
    local worktrees_dir="$git_root/../worktrees"
    
    if [[ ! -d "$worktrees_dir" ]]; then
        echo "No worktrees directory found"
        return 0
    fi
    
    echo "Removing all worktrees..."
    
    # Get list of worktrees (excluding main repository)
    git worktree list --porcelain | grep -A1 '^worktree ' | grep -v "^worktree $git_root$" | grep '^worktree ' | cut -d' ' -f2 | while read -r worktree_path; do
        if [[ -n "$worktree_path" && "$worktree_path" != "$git_root" ]]; then
            echo "  - Removing worktree: $worktree_path"
            git worktree remove --force "$worktree_path" || true
        fi
    done
    
    # Remove worktrees directory if empty
    if [[ -d "$worktrees_dir" ]] && [[ -z "$(ls -A "$worktrees_dir")" ]]; then
        rmdir "$worktrees_dir"
        echo "Removed empty worktrees directory"
    fi
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
    cleanup)
        cleanup_worktrees
        ;;
    -h|--help)
        echo "Usage: $0 <command> [args]"
        echo "Commands:"
        echo "  create <name>  Create a new worktree"
        echo "  remove <name>  Remove an existing worktree"
        echo "  list          List all worktrees"
        echo "  cleanup       Remove all worktrees"
        exit 0
        ;;
    *)
        echo "Usage: $0 <command> [args]" >&2
        echo "Run '$0 --help' for more information" >&2
        exit 1
        ;;
esac