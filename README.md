# Agent Sandbox (AGS)

Run Claude Code AI agents in isolated Docker containers with network restrictions and git worktree isolation.

## What It Does

AGS creates secure, isolated environments for Claude Code agents to:
- Work in separate git worktrees with dedicated branches
- Run inside Docker containers with network whitelisting
- Execute specific tasks without affecting your main codebase
- Automatically commit their changes to feature branches

## Quick Start

### Prerequisites
- Python 3.9+
- Docker running
- Git repository
- Claude Code subscription

### Installation

```bash
# Clone and setup
git clone https://github.com/anthropics/agent-sandbox.git
cd agent-sandbox

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Optional: Add to PATH
export PATH="$(pwd)/bin:$PATH"
```

### Basic Usage

```bash
# Authenticate Claude Code (first time only)
ags auth

# Start an agent
ags start feature-x "Add authentication to the user API"

# List agent branches
ags list

# Stop a running agent (if needed)
ags stop feature-x

# Clean up all agents
ags cleanup
```

## How It Works

1. **Creates Git Worktree**: Isolated workspace at `../worktrees/<name>`
2. **Builds Docker Images**: Agent container + proxy container
3. **Configures Security**: Sets up hooks and network restrictions
4. **Runs Claude Code**: Executes with your goal, streams output
5. **Commits Changes**: Automatically commits to `agent--<name>` branch

## Architecture

```
┌─────────────────┐     ┌──────────────────┐
│  Agent Container│────▶│  Proxy Container │────▶ Whitelisted
│  (Claude Code)  │     │   (Tinyproxy)    │     Domains Only
└─────────────────┘     └──────────────────┘
         │
         ▼
   Git Worktree
  (../worktrees/name)
```

## Security Features

- **Network Isolation**: All traffic goes through proxy
- **Domain Whitelisting**: Only approved domains (GitHub, Anthropic API, etc.)
- **File System Isolation**: Agents confined to their worktree
- **Hook Validation**: Pre/post action validation
- **No Host Access**: Containers can't access host system

## Commands

| Command | Description |
|---------|-------------|
| `ags start <name> "<goal>"` | Start new agent with goal |
| `ags list` | Show agent records with status |
| `ags logs <name>` | View logs for specific agent |
| `ags apply <name>` | Apply stored diff from agent |
| `ags stop <name>` | Stop running agent |
| `ags cleanup` | Remove all agents |
| `ags auth` | Authenticate Claude Code |

## Examples

```bash
# Add tests to a module
ags start add-tests "Write unit tests for the auth module"

# Fix a bug
ags start fix-bug "Fix the memory leak in the worker process"

# Refactor code
ags start refactor "Refactor database queries to use prepared statements"

# View agent history and apply changes
ags list                           # Show completed agents
ags logs add-tests-20240122-143022 # View specific agent logs  
ags apply add-tests-20240122-143022 # Apply the agent's changes

# Multiple agents in parallel
ags start frontend "Update React components to use hooks"
ags start backend "Add rate limiting to API endpoints"
ags start docs "Generate API documentation"
```

## Configuration

### Whitelisted Domains
Edit `tinyproxy-whitelist` to add domains:
```
api.anthropic.com
github.com
npmjs.org
# Add your domains here
```

### Hooks
Validation hooks in `hooks/`:
- `pre-bash`: Validate shell commands
- `pre-writes`: Validate file modifications
- `post-writes`: After file changes
- `post-stop`: Cleanup actions

## Troubleshooting

```bash
# View agent logs
docker logs <agent-name>

# Access container
docker exec -it <agent-name> /bin/bash

# Check proxy logs
docker logs proxy-<agent-name>

# Force cleanup
docker stop $(docker ps -q --filter "label=ags")
ags cleanup
```

## Project Structure

```
agent-process/
├── src/                   # Modular Python source
│   ├── main.py           # CLI interface
│   ├── agent.py          # Agent orchestration
│   ├── workspace.py      # Git/Docker management
│   ├── diff.py           # Diff operations
│   ├── log.py            # Log formatting
│   └── *_db.py           # Database modules
├── requirements.txt       # Dependencies (click, docker, rich)
├── bin/
│   ├── ags               # CLI wrapper
│   └── ags-test          # Test script
├── hooks/                 # Validation scripts
├── certs/                 # SSL certificates
├── Dockerfile.agent       # Claude Code container
├── Dockerfile.proxy       # Proxy container
├── tinyproxy-whitelist    # Allowed domains
└── example/              # Sample project
```

## License

MIT License - see LICENSE file for details.

