#!/usr/bin/env python3
"""Main entry point for Agent Sandbox (AGS)."""

import sys
import click

from .tui.app import run_tui
from .cli import cli as cli_commands


@click.group(invoke_without_command=True)
@click.option("--cli", is_flag=True, help="Use CLI interface instead of TUI")
@click.pass_context
def main(ctx, cli):
    """Agent Sandbox (AGS) - Sandbox for Claude Code AI agents.
    
    By default launches the TUI interface. Use --cli to access CLI commands.
    """
    if ctx.invoked_subcommand is None:
        if cli:
            # Show CLI help when --cli is used without subcommand
            cli_commands.main(["--help"], standalone_mode=False)
        else:
            # Launch TUI by default
            run_tui()


# Add CLI group as subcommand
main.add_command(cli_commands)


if __name__ == "__main__":
    main()