"""CLI interface for Agent Sandbox (fallback commands)."""

from pathlib import Path
import click

from .agent import AgentManager


def get_db_path() -> str:
    """Get the database path."""
    ags_dir = Path.home() / ".ags"
    ags_dir.mkdir(exist_ok=True)
    return str(ags_dir / "agents.db")


@click.group()
def cli():
    """Agent Sandbox (AGS) - CLI commands."""
    pass


@cli.command()
@click.argument("goal")
def start(goal: str):
    """Start a new agent with a specific goal."""
    manager = AgentManager(get_db_path())
    try:
        manager.start_agent(goal)
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command()
@click.argument("agent_id")
def stop(agent_id: str):
    """Stop and remove an agent by ID."""
    manager = AgentManager(get_db_path())
    try:
        manager.stop_agent(agent_id)
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command(name="list")
def list_agents():
    """List all agents."""
    manager = AgentManager(get_db_path())
    manager.list_agents()


@cli.command()
def cleanup():
    """Clean up all agents and resources."""
    manager = AgentManager(get_db_path())
    manager.cleanup_all()


@cli.command()
def auth():
    """Authenticate with Claude Code."""
    manager = AgentManager(get_db_path())
    manager.auth()


@cli.command()
@click.argument("agent_id")
def logs(agent_id: str):
    """View logs for a specific agent from the database."""
    manager = AgentManager(get_db_path())
    
    try:
        manager.show_agent_logs(agent_id)
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command()
@click.argument("agent_id")
def diff(agent_id: str):
    """Output the diff content for a specific agent."""
    manager = AgentManager(get_db_path())
    
    try:
        manager.show_diff(agent_id)
    except Exception as e:
        raise click.ClickException(str(e))


if __name__ == "__main__":
    cli()