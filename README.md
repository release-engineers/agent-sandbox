# Agent Sandbox (AGS)

Run Claude Code AI agents in isolated Docker containers with network restrictions and git worktree isolation.

## What It Does

AGS creates secure, isolated environments for Claude Code agents with:
- **Interactive TUI**: Modern terminal interface with real-time monitoring
- **Vim-style commands**: Intuitive `:quit`, `:diff`, `:restart` workflow
- **Git worktrees**: Isolated workspaces with dedicated branches
- **Docker containers**: Sandboxed execution with network whitelisting
- **Diff viewer**: Fullscreen syntax-highlighted code review
- **Agent restart**: Re-run agents with the same goals

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

## Usage

```bash
ags

# Type your goal, hit Enter. i.e. "Add error handling to the login function"

# Navigate with arrows when input is empty
# Use colon commands:
:d    # or :diff    to view a diff for the selected agent
:r    # or :restart to restart the selected agent
:c    # or :cleanup to remove all agent containers and worktrees
:q    # or :quit    to exit the TUI

# The first run will require Claude auth to set up your credentials volume:
docker run -it --rm -v claude-code-credentials:/home/node/.claude node:20 claude auth
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

- **File System Isolation**: Agents run against a worktree copy of your project
- **No Host Access**: Agents run in isolated containers
- **Network Isolation**: No network access except for our proxy
- **Domain Whitelisting**: The proxy only allows access to pre-approved domains (GitHub, Anthropic API, etc.)

## Configuration

### Whitelisted Domains
Edit [`tinyproxy-whitelist`](tinyproxy-whitelist) to add domains.

### Hooks
Hooks in `hooks/`:
- [`pre-any`](hooks/pre-any): Logs all tool usage
- [`pre-bash`](hooks/pre-bash): Bash command hooks
- [`pre-writes`](hooks/pre-writes): File modification hooks
- [`post-writes`](hooks/post-writes): After file changes
- [`post-stop`](hooks/post-stop): Cleanup actions

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
│   ├── main.py            # CLI interface
│   ├── agent.py           # Agent orchestration
│   ├── workspace.py       # Git/Docker management
│   ├── diff.py            # Diff operations
│   ├── log.py             # Log formatting
│   ├── *_db.py            # Database modules
│   └── tui/               # Terminal User Interface
│       └── app.py         # Textual-based TUI
├── requirements.txt       # Dependencies (click, docker, rich)
├── bin/
│   ├── ags                # CLI wrapper
│   └── ags-test           # Test script
├── hooks/                 # Validation scripts
├── certs/                 # SSL certificates
├── Dockerfile.agent       # Claude Code container
├── Dockerfile.proxy       # Proxy container
├── tinyproxy-whitelist    # Allowed domains
└── example/               # Sample project
```

## License

This is a reference implementation on how to implement an agent sandbox.
It is not licensed under any open source license.
