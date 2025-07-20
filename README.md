# Agent Process - Docker-based Claude Code Workflow

A containerized workflow system for running Claude Code with network isolation, HTTP proxy, and git worktree management.

## Overview

This system provides a secure, isolated environment for running Claude Code agents with:
- Docker containers with network restrictions
- HTTP proxy with domain whitelisting
- Git worktree management for parallel development
- Pre/post execution hooks for validation
- Self-signed certificate management

## Quick Start

### Prerequisites
- Docker installed and running
- Git repository with committed changes
- Node.js (for certificate generation)

### Basic Usage

1. **From any git project directory:**
   ```bash
   # Start an agent with worktree + container
   /path/to/agent-process/scripts/agent.sh start my-feature
   
   # Stop and cleanup
   /path/to/agent-process/scripts/agent.sh stop my-feature
   
   # List active agents
   /path/to/agent-process/scripts/agent.sh list
   ```

2. **From the example project:**
   ```bash
   cd example/
   ../scripts/agent.sh start hello-world
   ```

## Architecture

### Components

- **Agent Container** (`claude-code-agent`) - Runs Claude Code in isolated network
- **Proxy Container** (`container-proxy.local`) - Provides HTTP proxy with domain filtering
- **Git Worktrees** - Parallel development environments
- **Hooks System** - Pre/post execution validation

### Network Isolation

The agent container can only access external resources through the HTTP proxy, which filters requests to allowed domains. See [tinyproxy-whitelist](tinyproxy-whitelist) for an actual list.

## Scripts

### `scripts/agent.sh`
Main orchestration script for the complete workflow.

```bash
# Commands
agent.sh start <name>    # Create worktree and start container
agent.sh stop <name>     # Stop container and remove worktree
agent.sh list            # List active agents
```

### `scripts/worktree.sh`
Git worktree management.

```bash
# Commands
worktree.sh create <name>  # Create new worktree
worktree.sh remove <name>  # Remove worktree
worktree.sh list           # List all worktrees
```

### `scripts/container.sh`
Docker container management.

```bash
# Usage
container.sh [container-name]  # Start container with optional name
```

## Configuration Files

### Docker Images
- `Dockerfile.agent` - Claude Code agent container
- `Dockerfile.proxy` - Tinyproxy container

### Proxy Configuration
- `tinyproxy.conf` - Tinyproxy settings
- `tinyproxy-whitelist` - Allowed domains

### Certificates
- `certs/proxy.crt` - Self-signed certificate
- `certs/proxy.key` - Private key

### Hooks
- `hooks/pre-bash` - Validates bash commands
- `hooks/pre-writes` - Validates file operations
- `hooks/post-writes` - Post-operation actions
- `hooks/post-stop` - Cleanup on stop

## Directory Structure

```
agent-process/
├── scripts/
│   ├── agent.sh          # Main workflow orchestrator
│   ├── worktree.sh       # Git worktree management
│   └── container.sh      # Docker container management
├── hooks/                # Execution hooks
├── certs/                # SSL certificates
├── example/              # Sample Go project
├── Dockerfile.agent      # Agent container definition
├── Dockerfile.proxy      # Proxy container definition
├── tinyproxy.conf        # Proxy configuration
├── tinyproxy-whitelist   # Allowed domains
└── FEATURES.md           # Implementation status
```

## Workflow

1. **Agent Start Process:**
   - Creates git worktree in `../worktrees/<name>`
   - Changes to worktree directory
   - Builds Docker images if needed
   - Creates isolated network
   - Starts proxy container with external access
   - Starts agent container with network restrictions
   - Mounts worktree as `/workspace`

2. **Agent Stop Process:**
   - Stops and removes agent container
   - Removes git worktree
   - Cleans up resources

## Security Features

- **Network Isolation**: Agent container cannot access external networks directly
- **Domain Filtering**: HTTP proxy restricts access to whitelisted domains
- **Certificate Trust**: Self-signed certificates embedded in system CA bundle
- **Hook System**: Pre/post execution validation and quality controls
- **Volume Isolation**: Persistent volumes for bash history and Claude config

## Example Project

The `example/` directory contains a minimal Go Hello World application that demonstrates the workflow:

```go
package main

import "fmt"

func main() {
    fmt.Println("Hello, World!")
}
```

## Troubleshooting

### Common Issues

1. **Docker not running**: Ensure Docker daemon is started
2. **Not in git repository**: Run from within a git project
3. **Port conflicts**: Proxy uses port 3128
4. **Certificate issues**: Rebuild images to refresh certificates

### Debugging

```bash
# Check container logs
docker logs <container-name>

# Check proxy connectivity
docker exec <container-name> curl -I http://172.20.0.10:3128

# List networks
docker network ls
```
