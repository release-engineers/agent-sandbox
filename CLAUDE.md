# Agent Process - Technical Documentation for LLMs

## Project Overview

Agent Process is a sandbox system for running Claude Code AI agents in isolated, secure environments. Each agent operates in its own Docker container with network restrictions and git worktree isolation.

## Core Architecture

### Components
1. **Agent Container**: Docker container running Claude Code CLI with restricted network access
2. **Proxy Container**: Tinyproxy instance handling whitelisted domain access
3. **Git Worktrees**: Isolated git branches for parallel development
4. **Hook System**: Validation layer for all agent actions

### Directory Structure
```
agent-process/
├── scripts/
│   ├── agent.sh           # Main orchestrator script
│   ├── agent-workspace.sh # Git worktree management
│   ├── agent-container.sh # Docker container lifecycle
│   └── agent-proxy.sh     # Proxy configuration and management
├── hooks/                 # Validation hooks for agent actions
├── certs/                 # SSL certificates for proxy
├── example/               # Sample project for testing
├── Dockerfile.agent       # Agent container definition (Node.js 20 + Claude Code)
├── Dockerfile.proxy       # Proxy container definition
└── tinyproxy-whitelist    # Allowed domains list
```

## Key Commands

### Starting an Agent
```bash
./scripts/agent.sh start <agent-name> "<goal-description>"
```
- Creates git worktree at `../worktrees/<agent-name>`
- Launches Docker containers (agent + proxy)
- Runs Claude Code with specified goal
- Enforces network restrictions via proxy

### Managing Agents
```bash
./scripts/agent.sh list     # Show active agents
./scripts/agent.sh stop <name>  # Stop specific agent
./scripts/agent.sh cleanup  # Remove all agents and worktrees
```

## Technical Details

### Agent Container (Dockerfile.agent)
- **Base Image**: node:20
- **Key Packages**: git, gh, vim, jq, fzf, curl, wget
- **Claude Code**: Installed globally via npm
- **User**: Runs as non-root 'node' user with sudo access
- **Working Directory**: /workspace (mounted from git worktree)
- **Environment Variables**:
  - `CLAUDE_GOAL`: The task description for the agent
  - `CLAUDE_CONFIG_DIR`: /home/node/.claude
  - `NODE_OPTIONS`: --max-old-space-size=4096

### Network Security
- **Default Policy**: No external network access
- **Whitelisted Domains** (via tinyproxy-whitelist):
  - api.anthropic.com (Claude API)
  - github.com (Git operations)
  - npmjs.org (Package management)
  - Additional domains as needed
- **Proxy Certificate**: Self-signed cert at /usr/local/share/ca-certificates/proxy.crt

### Git Worktree Isolation
- Each agent gets isolated worktree: `../worktrees/<agent-name>`
- Branches from current HEAD
- No interference between agents
- Easy cleanup and integration

### Hook System
- Location: `/hooks/` directory in container
- Purpose: Validate and control agent actions
- Execution: Automatic via Claude Code hooks configuration

## Security Constraints

1. **Network Isolation**: Agents cannot access arbitrary external resources
2. **Domain Whitelisting**: Only pre-approved domains accessible
3. **File System Isolation**: Agents work only in their worktree
4. **Goal Scoping**: Each agent has specific, limited objective
5. **Hook Validation**: All actions pass through validation layer

## Usage Patterns

### Single Feature Development
```bash
./scripts/agent.sh start auth-feature "Implement JWT authentication"
```

### Parallel Development
```bash
./scripts/agent.sh start ui-update "Modernize dashboard UI"
./scripts/agent.sh start api-docs "Generate OpenAPI documentation"
./scripts/agent.sh start test-coverage "Add unit tests for user service"
```

### Code Review Tasks
```bash
./scripts/agent.sh start security-review "Review code for security vulnerabilities"
```

## Important Notes for LLMs

1. **Always use relative paths** within the worktree
2. **Network requests** must go through proxy (automatic via container setup)
3. **Git operations** are isolated to the worktree branch
4. **External tools** availability depends on Dockerfile.agent configuration
5. **Environment variables** from host are not passed unless explicitly configured

## Troubleshooting

### Common Issues
- **Network errors**: Check if domain is in tinyproxy-whitelist
- **Permission errors**: Ensure proper ownership of worktree files
- **Container failures**: Check Docker logs via `docker logs agent-<name>`
- **Git conflicts**: Resolve in worktree before merging

### Debug Commands
```bash
# View agent logs
docker logs agent-<name>

# Access agent container
docker exec -it agent-<name> /bin/bash

# Check proxy logs
docker logs proxy-<name>
```

## Integration Points

- **Main Branch**: Agents work on separate branches, merge via PR
- **CI/CD**: Can trigger agents for automated tasks
- **Code Review**: Agents can be spawned for review tasks
- **Testing**: Isolated environment perfect for testing changes

## Best Practices

1. **Clear Goals**: Provide specific, actionable goals to agents
2. **Resource Limits**: Monitor container resource usage
3. **Regular Cleanup**: Remove unused worktrees and containers
4. **Domain Management**: Keep whitelist minimal and secure
5. **Hook Validation**: Implement strict validation in hooks

This system enables safe, parallel AI development with strong isolation and security boundaries.