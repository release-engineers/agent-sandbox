# Agent Sandbox (AGS) - Technical Documentation

## Overview

Agent Sandbox (AGS) is a Docker-based isolation system for running Claude Code AI agents in secure, sandboxed environments. This document provides technical implementation details for AI assistants working with this codebase.

## Architecture

### Core Implementation
- **Modular Python application**: Organized into `src/` directory with separation of concerns
- **Dependencies**: `click` (CLI framework), `docker` (container management), `rich` (output formatting)
- **Database persistence**: SQLite for tracking agents, diffs, and logs
- **Direct subprocess calls**: Git operations handled via subprocess
- **Docker SDK**: Container management via docker-py

### Container Architecture
1. **Agent Container** (`claude-code-agent`)
   - Base: `node:20`
   - Claude Code CLI installed globally
   - Runs as non-root `node` user with sudo access
   - Network access only through proxy

2. **Proxy Container** (`claude-code-proxy`)
   - Base: `alpine:latest`
   - Tinyproxy for domain whitelisting
   - Port 3128 for HTTP/HTTPS proxy

### Network Security
- **Isolated network**: `agent-network` Docker network
- **Proxy enforcement**: All traffic routes through tinyproxy
- **Whitelisted domains** (tinyproxy-whitelist):
  - api.anthropic.com
  - docs.anthropic.com
  - statsig.anthropic.com
  - sentry.io
  - github.com
  - objects.githubusercontent.com
  - raw.githubusercontent.com

## Key Classes and Methods

### Core Modules

#### AgentManager (`src/agent.py`)
Main orchestration class with database integration:
- `__init__(db_path)`: Initializes with database path, sets up all managers
- `start_agent(goal)`: Creates unique timestamped agent, manages full workflow
- `restart_agent(agent_name)`: Restart existing agent with same goal and reset status
- `list_agents()`: Shows agent records from database with rich formatting
- `cleanup_all()`: Removes all agents and resources
- `auth()`: Runs Claude Code authentication
- `show_agent_logs(name)`: Display logs for specific agent
- `show_diff(agent_name)`: Output diff content for CLI piping
- `get_diff(agent_name)`: Get diff content for TUI display

#### WorkspaceManager (`src/workspace.py`)
Git worktree and Docker container management:
- `create_workspace(name)`: Creates git worktree in `../worktrees/<name>`
- `setup_claude_settings(workspace_path)`: Generates `.claude/settings.json`
- `build_images()`: Builds agent and proxy Docker images
- `run_agent_container()`: Executes Claude Code with log streaming
- `cleanup_existing_agent(name)`: Removes existing containers/worktrees

#### DiffManager (`src/diff.py`)
Diff generation and application:
- `generate_diff(agent_name, workspace_path)`: Creates and stores git diff
- `apply_diff(agent_name)`: Applies stored diff to current working directory
- `get_diff_by_agent_name(agent_id)`: Retrieves diff content for specific agent
- `update_agent_status()`: Updates agent status in database

#### LogManager (`src/log.py`)
Log formatting and storage:
- `AgentLogFormatter`: Rich console formatting with tool icons/colors
- `LogManager`: Database storage and retrieval of agent logs
- `display_agent_logs()`: Shows formatted logs from database

#### Database Classes (`src/db.py`, `src/*_db.py`)
SQLite persistence layer:
- `Database`: Base class with thread-safe operations
- `AgentDatabase`: Tracks agent requests and status
- `DiffDatabase`: Stores and manages diff content
- `LogDatabase`: Persists agent execution logs

### Workflow Sequence
1. **Cleanup**: Remove any existing agent with same name
2. **Database Entry**: Create agent request record with unique timestamped name
3. **Git Worktree**: Create at `../worktrees/<name>-<timestamp>`
4. **Claude Settings**: Generate `.claude/settings.json` with hooks
5. **Build Images**: Build both Docker images
6. **Start Proxy**: Launch proxy container first
7. **Run Agent**: Execute Claude Code with goal, stream and store output
8. **Generate Diff**: Create git diff and store in database
9. **Cleanup**: Remove containers and worktree, preserve database records

