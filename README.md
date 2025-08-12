# Agent Sandbox

`agent-sandbox` makes it easy to sandbox agents like Claude. These sandboxes are containers each with their own copy of your working directory, a dedicated Docker network and HTTP(S) proxy to limit access to the internet. When an agent completes, it yields a `.patch` file of its changes to your original working directory.

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

> [!WARNING]  
> When using `claude` with `--print`, be aware that it does not stream output and until Claude fully completes it will appear to hang.

## Requirements

- Python 3.8+
- Docker
- Git
- Claude CLI JSON (`~/.claude.json` must exist)

## Installation

```bash
# Add to your PATH
export PATH=$PATH:/path/to/agent-sandbox/bin

# Set up the authentication volume by running an interactive sandbox
agent-sandbox
# > claude
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
#   --allow DOMAIN    Allow additional domain through proxy (can be used multiple times)
#   --help            Show this message and exit.
```

Generated patch files are named `sandbox-diff-<timestamp>.patch`, and can be applied to your original working directory with `git apply`.

### Extending Proxy Whitelist

By default, the sandbox proxy only allows connections to [whitelisted domains](tinyproxy-whitelist). You can extend this whitelist using the `--allow` option:

```bash
# Allow google.com in addition to defaults
agent-sandbox --allow google.com -- claude "help me with my code"

# Allow multiple additional domains
agent-sandbox --allow google.com --allow stackoverflow.com -- python script.py
```

## Features

- **Isolated Environment**: Each sandbox runs in its own Docker container with dedicated network
- **Copy-on-Write Workspace**: Creates a temporary copy of your current directory  
- **Interactive Shell**: Bash shell with development tools and [Claude Code pre-installed](Dockerfile.agent)
- **Automatic Diff Generation**: Generates a patch file of all changes when you exit
- **Network Isolation**: Each sandbox gets its own network and [proxy container](Dockerfile.proxy)
- **Network Whitelist**: Only allow access to [whitelisted domains](tinyproxy-whitelist)
- **Hook Support**: Mounts validation [hooks for Claude Code](hooks/)
