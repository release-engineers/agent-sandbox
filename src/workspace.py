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

import docker


class WorkspaceManager:
    """Manages git worktrees and Docker containers for agent execution."""
    
    def __init__(self, project_path: Optional[Path] = None, log_manager=None):
        self.console = Console()
        self.log_manager = log_manager
        try:
            self.docker = docker.from_env()
        except Exception as e:
            self.console.print(f"[bold red]Error connecting to Docker:[/bold red] {e}")
            sys.exit(1)
        
        self.project_path = project_path or Path.cwd()
        self.git_root = self._get_git_root()
        self.worktree_dir = Path.home() / ".ags" / "worktrees"
        self.worktree_dir.mkdir(parents=True, exist_ok=True)
    
    def _log_message(self, agent_name: str, message: str):
        """Log a message for the agent."""
        if self.log_manager:
            self.log_manager.log_message(agent_name, "INFO", message, tool_name="WORKSPACE", tool_type="AGS")
    
    def _get_git_root(self) -> Path:
        """Get git repository root."""
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
            cwd=str(self.project_path)
        )
        return Path(result.stdout.strip())
    
    def _run_command(self, cmd: list[str], cwd: Optional[str] = None) -> subprocess.CompletedProcess:
        """Run a command and return result."""
        return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or str(self.project_path))
    
    def cleanup_existing_agent(self, agent_id: str):
        """Clean up any existing agent environment."""
        for container_name in [agent_id, f"proxy-{agent_id}"]:
            try:
                container = self.docker.containers.get(container_name)
                container.stop()
                container.remove()
            except docker.errors.NotFound:
                pass
        
        workspace_path = self.worktree_dir / agent_id
        if workspace_path.exists():
            shutil.rmtree(workspace_path)
    
    def create_workspace(self, agent_id: str) -> Path:
        """Create workspace directory and clone repo."""
        workspace_path = self.worktree_dir / agent_id
        
        result = self._run_command([
            "git", "clone", str(self.git_root), str(workspace_path)
        ])
        if result.returncode != 0:
            raise Exception(f"Failed to clone repo: {result.stderr}")
        
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
        
        self.docker.images.build(
            path=str(agent_process_dir),
            dockerfile="Dockerfile.agent",
            tag="claude-code-agent"
        )
        
        self.docker.images.build(
            path=str(agent_process_dir),
            dockerfile="Dockerfile.proxy",
            tag="claude-code-proxy"
        )
    
    def ensure_network(self):
        """Create agent network if it doesn't exist."""
        try:
            self.docker.networks.get("agent-network")
        except docker.errors.NotFound:
            self.docker.networks.create("agent-network")
    
    def start_proxy_container(self, agent_id: str):
        """Start proxy container."""
        self.docker.containers.run(
            "claude-code-proxy",
            name=f"proxy-{agent_id}",
            network="agent-network",
            detach=True,
            auto_remove=True
        )
        self._log_message(agent_id, "Proxy container started")
    
    def run_agent_container(self, agent_id: str, goal: str, workspace_path: Path) -> int:
        """Run agent container and return exit code."""
        self._log_message(agent_id, "Starting agent container...")
        
        temp_log_dir = None
        try:
            temp_log_dir = tempfile.mkdtemp(prefix=f"ags-{agent_id}-logs-")
            log_dir = Path(temp_log_dir)
            log_file = log_dir / "ags.log"
            log_file.touch()
            self._log_message(agent_id, f"Log directory: {log_dir}")
            
            container = self.docker.containers.create(
                "claude-code-agent",
                name=agent_id,
                network="agent-network",
                environment={
                    "CLAUDE_GOAL": goal,
                    "HTTP_PROXY": f"http://proxy-{agent_id}:3128",
                    "HTTPS_PROXY": f"http://proxy-{agent_id}:3128"
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
                """Tail the log file and store new lines."""
                with open(log_file, 'r') as f:
                    f.seek(0, 2)
                    while container.status in ['running', 'created']:
                        line = f.readline()
                        if line:
                            self._log_message(agent_id, line.rstrip())
                        else:
                            time.sleep(0.1)
            
            tail_thread = threading.Thread(target=tail_log_file)
            tail_thread.daemon = True
            tail_thread.start()
            
            for line in container.logs(stream=True, follow=True):
                decoded_line = line.decode('utf-8', errors='ignore').rstrip()
                if decoded_line:
                    self._log_message(agent_id, decoded_line)
            
            result = container.wait()
            return result['StatusCode']
            
        finally:
            if temp_log_dir and Path(temp_log_dir).exists():
                self._log_message(agent_id, "Cleaning up temporary log directory...")
                shutil.rmtree(temp_log_dir)
    
    def stop_containers(self, agent_id: str):
        """Stop and remove containers."""
        for container_name in [agent_id, f"proxy-{agent_id}"]:
            try:
                container = self.docker.containers.get(container_name)
                container.stop()
            except docker.errors.NotFound:
                pass
    
    def remove_workspace(self, agent_id: str):
        """Remove workspace directory."""
        workspace_path = self.worktree_dir / agent_id
        if workspace_path.exists():
            shutil.rmtree(workspace_path)
    
    def cleanup_all(self):
        """Clean up all agents and resources."""
        for container in self.docker.containers.list(all=True):
            if container.attrs["Config"]["Image"] in ["claude-code-agent", "claude-code-proxy"]:
                container.stop()
                container.remove()
        
        try:
            network = self.docker.networks.get("agent-network")
            network.remove()
        except docker.errors.NotFound:
            pass
        
        if self.worktree_dir.exists():
            shutil.rmtree(self.worktree_dir)
            self.worktree_dir.mkdir(exist_ok=True)
    
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