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
        
    def create_workspace_copy(self):
        """Create a temporary copy of the current working directory."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.sandbox_name = f"sandbox-{timestamp}"
        self.network_name = f"agent-network-{self.sandbox_name}"
        self.proxy_container_name = f"proxy-{self.sandbox_name}"
        
        # Create temp directory for workspace
        self.temp_workspace = Path(tempfile.mkdtemp(prefix=f"agent-sandbox-{timestamp}-"))
        
        self.console.print(f"→ Creating workspace copy at {self.temp_workspace}")
        
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
        
        self.console.print("→ Created Claude settings with hooks")
    
    def build_images(self):
        """Build required Docker images."""
        self.console.print("→ Building Docker images...")
        
        # Build agent image
        self.docker_client.images.build(
            path=str(self.project_root),
            dockerfile="Dockerfile.agent",
            tag="claude-code-agent:latest",
            rm=True
        )
        self.console.print("  ✓ Agent image built")
        
        # Build proxy image
        self.docker_client.images.build(
            path=str(self.project_root),
            dockerfile="Dockerfile.proxy",
            tag="claude-code-proxy:latest",
            rm=True
        )
        self.console.print("  ✓ Proxy image built")
    
    def ensure_network(self):
        """Create the Docker network."""
        self.console.print(f"→ Creating Docker network: {self.network_name}")
        self.docker_client.networks.create(self.network_name, driver="bridge")
    
    def start_proxy_container(self):
        """Start the proxy container."""
        self.console.print(f"→ Starting proxy container: {self.proxy_container_name}")
        
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
        self.console.print("→ Starting interactive shell...")
        
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
        self.console.print("→ Generating diff...")
        
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
            self.console.print(f"  ✓ Diff saved to: [green]{diff_file}[/green]")
        else:
            self.console.print("  ✓ No changes detected")
    
    def cleanup(self):
        """Clean up temporary workspace and containers."""
        self.console.print("\n→ Starting cleanup...")
        
        # Stop proxy container (auto_remove should handle removal)
        self.console.print(f"→ Stopping proxy container: {self.proxy_container_name}")
        try:
            proxy = self.docker_client.containers.get(self.proxy_container_name)
            proxy.stop()
            self.console.print(f"  ✓ Proxy container stopped")
        except:
            self.console.print(f"  ✓ Proxy container already stopped")
        
        # Remove network
        self.console.print(f"→ Removing network: {self.network_name}")
        try:
            network = self.docker_client.networks.get(self.network_name)
            network.remove()
            self.console.print(f"  ✓ Network removed")
        except:
            self.console.print(f"  ✓ Network already removed")
        
        # Remove temporary workspace
        self.console.print(f"→ Removing temporary workspace: {self.temp_workspace}")
        shutil.rmtree(self.temp_workspace)
        self.console.print(f"  ✓ Temporary workspace removed")
        
        self.console.print("\n✓ Cleanup completed")
    
    def run(self):
        """Main execution flow."""
        try:
            # Build images if needed
            self.build_images()
            
            # Create workspace copy
            workspace_path = self.create_workspace_copy()
            
            # Setup Claude settings if hooks exist
            self.setup_claude_settings(workspace_path)
            
            # Ensure network and start proxy
            self.ensure_network()
            self.start_proxy_container()
            
            # Run interactive shell
            self.run_interactive_shell(workspace_path)
            
            # Generate diff after shell exits
            self.generate_diff(workspace_path)
            
        finally:
            # Always cleanup
            self.cleanup()


@click.command()
def sandbox():
    """Launch an interactive agent sandbox environment."""
    sandbox = AgentSandbox()
    sandbox.run()


if __name__ == "__main__":
    sandbox()