## File Structure

```
agent-process/
├── src/                   # Modular Python source code
│   ├── __init__.py       # Package initialization
│   ├── main.py           # CLI interface with click commands
│   ├── agent.py          # AgentManager orchestration class
│   ├── workspace.py      # Git worktree and Docker management
│   ├── diff.py           # Diff generation and application
│   ├── log.py            # Log formatting and display
│   ├── db.py             # Base database class
│   ├── agent_db.py       # Agent request tracking
│   ├── diff_db.py        # Diff storage and retrieval
│   ├── log_db.py         # Log persistence
│   └── tui/              # Terminal User Interface
│       └── app.py        # Textual-based TUI application
├── requirements.txt       # Python dependencies (click, docker, rich)
├── bin/
│   ├── ags               # Wrapper script for PATH usage
│   └── ags-test          # Test script for example/
├── hooks/                 # Validation hooks
│   ├── pre-bash          # Validates bash commands
│   ├── pre-writes        # Validates file writes
│   ├── post-writes       # Post-write actions
│   └── post-stop         # Cleanup on stop
├── certs/
│   └── proxy.crt         # Self-signed cert for proxy
├── Dockerfile.agent       # Agent container definition
├── Dockerfile.proxy       # Proxy container definition
├── tinyproxy.conf        # Proxy configuration
├── tinyproxy-whitelist   # Allowed domains
└── example/              # Test project
```

## Docker Configuration

### Agent Container (`Dockerfile.agent`)
- **Packages**: git, gh, vim, jq, fzf, curl, wget, less, procps, sudo, zsh, unzip
- **Node.js**: Version 20 with increased memory (4096MB)
- **Claude Code**: Installed globally via npm
- **Volumes**:
  - Worktree mounted at `/workspace`
  - Credentials at `/home/node/.claude`
- **Environment**:
  - `CLAUDE_GOAL`: Task description
  - `CLAUDE_CONFIG_DIR`: /home/node/.claude
  - `NODE_OPTIONS`: --max-old-space-size=4096
- **Command**: `claude -p "$CLAUDE_GOAL" --dangerously-skip-permissions`

### Proxy Container (`Dockerfile.proxy`)
- **Base**: Alpine Linux (minimal)
- **Service**: Tinyproxy on port 3128
- **Configuration**: Custom whitelist and config files

## Git Management

### Worktree Handling
- **Location**: `../worktrees/<name>` (parent directory)
- **Branch naming**: `agent--<name>`
- **Isolation**: Each agent gets separate worktree
- **Cleanup**: Worktree removed after commit

### Commit Process
- **Automatic staging**: `git add .` in worktree
- **Commit message**: "Agent {name} changes\n\nAutomatically committed by agent-process"
- **Branch persistence**: Branch remains after worktree removal
- **Exclusions**: `.claude/` folders excluded via .gitignore

## Hook System

### Configuration (in `.claude/settings.json`)
```json
{
  "hooks": {
    "PreToolUse": [
      {"matcher": "Bash", "hooks": [{"type": "command", "command": "/hooks/pre-bash"}]},
      {"matcher": "Write|Edit|MultiEdit", "hooks": [{"type": "command", "command": "/hooks/pre-writes"}]}
    ],
    "PostToolUse": [
      {"matcher": "Write|Edit|MultiEdit", "hooks": [{"type": "command", "command": "/hooks/post-writes"}]}
    ],
    "Stop": [
      {"matcher": ".*", "hooks": [{"type": "command", "command": "/hooks/stop"}]}
    ]
  },
  "tools": {"computer_use": {"enabled": false}}
}
```

## User Interfaces

### Terminal User Interface (TUI)
Agent Sandbox includes a modern TUI built with Textual for interactive agent management:

#### Starting the TUI
```bash
ags tui
# or
ags  # TUI is the default interface
```

