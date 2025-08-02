#!/usr/bin/env python3
"""Main entry point for Agent Sandbox (AGS)."""

import click


@click.command()
def main():
    """Agent Sandbox (AGS) - Sandbox for Claude Code AI agents.
    
    Use the web interface instead:
    1. Start the server: ags-server
    2. Open the web interface: ags-web
    """
    print("Agent Sandbox (AGS)")
    print("")
    print("The TUI has been replaced with a web interface.")
    print("")
    print("To use Agent Sandbox:")
    print("1. Start the server: ags-server")
    print("2. Open the web interface: ags-web")
    print("3. Access at http://localhost:8080")


if __name__ == "__main__":
    main()