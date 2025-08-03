#!/usr/bin/env python3
"""Simple agent process manager for Claude Code."""

import sys
import json
import subprocess
import threading
import time
from pathlib import Path

import click
import docker


class AgentManager:
    """Manages Claude Code agents with Docker and git worktrees."""
    
    def __init__(self):
        try:
            self.docker = docker.from_env()
        except Exception as e:
            print(f"Error connecting to Docker: {e}")
            print("Please ensure Docker is running and try again.")
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
    
    def _cleanup_existing_agent(self, name: str):
        """Clean up any existing agent environment."""
        # Stop and remove containers
        for container_name in [name, f"proxy-{name}"]:
            try:
                container = self.docker.containers.get(container_name)
                print(f"Stopping existing container: {container_name}")
                container.stop()
                container.remove()
            except docker.errors.NotFound:
                pass
        
        # Remove existing worktree
        worktree_path = self.worktree_dir / name
        if worktree_path.exists():
            print(f"Removing existing worktree: {worktree_path}")
            # Force remove the worktree
            self._run_command(["git", "worktree", "remove", "--force", str(worktree_path)])
        
        # Check if branch exists and delete it
        branch_name = f"agent--{name}"
        result = self._run_command(["git", "branch", "--list", branch_name])
        if result.stdout.strip():
            print(f"Deleting existing branch: {branch_name}")
            self._run_command(["git", "branch", "-D", branch_name])
    
    def start_agent(self, name: str, goal: str):
        """Start a new agent."""
        print(f"Starting agent: {name}")
        print(f"Goal: {goal}")
        
        # Clean up any existing environment for this name
        self._cleanup_existing_agent(name)
        
        # Create worktree
        worktree_path = self.worktree_dir / name
        
        print("Creating worktree...")
        result = self._run_command([
            "git", "worktree", "add", str(worktree_path), "-b", f"agent--{name}"
        ])
        if result.returncode != 0:
            raise click.ClickException(f"Failed to create worktree: {result.stderr}")
        
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
        
        print("Building agent image...")
        self.docker.images.build(
            path=str(agent_process_dir),
            dockerfile="Dockerfile.agent",
            tag="claude-code-agent"
        )
        
        print("Building proxy image...")
        self.docker.images.build(
            path=str(agent_process_dir),
            dockerfile="Dockerfile.proxy",
            tag="claude-code-proxy"
        )
        
        # Create network if needed
        try:
            self.docker.networks.get("agent-network")
        except docker.errors.NotFound:
            self.docker.networks.create("agent-network")
        
        # Start proxy container
        print("Starting proxy container...")
        self.docker.containers.run(
            "claude-code-proxy",
            name=f"proxy-{name}",
            network="agent-network",
            detach=True,
            auto_remove=True
        )
        
        # Start agent container
        print("Starting agent container...")
        
        try:
            # Create log file in worktree
            log_dir = worktree_path / "var" / "log"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "ags.log"
            log_file.touch()
            
            # Create and start container to properly stream output
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
                            print(f"[LOG] {line.rstrip()}")
                        else:
                            time.sleep(0.1)
            
            # Start tailing in a separate thread
            tail_thread = threading.Thread(target=tail_log_file)
            tail_thread.daemon = True
            tail_thread.start()
            
            # Also stream regular container logs
            for line in container.logs(stream=True, follow=True):
                print(line.decode('utf-8', errors='ignore').rstrip())
            
            # Wait for completion
            result = container.wait()
            if result['StatusCode'] == 0:
                print("Agent completed successfully")
            else:
                print(f"Agent failed with exit code: {result['StatusCode']}")
            
        except Exception as e:
            print(f"Agent failed: {e}")
            
        # Now clean up and commit changes
        self._cleanup_and_commit(name)
        
    def _cleanup_and_commit(self, name: str):
        """Clean up containers and commit changes."""
        print("Cleaning up and committing changes...")
        
        # Stop containers (they may already be removed due to auto_remove=True)
        for container_name in [name, f"proxy-{name}"]:
            try:
                container = self.docker.containers.get(container_name)
                container.stop()
                print(f"Stopped {container_name}")
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
                print(commit_result.stdout)
            if commit_result.stderr:
                print(commit_result.stderr)
            
            # Remove worktree
            self._run_command(["git", "worktree", "remove", str(worktree_path)])
            print(f"Removed worktree")
        
        print(f"Agent {name} completed successfully")
        
    def list_agents(self):
        """List agent branches."""
        print("Agent branches:")
        print("-" * 50)
        
        # Get agent branches
        result = self._run_command(["git", "branch"])
        agent_branches = []
        for line in result.stdout.strip().split("\n"):
            branch = line.strip().lstrip("* ")
            if branch.startswith("agent--"):
                agent_branches.append(branch)
        
        if not agent_branches:
            print("No agent branches found")
            return
        
        for branch in sorted(agent_branches):
            print(f"  {branch}")
            
    def stop_agent(self, name: str):
        """Stop and remove an agent (for backward compatibility)."""
        print(f"Stopping agent: {name}")
        self._cleanup_and_commit(name)
    
    def cleanup_all(self):
        """Clean up all agents and resources."""
        print("Cleaning up all agents...")
        
        # Stop all agent containers
        for container in self.docker.containers.list(all=True):
            if container.attrs["Config"]["Image"] in ["claude-code-agent", "claude-code-proxy"]:
                print(f"Removing container: {container.name}")
                container.stop()
                container.remove()
        
        # Remove network
        try:
            network = self.docker.networks.get("agent-network")
            network.remove()
            print("Removed agent network")
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
            print(f"Force removing worktree: {path}")
            # Use --force to ensure removal even if there are uncommitted changes
            remove_result = self._run_command(["git", "worktree", "remove", "--force", path])
            if remove_result.returncode != 0:
                print(f"  Warning: {remove_result.stderr}")
        
        # Run prune to clean up any stale worktree references
        print("Pruning stale worktree references...")
        self._run_command(["git", "worktree", "prune"])
        
        # Now delete agent branches
        result = self._run_command(["git", "branch"])
        for line in result.stdout.strip().split("\n"):
            branch = line.strip().lstrip("* ")  # Remove current branch indicator
            if branch.startswith("agent--") or branch.startswith("test-"):
                print(f"Deleting branch: {branch}")
                delete_result = self._run_command(["git", "branch", "-D", branch])
                if delete_result.returncode != 0:
                    print(f"  Warning: {delete_result.stderr}")
        
        print("Cleanup completed")
    
    def auth(self):
        """Run Claude Code authentication."""
        print("Starting Claude Code authentication...")
        print("Follow the prompts to authenticate with your Claude account.\n")
        
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
