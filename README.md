# Agent Sandbox (AGS)

Run Claude Code AI agents in isolated Docker containers with network restrictions and git worktree isolation.

## What It Does

AGS creates secure, isolated environments for Claude Code agents with:
- **Client-Server Architecture**: FastAPI server manages agents, web interface as client
- **Web Interface**: Modern browser-based interface with real-time monitoring
- **Project Management**: Work with any Git repository by URL
- **Git worktrees**: Isolated workspaces with dedicated branches
- **Docker containers**: Sandboxed execution with network whitelisting
- **Diff viewer**: Built-in syntax-highlighted code review
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
# Start the server (in one terminal)
ags-server

# Start the web interface (in another terminal)
ags-web

# Open your browser to http://localhost:8080
# 1. Add Git repositories by entering their URLs
# 2. Select a project to work with
# 3. Create agents by entering goals
# 4. Monitor agent progress in real-time
# 5. View diffs and restart agents as needed

# The first run will require Claude auth to set up your credentials volume:
docker run -it --rm -v claude-code-credentials:/home/node/.claude node:20 claude auth
```

## How It Works

1. **Creates Git Worktree**: Isolated workspace at `~/.ags/worktrees/<name>`
2. **Builds Docker Images**: Agent container + proxy container
3. **Configures Security**: Sets up hooks and network restrictions
4. **Runs Claude Code**: Executes with your goal, streams output
5. **Stores Diffs**: Records changes in database for review and application

## Architecture

```
┌───────────┐     ┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│    Web    │────▶│   FastAPI    │────▶│  Agent Container│────▶│  Proxy Container │
│ Interface │     │   Server     │  ┌─▶│  (Claude Code)  │     │   (Tinyproxy)    │
└───────────┘     └──────────────┘  │  └─────────────────┘     └──────────────────┘
                          │         │  ┌─────────────────┐     ┌──────────────────┐
                          │         ├─▶│  Agent Container│────▶│  Proxy Container │
                          │         │  │  (Claude Code)  │     │   (Tinyproxy)    │
                          │         │  └─────────────────┘     └──────────────────┘
                          │         │  ┌─────────────────┐     ┌──────────────────┐
                          │         └─▶│  Agent Container│────▶│  Proxy Container │
                          │            │  (Claude Code)  │     │   (Tinyproxy)    │
                          │            └─────────────────┘     └──────────────────┘
                          ▼                      │
                      Database                   ▼
                   (~/.ags/agents.db)      Git Worktrees
                          │               (~/.ags/worktrees/<name>)
                          ▼
                    Git Clones
                (~/.ags/projects/project-<hash>)
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
ags cleanup
```

## Project Structure

```
agent-process/
├── src/                   # Modular Python source
│   ├── main.py            # CLI interface
│   ├── server.py          # FastAPI server
│   ├── api_client.py      # HTTP client for TUI
│   ├── agent.py           # Agent orchestration
│   ├── workspace.py       # Git/Docker management
│   ├── diff.py            # Diff operations
│   ├── log.py             # Log formatting
│   └── *_db.py            # Database modules
├── web/                   # Web interface
│   └── index.html         # Single-page web application
├── requirements.txt       # Dependencies (click, docker, rich, fastapi, uvicorn, requests)
├── bin/
│   ├── ags-server         # Server startup script
│   ├── ags-web            # Web interface server
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
