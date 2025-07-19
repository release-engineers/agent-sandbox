#!/usr/bin/env python3
"""Git worktree and container related operations."""

import sys
import json
import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

import docker


class WorkspaceManager:
    """Manages git worktrees and Docker containers for agent execution."""
    
    def __init__(self):
        self.console = Console()
        try:
            self.docker = docker.from_env()
        except Exception as e:
            self.console.print(f"[bold red]Error connecting to Docker:[/bold red] {e}")
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
    
    def cleanup_existing_agent(self, name: str):
        """Clean up any existing agent environment."""
        for container_name in [name, f"proxy-{name}"]:
            try:
                container = self.docker.containers.get(container_name)
                self.console.print(f"[yellow]⏹  Stopping existing container:[/yellow] {container_name}")
                container.stop()
                container.remove()
            except docker.errors.NotFound:
                pass
        
        workspace_path = self.worktree_dir / name
        if workspace_path.exists():
            self.console.print(f"[yellow]🗑  Removing existing workspace:[/yellow] {workspace_path}")
            shutil.rmtree(workspace_path)
    
    def create_workspace(self, name: str) -> Path:
        """Create workspace directory and clone repo."""
        workspace_path = self.worktree_dir / name
        
        with self.console.status("[cyan]Creating workspace...[/cyan]", spinner="dots") as status:
            result = self._run_command([
                "git", "clone", str(self.git_root), str(workspace_path)
            ])
            if result.returncode != 0:
                raise Exception(f"Failed to clone repo: {result.stderr}")
            status.update("[green]✓ Workspace created[/green]")
        
        return workspace_path
    
    def setup_claude_settings(self, workspace_path: Path):
        """Setup Claude settings in workspace."""
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
    
    def build_images(self):
        """Build Docker images with progress display."""
        agent_process_dir = Path(__file__).parent.parent
        
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
    
    def ensure_network(self):
        """Create agent network if it doesn't exist."""
        try:
            self.docker.networks.get("agent-network")
        except docker.errors.NotFound:
            self.docker.networks.create("agent-network")
    
    def start_proxy_container(self, name: str):
        """Start proxy container."""
        with self.console.status("[cyan]Starting proxy container...[/cyan]", spinner="dots"):
            self.docker.containers.run(
                "claude-code-proxy",
                name=f"proxy-{name}",
                network="agent-network",
                detach=True,
                auto_remove=True
            )
            self.console.print("[green]✓ Proxy container started[/green]")
    
    def run_agent_container(self, name: str, goal: str, workspace_path: Path, log_formatter) -> int:
        """Run agent container and return exit code."""
        self.console.print("\n[bold cyan]🤖 Starting agent container...[/bold cyan]")
        
        temp_log_dir = None
        try:
            temp_log_dir = tempfile.mkdtemp(prefix=f"ags-{name}-logs-")
            log_dir = Path(temp_log_dir)
            log_file = log_dir / "ags.log"
            log_file.touch()
            self.console.print(f"[dim]Log directory: {log_dir}[/dim]")
            
            container = self.docker.containers.create(
                "claude-code-agent",
                name=name,
                network="agent-network",
                environment={
                    "CLAUDE_GOAL": goal,
                    "HTTP_PROXY": f"http://proxy-{name}:3128",
                    "HTTPS_PROXY": f"http://proxy-{name}:3128"
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
            
            container.start()
            
            import threading
            import time
            
            def tail_log_file():
                """Tail the log file and print new lines."""
                with open(log_file, 'r') as f:
                    f.seek(0, 2)
                    while container.status in ['running', 'created']:
                        line = f.readline()
                        if line:
                            log_formatter.format_log_line(line.rstrip())
                        else:
                            time.sleep(0.1)
            
            tail_thread = threading.Thread(target=tail_log_file)
            tail_thread.daemon = True
            tail_thread.start()
            
            for line in container.logs(stream=True, follow=True):
                decoded_line = line.decode('utf-8', errors='ignore').rstrip()
                if decoded_line:
                    log_formatter.format_log_line(decoded_line)
            
            result = container.wait()
            return result['StatusCode']
            
        finally:
            if temp_log_dir and Path(temp_log_dir).exists():
                self.console.print(f"[dim]Cleaning up temporary log directory...[/dim]")
                shutil.rmtree(temp_log_dir)
    
    def stop_containers(self, name: str):
        """Stop and remove containers."""
        for container_name in [name, f"proxy-{name}"]:
            try:
                container = self.docker.containers.get(container_name)
                container.stop()
                self.console.print(f"[green]✓ Stopped {container_name}[/green]")
            except docker.errors.NotFound:
                pass
    
    def remove_workspace(self, name: str):
        """Remove workspace directory."""
        workspace_path = self.worktree_dir / name
        if workspace_path.exists():
            self.console.print(f"[yellow]🗑  Removing workspace:[/yellow] {workspace_path}")
            shutil.rmtree(workspace_path)
    
    def cleanup_all(self):
        """Clean up all agents and resources."""
        self.console.print("[bold yellow]🧽 Cleaning up all agents...[/bold yellow]")
        
        for container in self.docker.containers.list(all=True):
            if container.attrs["Config"]["Image"] in ["claude-code-agent", "claude-code-proxy"]:
                self.console.print(f"[yellow]🗑  Removing container:[/yellow] {container.name}")
                container.stop()
                container.remove()
        
        try:
            network = self.docker.networks.get("agent-network")
            network.remove()
            self.console.print("[green]✓ Removed agent network[/green]")
        except docker.errors.NotFound:
            pass
        
        if self.worktree_dir.exists():
            self.console.print(f"[yellow]🗑  Removing all workspaces:[/yellow] {self.worktree_dir}")
            shutil.rmtree(self.worktree_dir)
            self.worktree_dir.mkdir(exist_ok=True)
        
        self.console.print("\n[bold green]✅ Cleanup completed[/bold green]")
    
    def run_auth_container(self):
        """Run Claude Code authentication."""
        try:
            self.docker.volumes.get("claude-code-credentials")
        except docker.errors.NotFound:
            self.docker.volumes.create("claude-code-credentials")
        
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
    
    def list_active_containers(self) -> list[str]:
        """List active agent containers."""
        active_containers = []
        for container in self.docker.containers.list(all=True):
            if container.attrs["Config"]["Image"] == "claude-code-agent":
                active_containers.append(container.name)
        return active_containers