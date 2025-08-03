#!/usr/bin/env python3
"""Simple agent process manager for Claude Code."""

import sys
import json
import subprocess
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
    
    def start_agent(self, name: str, goal: str):
        """Start a new agent."""
        print(f"Starting agent: {name}")
        print(f"Goal: {goal}")
        
        # Create worktree
        worktree_path = self.worktree_dir / name
        if worktree_path.exists():
            raise click.ClickException(f"Agent {name} already exists")
        
        print("Creating worktree...")
        self._run_command([
            "git", "worktree", "add", str(worktree_path), "-b", f"agent--{name}"
        ])
        
        # Setup Claude settings
        claude_dir = worktree_path / ".claude"
        claude_dir.mkdir(exist_ok=True)
        
        settings = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": "/hooks/pre-bash"}]},
                    {"matcher": "Write|Edit|MultiEdit", "hooks": [{"type": "command", "command": "/hooks/pre-writes"}]}
                ],
                "PostToolUse": [
                    {"matcher": "Write|Edit|MultiEdit", "hooks": [{"type": "command", "command": "/hooks/post-writes"}]}
                ],
                "Stop": [
                    {"matcher": ".*", "hooks": [{"type": "command", "command": "/hooks/stop"}]}
                ]
            },
            "tools": {"computer_use": {"enabled": False}}
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
        print("-" * 50)
        
        try:
            # Run container in detached mode to stream logs
            container = self.docker.containers.run(
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
                    "claude-code-credentials": {"bind": "/home/node/.claude", "mode": "rw"}
                },
                working_dir="/workspace",
                user="node",
                detach=True,  # Run in detached mode to stream logs
                auto_remove=True
            )
            
            # Stream container logs to the user
            for line in container.logs(stream=True, follow=True):
                print(line.decode('utf-8', errors='ignore').rstrip())
            
            # Wait for container to finish
            result = container.wait()
            
            print("-" * 50)
            if result['StatusCode'] == 0:
                print(f"Agent completed successfully")
            else:
                print(f"Agent failed with exit code: {result['StatusCode']}")
            
        except Exception as e:
            print(f"Agent failed: {e}")
            # Try to get container logs if it exists
            try:
                failed_container = self.docker.containers.get(name)
                print("Container logs:")
                print(failed_container.logs().decode('utf-8', errors='ignore'))
            except:
                pass
            
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
        
        # Remove all worktrees
        result = self._run_command(["git", "worktree", "list"])
        for line in result.stdout.strip().split("\n"):
            if "/worktrees/" in line:
                path = line.split()[0]
                print(f"Removing worktree: {path}")
                self._run_command(["git", "worktree", "remove", path])
        
        # Delete agent branches
        result = self._run_command(["git", "branch"])
        for line in result.stdout.strip().split("\n"):
            branch = line.strip().lstrip("* ")  # Remove current branch indicator
            if branch.startswith("agent--") or branch.startswith("test-"):
                print(f"Deleting branch: {branch}")
                self._run_command(["git", "branch", "-D", branch])
        
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
