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
    
    def __init__(self):
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
        
    def create_workspace_copy(self):
        """Create a temporary copy of the current working directory."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.sandbox_name = f"sandbox-{timestamp}"
        self.network_name = f"agent-network-{self.sandbox_name}"
        self.proxy_container_name = f"proxy-{self.sandbox_name}"
        
        # Create temp directory for workspace
        self.temp_workspace = Path(tempfile.mkdtemp(prefix=f"agent-sandbox-{timestamp}-"))
        
        
        # Copy current directory to temp workspace, excluding .git and other large dirs
        ignore_patterns = shutil.ignore_patterns('.git', 'node_modules', '__pycache__', '*.pyc', '.DS_Store')
        shutil.copytree(self.cwd, self.temp_workspace / "workspace", ignore=ignore_patterns)
        
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
        self.docker_client.images.build(
            path=str(self.project_root),
            dockerfile="Dockerfile.agent",
            tag="claude-code-agent:latest",
            rm=True
        )
        
        # Build proxy image
        self.docker_client.images.build(
            path=str(self.project_root),
            dockerfile="Dockerfile.proxy",
            tag="claude-code-proxy:latest",
            rm=True
        )
    
    def ensure_network(self):
        """Create the Docker network."""
        self.docker_client.networks.create(self.network_name, driver="bridge")
    
    def start_proxy_container(self):
        """Start the proxy container."""
        
        proxy_container = self.docker_client.containers.run(
            "claude-code-proxy:latest",
            name=self.proxy_container_name,
            network=self.network_name,
            detach=True,
            auto_remove=True
        )
        
        return proxy_container
    
    def run_interactive_shell(self, workspace_path):
        """Run an interactive shell in the agent container."""
        # Build command to run interactive shell
        hooks_dir = self.project_root / "hooks"
        docker_cmd = [
            "docker", "run",
            "--rm",
            "--interactive",
            "--tty",
            "--name", f"agent-sandbox-{self.sandbox_name}",
            "--volume", f"{workspace_path}:/workspace",
            "--volume", f"{hooks_dir}:/hooks:ro",
            "--workdir", "/workspace",
            "--user", "node",
            "--network", self.network_name,
            "--env", f"http_proxy=http://{self.proxy_container_name}:3128",
            "--env", f"https_proxy=http://{self.proxy_container_name}:3128",
            "--env", f"HTTP_PROXY=http://{self.proxy_container_name}:3128",
            "--env", f"HTTPS_PROXY=http://{self.proxy_container_name}:3128",
            "--env", "NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt",
            "claude-code-agent:latest",
            "/bin/bash"
        ]
        
        # Run interactive shell
        subprocess.run(docker_cmd)
    
    def generate_diff(self, workspace_path):
        """Generate diff between original and modified workspace."""
        
        # Create diff file
        diff_file = self.cwd / f"sandbox-diff-{self.sandbox_name}.patch"
        
        # Generate diff using git diff
        cmd = [
            "git", "diff", "--no-index", "--no-prefix",
            str(self.cwd), str(workspace_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True)
        
        if result.stdout:
            with open(diff_file, 'wb') as f:
                f.write(result.stdout)
            return diff_file
        else:
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
            startup_task = progress.add_task("Starting agent sandbox...", total=4)
            
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
                
                # Ensure network and start proxy
                progress.update(startup_task, description="Creating network and proxy...", completed=3)
                self.ensure_network()
                self.start_proxy_container()
                
                # Complete startup
                progress.update(startup_task, description="✓ Sandbox ready", completed=4)
                progress.stop()
                
                # Clear and show ready message
                self.console.clear()
                self.console.print("[green]✓ Agent sandbox ready[/green]")
                self.console.print()
                
                # Run interactive shell
                self.run_interactive_shell(workspace_path)
                
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
def sandbox():
    """Launch an interactive agent sandbox environment."""
    sandbox = AgentSandbox()
    sandbox.run()


if __name__ == "__main__":
    sandbox()