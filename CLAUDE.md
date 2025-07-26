# Agent Process - LLM Technical Documentation

## Project Overview for LLMs

Agent Process is a sandbox system for running Claude Code AI agents in isolated environments. This documentation provides technical details for LLMs working on or maintaining this project.

**Key Point**: This system creates isolated workspaces where Claude Code agents can work safely without affecting the main codebase or accessing unauthorized resources.

## Core Architecture

### Components
1. **Agent Container**: Docker container running Claude Code CLI with restricted network access
2. **Proxy Container**: Tinyproxy instance handling whitelisted domain access
3. **Git Worktrees**: Isolated git branches for parallel development
4. **Hook System**: Validation layer for all agent actions

### Directory Structure
```
agent-process/
├── hooks/                 # Validation hooks for agent actions
├── certs/                 # SSL certificates for proxy
├── example/               # Sample project for testing
├── agent.py               # Python implementation
├── requirements.txt       # Python dependencies
├── Dockerfile.agent       # Agent container definition (Node.js 20 + Claude Code)
├── Dockerfile.proxy       # Proxy container definition
├── tinyproxy-whitelist    # Allowed domains list
└── tinyproxy.conf         # Proxy configuration
```

## Key Commands

### Starting an Agent
```bash
./agent.py start <agent-name> "<goal-description>"
```
- Creates git worktree at `../worktrees/<agent-name>`
- Launches Docker containers (agent + proxy)
- Runs Claude Code with specified goal
- Enforces network restrictions via proxy

### Managing Agents
```bash
./agent.py list        # Show agent branches with committed changes
./agent.py cleanup     # Remove all agents and worktrees
./agent.py auth        # Authenticate with Claude Code
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
./agent.py start auth-feature "Implement JWT authentication"
```

### Parallel Development
```bash
./agent.py start ui-update "Modernize dashboard UI"
./agent.py start api-docs "Generate OpenAPI documentation"
./agent.py start test-coverage "Add unit tests for user service"
```

### Code Review Tasks
```bash
./agent.py start security-review "Review code for security vulnerabilities"
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
- **Container failures**: Check Docker logs via `docker logs <agent-name>`
- **Git conflicts**: Resolve in worktree before merging

### Debug Commands
```bash
# View agent logs
docker logs <agent-name>

# Access agent container
docker exec -it <agent-name> /bin/bash

# Check proxy logs
docker logs proxy-<agent-name>
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

## Implementation Details

The system is implemented as a single Python file (`agent.py`) with the following key characteristics:

### Architecture
- **Single-file design**: All functionality in one ~250-line Python script
- **Simple dependencies**: Only `click` (CLI) and `docker` (container management)
- **Direct approach**: Uses subprocess for git operations, docker-py for containers

### Key Classes and Functions
- `AgentManager`: Main class handling all operations
- `start_agent()`: Creates worktree, runs agent, commits changes, and cleans up
- `list_agents()`: Shows agent branches with committed changes
- `cleanup_all()`: Removes all agents and resources
- `_cleanup_and_commit()`: Internal method for cleanup and git operations

### Container Management
- **Agent containers**: Use `claude-code-agent` image with Claude Code CLI
- **Proxy containers**: Use `claude-code-proxy` image with tinyproxy
- **Network isolation**: All containers run on `agent-network`
- **Volume mounts**: Worktree mounted to `/workspace`, credentials to `/home/node/.claude`

### Git Operations
- **Worktrees**: Created in `../worktrees/<agent-name>`
- **Branches**: Named `agent--<name>` 
- **Isolation**: Each agent gets its own branch and workspace
- **Commit Process**: Changes are automatically committed to `agent--<name>` branch on completion
- **Cleanup**: Worktrees are removed, branches remain with committed changes
- **Exclusions**: .claude/ folders are excluded from commits via .gitignore

### Configuration Management
- **Claude settings**: Generated in `.claude/settings.json` within each worktree
- **Hooks**: Pre-configured validation hooks for security
- **Environment**: Proxy settings automatically configured

## LLM Development Guidelines

### When Working on This Project
1. **Maintain simplicity**: The Python implementation should remain simple and readable
2. **Test thoroughly**: Always test container operations and git worktree management
3. **Handle errors gracefully**: Docker and git operations can fail, handle appropriately
4. **Preserve security**: Don't weaken network isolation or hook validation
5. **Document changes**: Update both README.md and CLAUDE.md
6. **Protect .claude/**: Ensure .claude/ folders remain in .gitignore

### Common Maintenance Tasks
- **Adding new domains**: Update `tinyproxy-whitelist` file
- **Modifying hooks**: Edit files in `hooks/` directory
- **Container updates**: Modify `Dockerfile.agent` or `Dockerfile.proxy`
- **Python updates**: Modify `agent.py` and update `requirements.txt`

### Testing Approach
```bash
# Test from example directory
cd example/
source ../venv/bin/activate
../agent.py start test "Simple test task"
../agent.py list
../agent.py stop test
```