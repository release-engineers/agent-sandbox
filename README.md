# Agent Process - Sandbox for AI Coding Agents

A sandbox for running Claude Code AI agents in isolated environments.

## What It Does

Creates **isolated workspaces** where each Claude Code agent:
- Gets its own git worktree (parallel development branch)
- Runs in a Docker container with network restrictions  
- Has a specific goal to accomplish
- Can only access whitelisted external domains through a proxy

## Quick Start

### Prerequisites
- Python 3.9+
- Docker running
- Git repository
- A Claude Code subscription

### Installation

```bash
# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Usage

```bash
# Run an AI agent with a specific goal
./agent.py start feature-name "Add user authentication to the login page"

# List agent branches (with committed changes)
./agent.py list

# Clean up everything
./agent.py cleanup

# Authenticate with Claude Code (run once)
./agent.py auth
```

### Example
```bash
cd example/
source ../venv/bin/activate
../agent.py start docs "Add documentation to the main.go file"
# Agent runs, shows output, commits changes, and exits
```

## How It Works

1. **Creates isolated git worktree** in `../worktrees/<name>` with branch `agent--<name>`
2. **Launches secure containers** (agent + proxy) with network restrictions
3. **Runs Claude Code CLI** with your specified goal, streaming output
4. **Validates all actions** through hook system
5. **Commits changes** to branch `agent--<name>` and cleans up when complete (excluding .claude configuration)

## Security Features

- **Network Isolation**: Agents can't access arbitrary external resources
- **Domain Whitelisting**: Only approved domains accessible (Anthropic API, GitHub, etc.)
- **Hook Validation**: All agent actions go through validation hooks
- **Goal-Scoped Execution**: Each agent has a specific, limited objective

## Use Cases

- **Parallel Development**: Run multiple agents on different features simultaneously
- **Safe AI Development**: Let AI agents work on code with security constraints
- **Experimentation**: Test AI agents on code changes without affecting main branch
- **Code Review**: Have agents work on specific review tasks in isolation

## Directory Structure

```
agent-process/
├── agent.py               # Main Python implementation
├── requirements.txt       # Python dependencies
├── .gitignore             # Excludes .claude/ and worktrees/
├── hooks/                 # Validation hooks
├── certs/                 # SSL certificates for proxy
├── example/               # Sample project
├── Dockerfile.agent       # Agent container
├── Dockerfile.proxy       # Proxy container
├── tinyproxy-whitelist    # Allowed domains
└── tinyproxy.conf         # Proxy configuration
```

This is essentially a **"sandbox for AI coding agents"** - letting you safely run multiple Claude Code instances on different tasks with security guardrails and isolation.