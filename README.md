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

### Basic Usage

```bash
# Launch the TUI interface
ags

# In the TUI:
# - Type your goal and press Enter to start an agent
# - Use :d to view diffs, :r to restart agents
# - Use :c to cleanup agents
# - Press :q to quit

# Authenticate Claude Code when prompted, or use:
# docker run -it --rm -v claude-code-credentials:/home/node/.claude node:20 claude auth
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

## Terminal User Interface

The interactive Terminal User Interface provides a modern agent management experience:

```bash
ags  # Launch TUI
```

**TUI Features:**
- **Real-time monitoring**: Auto-refreshing agent status table
- **Vim-style commands**: `:quit`, `:diff`, `:restart`, `:cleanup`
- **Fullscreen diff viewer**: Syntax-highlighted git diffs with scrolling
- **Seamless interaction**: Type anywhere to enter goals, arrows to navigate
- **Agent restart**: Re-run existing agents with same goals
- **Status indicators**: Color-coded agent states (running, done, failed)

**TUI Shortcuts:**
- `Enter` - Start agent (or view diff if input empty)
- `:d` - View diff for selected agent
- `:r` - Restart selected agent  
- `:c` - Clean up all agents
- `:q` - Quit
- `Ctrl+C` - Clear input
- `↑/↓` - Navigate table (when input empty or starts with `:`)

## Examples

### TUI Workflow
```bash
# Launch TUI
ags

# In TUI:
# 1. Type: "Write unit tests for the auth module" → Enter
# 2. Watch agent execute in real-time
# 3. When done, press Enter (empty input) to view diff
# 4. Use :r to restart if needed
# 5. Use :c to cleanup when satisfied
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
│   ├── *_db.py           # Database modules
│   └── tui/              # Terminal User Interface
│       └── app.py        # Textual-based TUI
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

