#!/usr/bin/env python3
"""Simple agent process manager for Claude Code."""

import sys
import json
import subprocess
import threading
import time
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import re

import click
import docker
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.syntax import Syntax
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich import print as rprint


class AgentManager:
    """Manages Claude Code agents with Docker and git worktrees."""
    
    def __init__(self):
        self.console = Console()
        try:
            self.docker = docker.from_env()
        except Exception as e:
            self.console.print(Panel(
                f"[bold red]Error connecting to Docker[/bold red]\n\n{e}\n\nPlease ensure Docker is running and try again.",
                title="Docker Connection Error",
                border_style="red"
            ))
            sys.exit(1)
        self.git_root = self._get_git_root()
        self.worktree_dir = self.git_root.parent / "worktrees"
        self.worktree_dir.mkdir(exist_ok=True)
        
    def _get_git_root(self) -> Path:
        """Get git repository root."""
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        return Path(result.stdout.strip())
    
    def _run_command(self, cmd: list[str]) -> subprocess.CompletedProcess:
        """Run a command and return result."""
        return subprocess.run(cmd, capture_output=True, text=True)
    
    def _format_log_line(self, line: str):
        """Format log lines with rich styling."""
        # Skip empty lines
        if not line.strip():
            return
            
        # Handle [LOG] prefixed lines from hooks
        if line.startswith('[LOG]'):
            # Remove the [LOG] prefix
            line = line[5:].strip()
            
            # Parse timestamp if present
            timestamp_match = re.match(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\]\s*(.*)', line)
            if timestamp_match:
                timestamp, content = timestamp_match.groups()
                
                # Parse the hook event and tool
                event_match = re.match(r'(\w+):\s*(\w+)\s*-\s*(.*)', content)
                if event_match:
                    event, tool, details = event_match.groups()
                    
                    # Color code by tool type
                    tool_colors = {
                        'Task': 'magenta',
                        'Read': 'blue',
                        'Write': 'green',
                        'Edit': 'green',
                        'MultiEdit': 'green',
                        'Bash': 'yellow',
                        'Grep': 'cyan',
                        'Glob': 'cyan',
                        'LS': 'blue',
                        'TodoWrite': 'purple',
                        'WebSearch': 'red',
                        'WebFetch': 'red'
                    }
                    
                    tool_icons = {
                        'Task': '🎯',
                        'Read': '📖',
                        'Write': '📝',
                        'Edit': '✏️',
                        'MultiEdit': '✏️',
                        'Bash': '💻',
                        'Grep': '🔍',
                        'Glob': '🔍',
                        'LS': '📁',
                        'TodoWrite': '📋',
                        'WebSearch': '🌐',
                        'WebFetch': '🌐'
                    }
                    
                    color = tool_colors.get(tool, 'white')
                    icon = tool_icons.get(tool, '🔧')
                    
                    # Format the output
                    time_str = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f').strftime('%H:%M:%S')
                    self.console.print(
                        f"[dim]{time_str}[/dim] {icon} [{color}]{tool}[/{color}] {details}"
                    )
                else:
                    # Fallback formatting
                    self.console.print(f"[dim]{timestamp}[/dim] {content}")
            else:
                # No timestamp, just print the content
                self.console.print(f"[yellow]{line}[/yellow]")
        else:
            # Regular output from the agent
            self.console.print(line)
    
    def _cleanup_existing_agent(self, name: str):
        """Clean up any existing agent environment."""
        # Stop and remove containers
        for container_name in [name, f"proxy-{name}"]:
            try:
                container = self.docker.containers.get(container_name)
                self.console.print(f"[yellow]⏹  Stopping existing container:[/yellow] {container_name}")
                container.stop()
                container.remove()
            except docker.errors.NotFound:
                pass
        
        # Remove existing worktree
        worktree_path = self.worktree_dir / name
        if worktree_path.exists():
            self.console.print(f"[yellow]🗑  Removing existing worktree:[/yellow] {worktree_path}")
            # Force remove the worktree
            self._run_command(["git", "worktree", "remove", "--force", str(worktree_path)])
        
        # Check if branch exists and delete it
        branch_name = f"agent--{name}"
        result = self._run_command(["git", "branch", "--list", branch_name])
        if result.stdout.strip():
            self.console.print(f"[yellow]🔀 Deleting existing branch:[/yellow] {branch_name}")
            self._run_command(["git", "branch", "-D", branch_name])
    
    def start_agent(self, name: str, goal: str):
        """Start a new agent."""
        self.console.print(Panel(
            f"[bold cyan]Agent Name:[/bold cyan] {name}\n[bold cyan]Goal:[/bold cyan] {goal}",
            title="🚀 Starting Agent",
            border_style="cyan"
        ))
        
        # Clean up any existing environment for this name
        self._cleanup_existing_agent(name)
        
        # Create worktree
        worktree_path = self.worktree_dir / name
        
        with self.console.status("[cyan]Creating worktree...[/cyan]", spinner="dots") as status:
            result = self._run_command([
                "git", "worktree", "add", str(worktree_path), "-b", f"agent--{name}"
            ])
            if result.returncode != 0:
                raise click.ClickException(f"Failed to create worktree: {result.stderr}")
            status.update("[green]✓ Worktree created[/green]")
        
        # Setup Claude settings
        claude_dir = worktree_path / ".claude"
        claude_dir.mkdir(exist_ok=True)
        
        settings = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": ".*", "hooks": [{"type": "command", "command": "/hooks/pre-any"}]},
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": "/hooks/pre-bash"}]},
                    {"matcher": "Write|Edit|MultiEdit", "hooks": [{"type": "command", "command": "/hooks/pre-writes"}]}
                ],
                "PostToolUse": [
                    {"matcher": "Write|Edit|MultiEdit", "hooks": [{"type": "command", "command": "/hooks/post-writes"}]}
                ],
                "Stop": [
                    {"matcher": ".*", "hooks": [{"type": "command", "command": "/hooks/stop"}]}
                ]
            }
        }
        
        with open(claude_dir / "settings.json", "w") as f:
            json.dump(settings, f, indent=2)
        
        # Build images
        agent_process_dir = Path(__file__).parent
        
        # Build images with progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console
        ) as progress:
            build_task = progress.add_task("[cyan]Building Docker images...[/cyan]", total=2)
            
            self.docker.images.build(
                path=str(agent_process_dir),
                dockerfile="Dockerfile.agent",
                tag="claude-code-agent"
            )
            progress.update(build_task, advance=1, description="[green]✓ Agent image built[/green]")
            
            self.docker.images.build(
                path=str(agent_process_dir),
                dockerfile="Dockerfile.proxy",
                tag="claude-code-proxy"
            )
            progress.update(build_task, advance=1, description="[green]✓ All images built[/green]")
        
        # Create network if needed
        try:
            self.docker.networks.get("agent-network")
        except docker.errors.NotFound:
            self.docker.networks.create("agent-network")
        
        # Start proxy container
        with self.console.status("[cyan]Starting proxy container...[/cyan]", spinner="dots"):
            self.docker.containers.run(
                "claude-code-proxy",
                name=f"proxy-{name}",
                network="agent-network",
                detach=True,
                auto_remove=True
            )
            self.console.print("[green]✓ Proxy container started[/green]")
        
        # Start agent container
        self.console.print("\n[bold cyan]🤖 Starting agent container...[/bold cyan]")
        
        temp_log_dir = None
        try:
            # Create log directory in a temporary location on the host
            temp_log_dir = tempfile.mkdtemp(prefix=f"ags-{name}-logs-")
            log_dir = Path(temp_log_dir)
            log_file = log_dir / "ags.log"
            log_file.touch()
            self.console.print(f"[dim]Log directory: {log_dir}[/dim]")
            
            # Add GOAL amendment with completion instructions
            goal_amendment = goal + """

Important: After you complete your work, commit all of it in one large commit. Run git status and similar tools beforehand to ensure you do not commit any files accidentally. If you happen to have documented your plans in a file in the workspace, remove these files too."""

            # Create and start container to properly stream output
            container = self.docker.containers.create(
                "claude-code-agent",
                name=name,
                network="agent-network",
                environment={
                    "CLAUDE_GOAL": goal_amendment,
                    "HTTP_PROXY": f"http://proxy-{name}:3128",
                    "HTTPS_PROXY": f"http://proxy-{name}:3128"
                },
                volumes={
                    str(worktree_path): {"bind": "/workspace", "mode": "rw"},
                    "claude-code-credentials": {"bind": "/home/node/.claude", "mode": "rw"},
                    str(log_dir): {"bind": "/var/log", "mode": "rw"}
                },
                working_dir="/workspace",
                user="node",
                auto_remove=True
            )
            
            # Start container
            container.start()
            
            # Tail the log file instead of container logs
            import threading
            import time
            
            def tail_log_file():
                """Tail the log file and print new lines."""
                with open(log_file, 'r') as f:
                    # Move to end of file
                    f.seek(0, 2)
                    while container.status in ['running', 'created']:
                        line = f.readline()
                        if line:
                            self._format_log_line(line.rstrip())
                        else:
                            time.sleep(0.1)
            
            # Start tailing in a separate thread
            tail_thread = threading.Thread(target=tail_log_file)
            tail_thread.daemon = True
            tail_thread.start()
            
            # Also stream regular container logs
            for line in container.logs(stream=True, follow=True):
                decoded_line = line.decode('utf-8', errors='ignore').rstrip()
                if decoded_line and not decoded_line.startswith('[LOG]'):
                    self.console.print(f"[dim]{decoded_line}[/dim]")
            
            # Wait for completion
            result = container.wait()
            if result['StatusCode'] == 0:
                self.console.print("\n[bold green]✅ Agent completed successfully[/bold green]")
            else:
                self.console.print(f"\n[bold red]❌ Agent failed with exit code: {result['StatusCode']}[/bold red]")
            
        except Exception as e:
            self.console.print(f"\n[bold red]❌ Agent failed:[/bold red] {e}")
        finally:
            # Clean up temporary log directory
            if temp_log_dir and Path(temp_log_dir).exists():
                self.console.print(f"[dim]Cleaning up temporary log directory...[/dim]")
                shutil.rmtree(temp_log_dir)
            
        # Now clean up and commit changes
        self._cleanup_and_commit(name)
        
    def _cleanup_and_commit(self, name: str):
        """Clean up containers and commit changes."""
        self.console.print("\n[bold]🧿 Cleaning up and committing changes...[/bold]")
        
        # Stop containers (they may already be removed due to auto_remove=True)
        for container_name in [name, f"proxy-{name}"]:
            try:
                container = self.docker.containers.get(container_name)
                container.stop()
                self.console.print(f"[green]✓ Stopped {container_name}[/green]")
            except docker.errors.NotFound:
                # Container already removed (auto_remove=True)
                pass
        
        # Handle worktree changes
        worktree_path = self.worktree_dir / name
        if worktree_path.exists():
            # Stage all changes
            self._run_command(["git", "-C", str(worktree_path), "add", "."])
            
            # Commit changes
            commit_result = self._run_command([
                "git", "-C", str(worktree_path), "commit", "-m", 
                f"Agent {name} changes\n\nAutomatically committed by agent-process"
            ])
            
            # Show what happened
            if commit_result.stdout:
                self.console.print(Panel(
                    commit_result.stdout,
                    title="Git Commit Output",
                    border_style="green"
                ))
            if commit_result.stderr and commit_result.returncode != 0:
                self.console.print(Panel(
                    commit_result.stderr,
                    title="Git Commit Error",
                    border_style="red"
                ))
            
            # Remove worktree
            self._run_command(["git", "worktree", "remove", str(worktree_path)])
            self.console.print(f"[green]✓ Removed worktree[/green]")
        
        self.console.print(f"\n[bold green]🎉 Agent {name} completed successfully[/bold green]")
        
    def list_agents(self):
        """List agent branches."""
        table = Table(title="Agent Branches", show_header=True, header_style="bold cyan")
        table.add_column("Branch Name", style="yellow")
        table.add_column("Agent Name", style="white")
        
        # Get agent branches
        result = self._run_command(["git", "branch"])
        agent_branches = []
        for line in result.stdout.strip().split("\n"):
            branch = line.strip().lstrip("* ")
            if branch.startswith("agent--"):
                agent_branches.append(branch)
        
        if not agent_branches:
            self.console.print("[dim]No agent branches found[/dim]")
            return
        
        for branch in sorted(agent_branches):
            agent_name = branch.replace("agent--", "")
            table.add_row(branch, agent_name)
        
        self.console.print(table)
            
    def stop_agent(self, name: str):
        """Stop and remove an agent (for backward compatibility)."""
        self.console.print(f"[bold yellow]⏹  Stopping agent: {name}[/bold yellow]")
        self._cleanup_and_commit(name)
    
    def cleanup_all(self):
        """Clean up all agents and resources."""
        self.console.print("[bold yellow]🧽 Cleaning up all agents...[/bold yellow]")
        
        # Stop all agent containers
        for container in self.docker.containers.list(all=True):
            if container.attrs["Config"]["Image"] in ["claude-code-agent", "claude-code-proxy"]:
                self.console.print(f"[yellow]🗑  Removing container:[/yellow] {container.name}")
                container.stop()
                container.remove()
        
        # Remove network
        try:
            network = self.docker.networks.get("agent-network")
            network.remove()
            self.console.print("[green]✓ Removed agent network[/green]")
        except docker.errors.NotFound:
            pass
        
        # First, force remove all worktrees
        result = self._run_command(["git", "worktree", "list", "--porcelain"])
        worktree_paths = []
        for line in result.stdout.strip().split("\n"):
            if line.startswith("worktree ") and "/worktrees/" in line:
                path = line.replace("worktree ", "").strip()
                worktree_paths.append(path)
        
        for path in worktree_paths:
            self.console.print(f"[yellow]🗑  Force removing worktree:[/yellow] {path}")
            # Use --force to ensure removal even if there are uncommitted changes
            remove_result = self._run_command(["git", "worktree", "remove", "--force", path])
            if remove_result.returncode != 0:
                self.console.print(f"[red]  ⚠️  Warning: {remove_result.stderr}[/red]")
        
        # Run prune to clean up any stale worktree references
        self.console.print("[cyan]🌳 Pruning stale worktree references...[/cyan]")
        self._run_command(["git", "worktree", "prune"])
        
        # Now delete agent branches
        result = self._run_command(["git", "branch"])
        for line in result.stdout.strip().split("\n"):
            branch = line.strip().lstrip("* ")  # Remove current branch indicator
            if branch.startswith("agent--") or branch.startswith("test-"):
                self.console.print(f"[yellow]🔀 Deleting branch:[/yellow] {branch}")
                delete_result = self._run_command(["git", "branch", "-D", branch])
                if delete_result.returncode != 0:
                    self.console.print(f"[red]  ⚠️  Warning: {delete_result.stderr}[/red]")
        
        self.console.print("\n[bold green]✅ Cleanup completed[/bold green]")
    
    def auth(self):
        """Run Claude Code authentication."""
        self.console.print(Panel(
            "[bold cyan]Starting Claude Code authentication...[/bold cyan]\n\nFollow the prompts to authenticate with your Claude account.",
            title="🔐 Authentication",
            border_style="cyan"
        ))
        
        # Ensure credentials volume exists
        try:
            self.docker.volumes.get("claude-code-credentials")
        except docker.errors.NotFound:
            self.docker.volumes.create("claude-code-credentials")
        
        # Run auth container
        self.docker.containers.run(
            "claude-code-agent",
            command="claude",
            volumes={
                "claude-code-credentials": {"bind": "/home/node/.claude", "mode": "rw"}
            },
            user="node",
            working_dir="/workspace",
            stdin_open=True,
            tty=True,
            auto_remove=True
        )
    


@click.group()
def cli():
    """Agent Sandbox (AGS) - Sandbox for Claude Code AI agents."""
    pass


@cli.command()
@click.argument("name")
@click.argument("goal")
def start(name: str, goal: str):
    """Start a new agent with a specific goal."""
    manager = AgentManager()
    try:
        manager.start_agent(name, goal)
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command()
@click.argument("name")
def stop(name: str):
    """Stop and remove an agent."""
    manager = AgentManager()
    try:
        manager.stop_agent(name)
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command(name="list")
def list_agents():
    """List all active agents."""
    manager = AgentManager()
    manager.list_agents()


@cli.command()
def cleanup():
    """Clean up all agents and resources."""
    manager = AgentManager()
    manager.cleanup_all()


@cli.command()
def auth():
    """Authenticate with Claude Code."""
    manager = AgentManager()
    manager.auth()


if __name__ == "__main__":
    cli()