#### TUI Features
- **Real-time agent monitoring**: Auto-refreshing table showing all agents with status updates
- **Vim-style colon commands**: Intuitive command interface inspired by vim
- **Fullscreen diff viewer**: Syntax-highlighted git diffs with scrolling support
- **Seamless typing**: Auto-focus input field, type anywhere to enter goals
- **Table navigation**: Use up/down arrows when input is empty or starts with ":"
- **Agent restart**: Re-run existing agents with the same goal

#### Colon Commands
- **`:q` or `:quit`**: Exit the TUI
- **`:l` or `:logs`**: Show logs for selected agent (future feature)
- **`:d` or `:diff`**: View diff for selected agent in fullscreen viewer
- **`:r` or `:restart`**: Restart selected agent with same goal
- **`:c` or `:cleanup`**: Clean up all agents and resources

#### Agent Status Colors
- **Green**: `DONE` - Agent completed with changes
- **Dim Green**: `DONE_AND_NONE` - Agent completed with no changes
- **Yellow**: `AGENT_RUNNING` - Agent currently executing
- **Blue**: `AGENT_COMPLETE` - Agent finished, generating diff
- **Red**: Error states or unknown status

#### Keyboard Shortcuts
- **Enter**: Submit goal to start new agent, or view diff if input is empty
- **Ctrl+C**: Clear input field
- **Up/Down arrows**: Navigate table when input empty or starts with ":"
- **Escape**: Close diff viewer or other modals

### CLI Commands (Legacy)

#### Primary Commands
- `ags start "<goal>"`: Create and run agent with unique timestamped name
- `ags list`: Show agent records from database with rich formatting
- `ags cleanup`: Remove all agents and resources
- `ags auth`: Authenticate with Claude Code
- `ags logs <name>`: View stored logs for specific agent
- `ags diff <agent_name>`: Output diff content for piping to git apply

#### Implementation Details
- **Click framework**: Command-line interface in `src/main.py`
- **Rich formatting**: Colorized output with progress indicators
- **Database persistence**: All operations tracked in `~/.ags/agents.db`
- **Error handling**: ClickException for user-friendly errors
- **Real-time output**: Streams container logs to terminal and database
- **Exit codes**: Proper status code handling

## Resource Management

### Container Lifecycle
- **Auto-removal**: Containers set with `auto_remove=True`
- **Graceful shutdown**: Stop containers before removal
- **Network cleanup**: Remove `agent-network` when done

### Volume Management
- **Credentials volume**: `claude-code-credentials` (persistent)
- **Worktree mount**: Temporary, removed after agent completes

### Database Management
- **Location**: `~/.ags/agents.db` (SQLite database)
- **Thread-safe**: All database operations use threading locks
- **Persistent storage**: Agent requests, diffs, and logs preserved
- **Cleanup**: Database records remain after container cleanup
- **Status tracking**: Enhanced diff status including `DONE_AND_NONE` for empty diffs

## Error Handling

### Common Scenarios
- **Docker not running**: Exit with error message
- **Git worktree conflicts**: Force removal of existing
- **Branch conflicts**: Delete existing branch before creating
- **Container failures**: Catch and display errors

## Security Considerations

1. **Network isolation**: Default deny, explicit allow via proxy
2. **File system boundaries**: Agent confined to worktree
3. **Credential isolation**: Separate volume for Claude credentials
4. **Hook validation**: All actions pass through hooks
5. **No direct internet**: Everything through proxy whitelist

## Testing

### Test Script (`bin/ags-test`)
- Changes to `example/` directory
- Cleans up existing test resources
- Runs simple "hello world" Go program task
- Useful for validation and debugging

## Best Practices for Development

1. **Maintain simplicity**: Keep agent.py readable and direct
2. **Test Docker operations**: Container and network management
3. **Handle edge cases**: Git conflicts, Docker failures
4. **Preserve security**: Don't bypass proxy or hooks
5. **Stream output**: Users need real-time feedback
6. **Clean up resources**: Always remove containers and worktrees