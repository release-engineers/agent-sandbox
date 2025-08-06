#!/usr/bin/env python3
"""Agent Sandbox - Interactive container environment with diff generation."""

import json
import shutil
import tempfile
import subprocess
from datetime import datetime
from pathlib import Path
import docker
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
import click

class AgentSandbox:
    """Manages interactive sandbox environments with copy-on-write workspaces."""
    
    def __init__(self, command=None, interactive=True):
        self.console = Console()
        self.docker_client = docker.from_env()
        self.cwd = Path.cwd()
        self.temp_workspace = None
        self.sandbox_name = None
        self.network_name = None
        self.proxy_container_name = None
        # Get the agent-sandbox project root (where this script is)
        self.project_root = Path(__file__).parent.parent
        self.live = None
        self.command = command
        self.interactive = interactive
        
    def create_workspace_copy(self):
        """Create a temporary copy of the current working directory."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.sandbox_name = f"sandbox-{timestamp}"
        self.network_name = f"agent-network-{self.sandbox_name}"
        self.proxy_container_name = f"proxy-{self.sandbox_name}"
        
        # Create temp directory for workspace
        self.temp_workspace = Path(tempfile.mkdtemp(prefix=f"agent-sandbox-{timestamp}-"))
        
        
        # Copy current directory to temp workspace
        shutil.copytree(self.cwd, self.temp_workspace / "workspace")
        
        return self.temp_workspace / "workspace"
    
    def setup_claude_settings(self, workspace_path):
        """Create Claude settings.json with hooks configuration."""
            
        settings_dir = workspace_path / ".claude"
        settings_dir.mkdir(exist_ok=True)
        
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
                    {"matcher": ".*", "hooks": [{"type": "command", "command": "/hooks/post-stop"}]}
                ]
            },
            "tools": {"computer_use": {"enabled": False}}
        }
        
        settings_file = settings_dir / "settings.json"
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=2)
        
    
    def build_images(self):
        """Build required Docker images."""
        
        # Build agent image
        subprocess.run([
            "docker", "build",
            "-f", str(self.project_root / "Dockerfile.agent"),
            "-t", "sandbox-agent:latest",
            str(self.project_root)
        ], check=True)
        
        # Build proxy image
        subprocess.run([
            "docker", "build",
            "-f", str(self.project_root / "Dockerfile.proxy"),
            "-t", "sandbox-proxy:latest",
            str(self.project_root)
        ], check=True)
    
    def ensure_network(self):
        """Create the Docker network."""
        self.docker_client.networks.create(self.network_name, driver="bridge")
    
    def start_proxy_container(self):
        """Start the proxy container."""
        
        proxy_container = self.docker_client.containers.run(
            "sandbox-proxy:latest",
            name=self.proxy_container_name,
            network=self.network_name,
            detach=True,
            auto_remove=True
        )
        
        return proxy_container
    
    def run_container(self, workspace_path, command=None, interactive=True):
        """Run a container with optional command and interactive mode."""
        # Build command to run container
        hooks_dir = self.project_root / "hooks"
        docker_cmd = [
            "docker", "run",
            "--rm",
            "--name", f"agent-sandbox-{self.sandbox_name}",
            "--volume", f"{workspace_path}:/workspace",
            "--volume", f"{hooks_dir}:/hooks:ro",
            "--volume", "claude-code-credentials:/root/.claude",
            "--workdir", "/workspace",
            "--network", self.network_name,
            "--env", f"http_proxy=http://{self.proxy_container_name}:3128",
            "--env", f"https_proxy=http://{self.proxy_container_name}:3128",
            "--env", f"HTTP_PROXY=http://{self.proxy_container_name}:3128",
            "--env", f"HTTPS_PROXY=http://{self.proxy_container_name}:3128",
            "--env", "NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt",
        ]
        
        # Mount host's .claude.json (required)
        host_claude_json = Path.home() / ".claude.json"
        if not host_claude_json.exists():
            raise FileNotFoundError(f"Claude configuration not found at {host_claude_json}. Please run 'claude' first.")
        docker_cmd.extend(["--volume", f"{host_claude_json}:/root/.claude.json"])
        
        # Add interactive and tty flags if needed
        if interactive:
            docker_cmd.extend(["--interactive", "--tty"])
        
        # Add the image
        docker_cmd.append("sandbox-agent:latest")
        
        # Add command to run
        if command:
            # Command is always a list now
            docker_cmd.extend(command)
        else:
            # Default to interactive bash shell
            docker_cmd.append("/bin/bash")
        
        # Run container
        subprocess.run(docker_cmd, check=True)
    
    def generate_diff(self, workspace_path):
        """Generate diff between original and modified workspace."""
        
        # Create diff file
        diff_file = self.cwd / f"sandbox-diff-{self.sandbox_name}.patch"
        
        # Add all changes to the index (respecting .gitignore)
        subprocess.run(["git", "add", "-A"], cwd=str(workspace_path), capture_output=True)
        
        # Generate diff and write directly to file
        with open(diff_file, 'w') as f:
            result = subprocess.run(["git", "diff", "--cached"], 
                                  cwd=str(workspace_path), 
                                  stdout=f)
        
        # Check if diff file has content
        if diff_file.stat().st_size > 0:
            return diff_file
        else:
            diff_file.unlink()  # Remove empty file
            return None
    
    def cleanup_containers(self):
        """Stop proxy container."""
        try:
            proxy = self.docker_client.containers.get(self.proxy_container_name)
            proxy.stop()
        except:
            pass
    
    def cleanup_network(self):
        """Remove Docker network."""
        try:
            network = self.docker_client.networks.get(self.network_name)
            network.remove()
        except:
            pass
    
    def cleanup_workspace(self):
        """Remove temporary workspace."""
        if self.temp_workspace and self.temp_workspace.exists():
            shutil.rmtree(self.temp_workspace)
    
    def cleanup(self):
        """Clean up all resources."""
        self.cleanup_containers()
        self.cleanup_network() 
        self.cleanup_workspace()
    
    def run(self):
        """Main execution flow."""
        # Setup progress display
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(complete_style="green", finished_style="green"),
            TaskProgressColumn(),
            console=self.console
        )
        
        with progress:
            # Startup progress
            startup_task = progress.add_task("Starting agent sandbox...", total=5)
            
            try:
                # Build images if needed
                progress.update(startup_task, description="Building Docker images...", completed=0)
                self.build_images()
                
                # Create workspace copy
                progress.update(startup_task, description="Creating workspace copy...", completed=1)
                workspace_path = self.create_workspace_copy()
                
                # Setup Claude settings
                progress.update(startup_task, description="Setting up Claude configuration...", completed=2)
                self.setup_claude_settings(workspace_path)
                
                # Create persistent volume for Claude Code credentials
                progress.update(startup_task, description="Creating credentials volume...", completed=3)
                subprocess.run(["docker", "volume", "create", "claude-code-credentials"], check=True)
                
                # Ensure network and start proxy
                progress.update(startup_task, description="Creating network and proxy...", completed=4)
                self.ensure_network()
                self.start_proxy_container()
                
                # Complete startup
                progress.update(startup_task, description="✓ Sandbox ready", completed=5)
                progress.stop()
                
                # Clear and show ready message
                self.console.clear()
                self.console.print("[green]✓ Agent sandbox ready[/green]")
                self.console.print()
                
                # Run container with command or interactive shell
                self.run_container(workspace_path, self.command, self.interactive)
                
                # After shell exits, start cleanup
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(complete_style="blue", finished_style="blue"),
                    TaskProgressColumn(),
                    console=self.console
                ) as cleanup_progress:
                    cleanup_task = cleanup_progress.add_task("Cleaning up sandbox...", total=4)
                    
                    cleanup_progress.update(cleanup_task, description="Generating diff...", completed=0)
                    diff_file = self.generate_diff(workspace_path)
                    
                    cleanup_progress.update(cleanup_task, description="Stopping containers...", completed=1)
                    self.cleanup_containers()
                    
                    cleanup_progress.update(cleanup_task, description="Removing network...", completed=2)
                    self.cleanup_network()
                    
                    cleanup_progress.update(cleanup_task, description="Removing workspace...", completed=3)
                    self.cleanup_workspace()
                    
                    cleanup_progress.update(cleanup_task, description="✓ Cleanup complete", completed=4)
                
                # Show diff result after cleanup
                self.console.print()
                if diff_file:
                    self.console.print(f"[blue]→[/blue] Diff saved to: [green]{diff_file.name}[/green]")
                else:
                    self.console.print("[blue]→[/blue] No changes detected")
                
            except Exception as e:
                progress.stop()
                self.console.print(f"[red]Error: {e}[/red]")
                self.cleanup()
                raise

@click.command()
@click.argument('command', nargs=-1)
@click.option('--noninteractive', is_flag=True, help='Run without interactive TTY')
def sandbox(command, noninteractive):
    """Launch an agent sandbox environment.
    
    COMMAND: Optional command to run in the sandbox. If not provided, launches an interactive shell.
    """
    # Pass command as list to preserve arguments
    command_list = list(command) if command else None
    # Interactive is True by default, unless --noninteractive is set
    interactive = not noninteractive
    
    sandbox = AgentSandbox(command=command_list, interactive=interactive)
    sandbox.run()


if __name__ == "__main__":
    sandbox(prog_name='agent-sandbox')
