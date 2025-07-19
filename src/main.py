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
@click.argument("goal")
def start(goal: str):
    """Start a new agent with a specific goal."""
    ags_dir = Path.home() / ".ags"
    ags_dir.mkdir(exist_ok=True)
    db_path = str(ags_dir / "agents.db")
    
    manager = AgentManager(db_path)
    try:
        manager.start_agent(goal)
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command()
@click.argument("agent_id")
def stop(agent_id: str):
    """Stop and remove an agent by ID."""
    ags_dir = Path.home() / ".ags"
    ags_dir.mkdir(exist_ok=True)
    db_path = str(ags_dir / "agents.db")
    
    manager = AgentManager(db_path)
    try:
        manager.stop_agent(agent_id)
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
@click.argument("agent_id")
def logs(agent_id: str):
    """View logs for a specific agent from the database."""
    ags_dir = Path.home() / ".ags"
    ags_dir.mkdir(exist_ok=True)
    db_path = str(ags_dir / "agents.db")
    
    manager = AgentManager(db_path)
    
    try:
        manager.show_agent_logs(agent_id)
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command()
@click.argument("agent_id")
def diff(agent_id: str):
    """Output the diff content for a specific agent."""
    ags_dir = Path.home() / ".ags"
    ags_dir.mkdir(exist_ok=True)
    db_path = str(ags_dir / "agents.db")
    
    manager = AgentManager(db_path)
    
    try:
        manager.show_diff(agent_id)
    except Exception as e:
        raise click.ClickException(str(e))


if __name__ == "__main__":
    cli()