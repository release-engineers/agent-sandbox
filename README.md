# Agent Sandbox

`agent-sandbox` runs a sandbox for AI agents like Claude; containers with their own copy of your working directory, each with a dedicated Docker network and proxy to limit access to the internet. When an agent exits, a `git diff` of its changes is written to your original working directory.

```bash
cd fastapi-project
agent-sandbox -- claude --dangerously-skip-permissions --print "Set up a FastAPI project."

# (after ~49 seconds)
# → Diff saved to: sandbox-diff-sandbox-20250804-182437.patch

cat *.patch
# diff --git a/fastapi-project/main.py b/fastapi-project/main.py
# new file mode 100644
# index 0000000..7ed4338
# --- /dev/null
# +++ b/fastapi-project/main.py
# @@ -0,0 +1,11 @@
# +from fastapi import FastAPI
# +
# +app = FastAPI()
# +
# +@app.get("/")
# +async def root():
# +    return {"message": "Hello World"}
# (...)
```

When using specifically `claude` with `--print`, be aware that it does not stream output and may appear to hang.

## Features

- **Isolated Environment**: Each sandbox runs in its own Docker container with dedicated network
- **Copy-on-Write Workspace**: Creates a temporary copy of your current directory  
- **Interactive Shell**: Bash shell with development tools and [Claude Code pre-installed](Dockerfile.agent)
- **Automatic Diff Generation**: Generates a patch file of all changes when you exit
- **Network Isolation**: Each sandbox gets its own network and [proxy container](Dockerfile.proxy)
- **Network Whitelist**: Only allow access to [whitelisted domains](tinyproxy-whitelist)
- **Hook Support**: Mounts validation [hooks for Claude Code](hooks/)

## Installation

```bash
# Add to your PATH
export PATH=$PATH:/path/to/agent-sandbox/bin
```

## Usage

```bash
# Usage: sandbox.py [OPTIONS] [COMMAND]...
#
#   Launch an agent sandbox environment.
#
#   COMMAND: Optional command to run in the sandbox. If not provided, launches
#   an interactive shell.
#
# Options:
#   --noninteractive  Run without interactive TTY
#   --help            Show this message and exit.
```

## Applying Changes

The sandbox generates a diff of all changes (including new files) when you exit, respecting `.gitignore` rules.

```bash
# Review the diff
cat sandbox-diff-*.patch

# Apply the patch
git apply sandbox-diff-*.patch
```

## Requirements

- Python 3.8+
- Docker
- Git
- Claude CLI JSON (`~/.claude.json` must exist)
