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

# Add to your PATH (optional)
export PATH=$PATH:/path/to/agent-sandbox/bin
```

## Usage

```bash
# Launch Claude Code in a sandbox
cd my-git-project
agent-sandbox -- claude --dangerously-skip-permissions --print "Set up a simple FastAPI project."

# Run without interactive TTY

agent-sandbox --noninteractive -- echo "Hello from sandbox"

# The tool will:
# 1. Create a temporary copy of your current directory
# 2. Start a proxy container for network isolation
# 3. Start an agent container with access only to the proxy
# 4. Run your command or launch an interactive shell
# 5. Place a diff of the changes after the sandbox closes
```


## What's Included

The sandbox container includes:
- Node.js 20 with Claude Code CLI pre-installed
- Your host's `.claude.json` configuration mounted
- A Docker volume to persist Claude Code credentials
- Common development tools: Git, GitHub CLI, vim, curl and [more](Dockerfile.agent)
- sudo access

## Examples

### Interactive Session
```bash
$ agent-sandbox
✓ Agent sandbox ready

node@container:/workspace$ # You're now in the sandbox!
node@container:/workspace$ npm install express
node@container:/workspace$ echo "console.log('test')" > test.js
node@container:/workspace$ exit

→ Diff saved to: sandbox-diff-sandbox-20240108-143022.patch
```

### Running Commands
```bash
# Create a file in the sandbox
$ agent-sandbox touch example.md
✓ Agent sandbox ready

→ Diff saved to: sandbox-diff-sandbox-20240108-143023.patch
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

The sandbox generates a diff of all changes (including new files) when you exit, respecting `.gitignore` rules.

```bash
# Review the diff
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
- Claude CLI JSON (`~/.claude.json` must exist)
