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

import click
import docker
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

from logs import AgentLogFormatter
from database import AgentDatabase, DiffStatus


class AgentManager:
    """Manages Claude Code agents with Docker and git worktrees."""
    
    def __init__(self):
        self.console = Console()
        # Create ~/.ags directory if it doesn't exist
        self.ags_dir = Path.home() / ".ags"
        self.ags_dir.mkdir(exist_ok=True)
        # Initialize database in ~/.ags/agents.db
        self.db = AgentDatabase(str(self.ags_dir / "agents.db"))
        self.log_formatter = None  # Will be initialized per agent
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
        # Get current project name (base name of working directory)
        self.project_name = Path.cwd().name
        
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
        
        # Remove existing workspace
        workspace_path = self.worktree_dir / name
        if workspace_path.exists():
            self.console.print(f"[yellow]🗑  Removing existing workspace:[/yellow] {workspace_path}")
            shutil.rmtree(workspace_path)
    
    def start_agent(self, name: str, goal: str):
        """Start a new agent."""
        # Generate unique agent name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        unique_name = f"{name}-{timestamp}"
        
        self.console.print(Panel(
            f"[bold cyan]Agent Name:[/bold cyan] {name}\n[bold cyan]Unique ID:[/bold cyan] {unique_name}\n[bold cyan]Goal:[/bold cyan] {goal}",
            title="🚀 Starting Agent",
            border_style="cyan"
        ))
        
        # Clean up any existing environment for this name
        self._cleanup_existing_agent(unique_name)
        
        # Create database request with unique name
        request_id = self.db.create_request(unique_name, self.project_name, goal)
        
        # Initialize log formatter with database support
        self.log_formatter = AgentLogFormatter(self.console, self.db, request_id)
        
        # Create workspace directory
        workspace_path = self.worktree_dir / unique_name
        
        with self.console.status("[cyan]Creating workspace...[/cyan]", spinner="dots") as status:
            # Clone the current repo to workspace
            result = self._run_command([
                "git", "clone", str(self.git_root), str(workspace_path)
            ])
            if result.returncode != 0:
                raise click.ClickException(f"Failed to clone repo: {result.stderr}")
            status.update("[green]✓ Workspace created[/green]")
        
        # Setup Claude settings
        claude_dir = workspace_path / ".claude"
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
                name=f"proxy-{unique_name}",
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
            temp_log_dir = tempfile.mkdtemp(prefix=f"ags-{unique_name}-logs-")
            log_dir = Path(temp_log_dir)
            log_file = log_dir / "ags.log"
            log_file.touch()
            self.console.print(f"[dim]Log directory: {log_dir}[/dim]")
            


            # Create and start container to properly stream output
            container = self.docker.containers.create(
                "claude-code-agent",
                name=unique_name,
                network="agent-network",
                environment={
                    "CLAUDE_GOAL": goal,
                    "HTTP_PROXY": f"http://proxy-{unique_name}:3128",
                    "HTTPS_PROXY": f"http://proxy-{unique_name}:3128"
                },
                volumes={
                    str(workspace_path): {"bind": "/workspace", "mode": "rw"},
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
                            self.log_formatter.format_log_line(line.rstrip())
                        else:
                            time.sleep(0.1)
            
            # Start tailing in a separate thread
            tail_thread = threading.Thread(target=tail_log_file)
            tail_thread.daemon = True
            tail_thread.start()
            
            # Also stream regular container logs
            for line in container.logs(stream=True, follow=True):
                decoded_line = line.decode('utf-8', errors='ignore').rstrip()
                if decoded_line:
                    self.log_formatter.format_log_line(decoded_line)
            
            # Wait for completion
            result = container.wait()
            exit_code = result['StatusCode']
            
            # Update database status to AGENT_COMPLETE
            self.db.update_request_status(unique_name, DiffStatus.AGENT_COMPLETE, exit_code=exit_code)
            
            if exit_code == 0:
                self.console.print("\n[bold green]✅ Agent completed successfully[/bold green]")
            else:
                self.console.print(f"\n[bold red]❌ Agent failed with exit code: {exit_code}[/bold red]")
                self.db.update_request_status(unique_name, DiffStatus.AGENT_COMPLETE, 
                                            exit_code=exit_code, 
                                            error_message=f"Agent failed with exit code {exit_code}")
            
        except Exception as e:
            self.console.print(f"\n[bold red]❌ Agent failed:[/bold red] {e}")
            # Update database with error
            self.db.update_request_status(unique_name, DiffStatus.AGENT_COMPLETE, 
                                        exit_code=-1, 
                                        error_message=str(e))
        finally:
            # Clean up temporary log directory
            if temp_log_dir and Path(temp_log_dir).exists():
                self.console.print(f"[dim]Cleaning up temporary log directory...[/dim]")
                shutil.rmtree(temp_log_dir)
            
        # Now clean up and commit changes
        self._cleanup_and_commit(unique_name)
        
    def _cleanup_and_commit(self, name: str):
        """Clean up containers and generate diff."""
        self.console.print("\n[bold]🧿 Cleaning up and generating diff...[/bold]")
        
        # Stop containers (they may already be removed due to auto_remove=True)
        for container_name in [name, f"proxy-{name}"]:
            try:
                container = self.docker.containers.get(container_name)
                container.stop()
                self.console.print(f"[green]✓ Stopped {container_name}[/green]")
            except docker.errors.NotFound:
                # Container already removed (auto_remove=True)
                pass
        
        # Generate diff before removing workspace
        workspace_path = self.worktree_dir / name
        if workspace_path.exists():
            self._generate_diff(name, workspace_path)
            
            self.console.print(f"[yellow]🗑  Removing workspace:[/yellow] {workspace_path}")
            shutil.rmtree(workspace_path)
        
        self.console.print(f"\n[bold green]🎉 Agent {name} completed successfully[/bold green]")
    
    def _generate_diff(self, name: str, workspace_path: Path):
        """Generate a diff of agent changes."""
        try:
            result = self._run_command(["git", "-C", str(workspace_path), "diff", "HEAD"])
            
            if result.stdout.strip():
                # Save diff directly to database and update status to DONE
                self.db.save_diff(name, result.stdout)
                self.console.print(f"[green]📄 Diff generated and saved to database[/green]")
            else:
                self.console.print("[dim]No changes detected[/dim]")
                # Even with no changes, update status to DONE
                self.db.save_diff(name, "")
                
        except Exception as e:
            self.console.print(f"[red]⚠️  Failed to generate diff: {e}[/red]")
            # Update database with error but still mark as DONE
            self.db.update_request_status(name, DiffStatus.DONE, 
                                        error_message=f"Failed to generate diff: {e}")
        
    def list_agents(self):
        """List agent workspaces and database records."""
        # Show database records - use same data as diff command
        requests = self.db.list_diffs_by_project(self.project_name, limit=20)
        
        table = Table(title=f"Agent Requests for Project: {self.project_name}", show_header=True, header_style="bold cyan")
        table.add_column("Name", style="yellow")
        table.add_column("Goal", style="white", max_width=40)
        table.add_column("Status", style="magenta")
        table.add_column("Project", style="cyan")
        table.add_column("Timestamp", style="green")
        
        if not requests:
            self.console.print(table)
            return
        
        for req in requests:
            # Get most recent timestamp between completed and started
            completed = req['completed_at'] if req['completed_at'] else None
            started = req['started_at'] if req['started_at'] else None
            most_recent = completed if completed else started if started else '-'
            
            # Truncate goal if too long
            goal = req['goal']
            if len(goal) > 40:
                goal = goal[:37] + "..."
            
            table.add_row(
                req['agent_name'],
                goal,
                req['diff_status'],
                req['project'],
                most_recent
            )
        
        self.console.print(table)
        
        # Show apply instruction if there are diffs available
        if requests:
            self.console.print(f"\n[dim]Use 'ags apply <agent-name>' to apply a specific diff[/dim]")
        
        # Also check for active containers
        active_containers = []
        for container in self.docker.containers.list(all=True):
            if container.attrs["Config"]["Image"] == "claude-code-agent":
                active_containers.append(container.name)
        
        if active_containers:
            self.console.print(f"\n[cyan]Active containers:[/cyan] {', '.join(active_containers)}")
            
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
        
        # Remove all workspace directories
        if self.worktree_dir.exists():
            self.console.print(f"[yellow]🗑  Removing all workspaces:[/yellow] {self.worktree_dir}")
            shutil.rmtree(self.worktree_dir)
            self.worktree_dir.mkdir(exist_ok=True)
        
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


@cli.command()
@click.argument("name")
def logs(name: str):
    """View logs for a specific agent from the database."""
    manager = AgentManager()
    
    # Initialize log formatter for display purposes
    manager.log_formatter = AgentLogFormatter(manager.console)
    
    # Get agent status
    status = manager.db.get_agent_status(name)
    if not status:
        raise click.ClickException(f"Agent '{name}' not found in database")
    
    # Display agent info
    manager.console.print(Panel(
        f"[bold cyan]Agent:[/bold cyan] {name}\n"
        f"[bold cyan]Goal:[/bold cyan] {status['goal']}\n"
        f"[bold cyan]Status:[/bold cyan] {status['diff_status']}\n"
        f"[bold cyan]Started:[/bold cyan] {status['started_at'] or '-'}\n"
        f"[bold cyan]Completed:[/bold cyan] {status['completed_at'] or '-'}",
        title="📋 Agent Information",
        border_style="cyan"
    ))
    
    # Get and display logs
    logs = manager.db.get_agent_logs(name)
    if not logs:
        manager.console.print("[dim]No logs found[/dim]")
        return
    
    manager.console.print(f"\n[bold]Agent Logs ({len(logs)} entries):[/bold]\n")
    
    for log in logs:
        timestamp = log['timestamp']
        if log['tool_name']:
            # Tool event
            tool_input = json.loads(log['tool_input']) if log['tool_input'] else {}
            details = manager.log_formatter._format_tool_details(log['tool_name'], tool_input)
            manager.console.print(
                f"[dim]{timestamp}[/dim] [{log['hook_event']}] "
                f"[bold blue]{log['tool_name']}[/bold blue]: {details}"
            )
        else:
            # Regular message
            manager.console.print(f"[dim]{timestamp}[/dim] {log['message']}")



@cli.command()
@click.argument("agent_name")
def apply(agent_name: str):
    """Apply a specific diff by agent name."""
    manager = AgentManager()
    
    # Get diff by agent name
    diff_record = manager.db.get_diff_by_agent_name(agent_name)
    if not diff_record:
        raise click.ClickException(f"No diff found for agent '{agent_name}'")
    
    if not diff_record['diff_content']:
        raise click.ClickException(f"No diff content available for agent '{agent_name}'")
    
    # Show diff info
    manager.console.print(Panel(
        f"[bold cyan]Agent:[/bold cyan] {diff_record['agent_name']}\n"
        f"[bold cyan]Project:[/bold cyan] {diff_record['project']}\n"
        f"[bold cyan]Goal:[/bold cyan] {diff_record['goal']}\n"
        f"[bold cyan]Completed:[/bold cyan] {diff_record['completed_at'] or '-'}",
        title="📄 Diff Information",
        border_style="cyan"
    ))
    
    # Apply the diff
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.diff', delete=False) as temp_file:
            temp_file.write(diff_record['diff_content'])
            temp_file_path = temp_file.name
        
        try:
            # Apply diff using git apply
            result = manager._run_command(["git", "apply", temp_file_path])
            
            if result.returncode == 0:
                manager.console.print(f"[green]✅ Successfully applied diff for agent '{agent_name}'[/green]")
            else:
                manager.console.print(f"[red]❌ Failed to apply diff: {result.stderr}[/red]")
                raise click.ClickException(f"Git apply failed: {result.stderr}")
        finally:
            # Clean up temporary file
            Path(temp_file_path).unlink(missing_ok=True)
            
    except Exception as e:
        raise click.ClickException(f"Failed to apply diff: {e}")


if __name__ == "__main__":
    cli()
