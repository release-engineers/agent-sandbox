#!/usr/bin/env python3
"""Main entry point for Agent Sandbox (AGS)."""

import click

from .tui.app import run_tui


@click.command()
def main():
    """Agent Sandbox (AGS) - Sandbox for Claude Code AI agents.
    
    Launches the interactive Terminal User Interface.
    """
    run_tui()


if __name__ == "__main__":
    main()