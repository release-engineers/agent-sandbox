#!/usr/bin/env python3
"""CLI interface exposing agent.py functionality."""

from pathlib import Path
import click

from .agent import AgentManager


@click.group()
def cli():
    """Agent Sandbox (AGS) - Sandbox for Claude Code AI agents."""
    pass


@cli.command()
@click.argument("name")
@click.argument("goal")
def start(name: str, goal: str):
    """Start a new agent with a specific goal."""
    ags_dir = Path.home() / ".ags"
    ags_dir.mkdir(exist_ok=True)
    db_path = str(ags_dir / "agents.db")
    
    manager = AgentManager(db_path)
    try:
        manager.start_agent(name, goal)
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command()
@click.argument("name")
def stop(name: str):
    """Stop and remove an agent."""
    ags_dir = Path.home() / ".ags"
    ags_dir.mkdir(exist_ok=True)
    db_path = str(ags_dir / "agents.db")
    
    manager = AgentManager(db_path)
    try:
        manager.stop_agent(name)
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command(name="list")
def list_agents():
    """List all active agents."""
    ags_dir = Path.home() / ".ags"
    ags_dir.mkdir(exist_ok=True)
    db_path = str(ags_dir / "agents.db")
    
    manager = AgentManager(db_path)
    manager.list_agents()


@cli.command()
def cleanup():
    """Clean up all agents and resources."""
    ags_dir = Path.home() / ".ags"
    ags_dir.mkdir(exist_ok=True)
    db_path = str(ags_dir / "agents.db")
    
    manager = AgentManager(db_path)
    manager.cleanup_all()


@cli.command()
def auth():
    """Authenticate with Claude Code."""
    ags_dir = Path.home() / ".ags"
    ags_dir.mkdir(exist_ok=True)
    db_path = str(ags_dir / "agents.db")
    
    manager = AgentManager(db_path)
    manager.auth()


@cli.command()
@click.argument("name")
def logs(name: str):
    """View logs for a specific agent from the database."""
    ags_dir = Path.home() / ".ags"
    ags_dir.mkdir(exist_ok=True)
    db_path = str(ags_dir / "agents.db")
    
    manager = AgentManager(db_path)
    
    try:
        manager.show_agent_logs(name)
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command()
@click.argument("agent_name")
def apply(agent_name: str):
    """Apply a specific diff by agent name."""
    ags_dir = Path.home() / ".ags"
    ags_dir.mkdir(exist_ok=True)
    db_path = str(ags_dir / "agents.db")
    
    manager = AgentManager(db_path)
    
    try:
        manager.apply_diff(agent_name)
    except Exception as e:
        raise click.ClickException(str(e))


if __name__ == "__main__":
    cli()