# Agent Sandbox (AGS) - Technical Documentation

## Overview

Agent Sandbox (AGS) is a Docker-based isolation system for running Claude Code AI agents in secure, sandboxed environments. This document provides technical implementation details for AI assistants working with this codebase.

## Architecture

### Core Implementation
- **Single-file Python application**: `agent.py` (~360 lines)
- **Dependencies**: `click` (CLI framework), `docker` (container management)
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

### AgentManager Class
Main orchestration class with the following methods:

- `__init__()`: Initializes Docker client, sets up paths
- `start_agent(name, goal)`: Main workflow orchestrator
- `_cleanup_existing_agent(name)`: Removes existing resources
- `_cleanup_and_commit(name)`: Commits changes and cleans up
- `list_agents()`: Shows agent branches
- `stop_agent(name)`: Backward compatibility wrapper
- `cleanup_all()`: Removes all agents and resources
- `auth()`: Runs Claude Code authentication

### Workflow Sequence
1. **Cleanup**: Remove any existing agent with same name
2. **Git Worktree**: Create at `../worktrees/<name>` with branch `agent--<name>`
3. **Claude Settings**: Generate `.claude/settings.json` with hooks
4. **Build Images**: Build both Docker images
5. **Start Proxy**: Launch proxy container first
6. **Run Agent**: Execute Claude Code with goal, stream output
7. **Commit & Cleanup**: Stage all changes, commit, remove worktree

## File Structure

```
agent-sandbox/
├── agent.py               # Main implementation
├── requirements.txt       # Python dependencies (click, docker)
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

## CLI Commands

### Primary Commands
- `ags start <name> "<goal>"`: Create and run agent
- `ags list`: Show agent branches
- `ags stop <name>`: Stop agent (backward compatibility)
- `ags cleanup`: Remove all agents and resources
- `ags auth`: Authenticate with Claude Code

### Implementation Details
- **Click framework**: Command-line interface
- **Error handling**: ClickException for user-friendly errors
- **Real-time output**: Streams container logs to terminal
- **Exit codes**: Proper status code handling

## Resource Management

### Container Lifecycle
- **Auto-removal**: Containers set with `auto_remove=True`
- **Graceful shutdown**: Stop containers before removal
- **Network cleanup**: Remove `agent-network` when done

### Volume Management
- **Credentials volume**: `claude-code-credentials` (persistent)
- **Worktree mount**: Temporary, removed after agent completes

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