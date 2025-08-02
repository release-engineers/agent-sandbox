# Agent Sandbox

A minimal CLI tool that provides an isolated Docker environment for safe experimentation.

## Features

- **Isolated Environment**: Each sandbox runs in its own Docker container with dedicated network
- **Copy-on-Write Workspace**: Creates a temporary copy of your current directory  
- **Interactive Shell**: Bash shell with development tools and Claude Code pre-installed
- **Automatic Diff Generation**: Generates a patch file of all changes when you exit
- **Network Isolation**: Each sandbox gets its own network and proxy container
- **Hook Support**: Mounts validation hooks for Claude Code if used

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Make the binary executable
chmod +x bin/agent-sandbox

# Add to your PATH (optional)
export PATH=$PATH:/path/to/agent-sandbox/bin
```

## Usage

### Basic Usage

```bash
# Launch an interactive sandbox
agent-sandbox

# The tool will:
# 1. Build Docker images (if needed)
# 2. Create a temporary copy of your current directory
# 3. Start a proxy container for network isolation
# 4. Launch an interactive bash shell in the container
# 5. Generate a diff file when you exit
```


## What's Included

The sandbox container includes:
- Node.js 20 with Claude Code CLI pre-installed
- Git, GitHub CLI (gh)
- Development tools: vim, fzf, jq, curl, wget
- Go programming language
- sudo access for the node user

## Example

```bash
$ agent-sandbox
→ Building Docker images...
  ✓ Agent image built
  ✓ Proxy image built
→ Creating workspace copy at /tmp/agent-sandbox-20240108-143022-abc123/workspace
→ Created Claude settings with hooks
→ Creating Docker network: agent-network-sandbox-20240108-143022
→ Starting proxy container: proxy-sandbox-20240108-143022
→ Starting interactive shell...

node@container:/workspace$ # You're now in the sandbox!
node@container:/workspace$ npm install express
node@container:/workspace$ echo "console.log('test')" > test.js
node@container:/workspace$ exit

→ Generating diff...
  ✓ Diff saved to: sandbox-diff-sandbox-20240108-143022.patch

→ Starting cleanup...
→ Stopping proxy container: proxy-sandbox-20240108-143022
  ✓ Proxy container stopped
→ Removing network: agent-network-sandbox-20240108-143022
  ✓ Network removed
→ Removing temporary workspace: /tmp/agent-sandbox-20240108-143022-abc123
  ✓ Temporary workspace removed

✓ Cleanup completed
```

## Network Isolation

Each sandbox runs with:
- **Dedicated Docker network**: Isolated from other sandboxes and the host
- **Unique proxy container**: Each sandbox gets its own proxy instance
- **Whitelisted domains only**: By default, only these domains are accessible:
  - api.anthropic.com
  - docs.anthropic.com
  - github.com
  - githubusercontent.com
  - sentry.io

## Hooks

The sandbox automatically mounts hooks from the `hooks/` directory to control Claude Code behavior:
- `pre-any`: Logs all tool usage
- `pre-bash`: Validates bash commands before execution
- `pre-writes`: Validates file modifications
- `post-writes`: Actions after file changes
- `post-stop`: Cleanup actions

## Applying Changes

To apply the changes from a sandbox session to your actual project:

```bash
# Review the diff first
cat sandbox-diff-*.patch

# Apply the patch
git apply sandbox-diff-*.patch
```

## Docker Images

The tool uses two Docker images:

1. **claude-code-agent**: The main container with development tools
2. **claude-code-proxy**: Tinyproxy for network isolation

These are built automatically on first run or can be rebuilt with `--rebuild`.

## Requirements

- Python 3.8+
- Docker
- Git