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
- Docker running
- Git repository
- A Claude Code subscription

### Usage

```bash
# Start an AI agent with a specific goal
./scripts/agent.sh start feature-name "Add user authentication to the login page"

# List active agents
./scripts/agent.sh list

# Stop specific agent
./scripts/agent.sh stop feature-name

# Clean up everything
./scripts/agent.sh cleanup
```

### Example
```bash
cd example/
../scripts/agent.sh start docs "Add documentation to the main.go file"
```

## How It Works

1. **Creates isolated git worktree** in `../worktrees/<name>`
2. **Launches secure containers** (agent + proxy) with network restrictions
3. **Runs Claude Code CLI** with your specified goal
4. **Validates all actions** through hook system
5. **Cleans up** when done

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
├── scripts/
│   ├── agent.sh           # Main orchestrator
│   ├── agent-workspace.sh # Git worktree management
│   ├── agent-container.sh # Container management
│   └── agent-proxy.sh     # Proxy management
├── hooks/                 # Validation hooks
├── example/               # Sample project
├── Dockerfile.agent       # Agent container
├── Dockerfile.proxy       # Proxy container
└── tinyproxy-whitelist    # Allowed domains
```

This is essentially a **"sandbox for AI coding agents"** - letting you safely run multiple Claude Code instances on different tasks with security guardrails and isolation.