# Proxy Whitelist Extension Feature

## Overview
The agent-sandbox proxy now supports extending the domain whitelist through command-line arguments, allowing you to specify additional domains that should be accessible through the proxy beyond the default whitelist.

## Usage

### Basic Usage
```bash
# Run with default whitelist only
agent-sandbox

# Allow google.com in addition to defaults
agent-sandbox --allow google.com

# Allow multiple additional domains
agent-sandbox --allow google.com --allow bing.com --allow stackoverflow.com
```

### With Commands
```bash
# Run a command with additional domains allowed
agent-sandbox --allow google.com -- claude "help me with my code"

# Non-interactive mode with additional domains
agent-sandbox --noninteractive --allow example.com -- python script.py
```

## How It Works

1. **Default Whitelist**: The proxy starts with a default whitelist (`tinyproxy-whitelist`) containing essential domains:
   - API and documentation sites (anthropic.com domains)
   - GitHub repositories
   - Package managers (npm, pip, etc.)
   - System update repositories

2. **Dynamic Extension**: When you specify `--allow` arguments:
   - The domains are passed to the proxy container via the `ADDITIONAL_DOMAINS` environment variable
   - A startup script (`proxy-entrypoint.sh`) merges these domains with the default whitelist
   - The proxy uses the combined whitelist for filtering

3. **Multiple Domains**: You can specify multiple `--allow` arguments, each adding a domain to the whitelist

## Implementation Details

### Modified Files
- `src/sandbox.py`: Added `--allow` CLI option and `allowed_domains` parameter
- `Dockerfile.proxy`: Modified to use entrypoint script and copy whitelist as default
- `proxy-entrypoint.sh`: New script that dynamically builds the whitelist
- `tinyproxy.conf`: Unchanged, still references `/etc/tinyproxy/whitelist`

### Environment Variable
The proxy container receives additional domains via the `ADDITIONAL_DOMAINS` environment variable as a comma-separated list.

## Testing
Run the included test script to verify the argument parsing:
```bash
./venv/bin/python test_sandbox_args.py
```

## Security Considerations
- Only add trusted domains to the whitelist
- The proxy still blocks all non-whitelisted domains
- Each sandbox session can have different allowed domains
- The default whitelist remains unchanged and is always included