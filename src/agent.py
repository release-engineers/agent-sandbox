#!/usr/bin/env python3
"""Agent related operations for the agent process manager."""

from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .agent_db import AgentDatabase
from .diff import DiffManager, DiffStatus
from .workspace import WorkspaceManager
from .log import AgentLogFormatter, LogManager


class AgentManager:
    """Manages Claude Code agents with Docker and git worktrees."""
    
    def __init__(self, db_path: str):
        self.console = Console()
        self.db = AgentDatabase(db_path)
        self.diff_manager = DiffManager(db_path)
        self.workspace_manager = WorkspaceManager()
        self.log_manager = LogManager(db_path)
        self.log_formatter = None
        self.project_name = Path.cwd().name
    
    def start_agent(self, name: str, goal: str):
        """Start a new agent."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        unique_name = f"{name}-{timestamp}"
        
        self.console.print(f"🚀 Starting agent [cyan]{name}[/cyan] ({unique_name})")
        self.console.print(f"   Goal: {goal}")
        
        self.workspace_manager.cleanup_existing_agent(unique_name)
        
        request_id = self.db.create_request(unique_name, self.project_name, goal)
        
        self.log_formatter = AgentLogFormatter(self.console, self.log_manager._db, request_id)
        
        try:
            workspace_path = self.workspace_manager.create_workspace(unique_name)
            self.workspace_manager.setup_claude_settings(workspace_path)
            self.workspace_manager.build_images()
            self.workspace_manager.ensure_network()
            self.workspace_manager.start_proxy_container(unique_name)
            
            exit_code = self.workspace_manager.run_agent_container(
                unique_name, goal, workspace_path, self.log_formatter
            )
            
            self.diff_manager.update_agent_status(unique_name, DiffStatus.AGENT_COMPLETE, exit_code=exit_code)
            
            if exit_code == 0:
                self.console.print("✅ Agent completed successfully")
            else:
                self.console.print(f"❌ Agent failed with exit code: {exit_code}")
                self.diff_manager.update_agent_status(
                    unique_name, DiffStatus.AGENT_COMPLETE, 
                    exit_code=exit_code, 
                    error_message=f"Agent failed with exit code {exit_code}"
                )
            
        except Exception as e:
            self.console.print(f"❌ Agent failed: {e}")
            self.diff_manager.update_agent_status(
                unique_name, DiffStatus.AGENT_COMPLETE, 
                exit_code=-1, 
                error_message=str(e)
            )
        finally:
            self._cleanup_and_commit(unique_name)
    
    def _cleanup_and_commit(self, name: str):
        """Clean up containers and generate diff."""
        self.console.print("🧹 Cleaning up and generating diff...")
        
        self.workspace_manager.stop_containers(name)
        
        workspace_path = self.workspace_manager.worktree_dir / name
        if workspace_path.exists():
            self.diff_manager.generate_diff(name, workspace_path)
            self.workspace_manager.remove_workspace(name)
        
        self.console.print(f"✅ Agent {name} completed successfully")
    
    def list_agents(self):
        """List agent workspaces and database records."""
        requests = self.diff_manager.list_diffs_by_project(self.project_name, limit=20)
        
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
            completed = req['completed_at'] if req['completed_at'] else None
            started = req['started_at'] if req['started_at'] else None
            most_recent = completed if completed else started if started else '-'
            
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
        
        if requests:
            self.console.print(f"\n[dim]Use 'ags apply <agent-name>' to apply a specific diff[/dim]")
        
        active_containers = self.workspace_manager.list_active_containers()
        if active_containers:
            self.console.print(f"\n[cyan]Active containers:[/cyan] {', '.join(active_containers)}")
    
    def stop_agent(self, name: str):
        """Stop and remove an agent (for backward compatibility)."""
        self.console.print(f"⏹ Stopping agent: {name}")
        self._cleanup_and_commit(name)
    
    def cleanup_all(self):
        """Clean up all agents and resources."""
        self.workspace_manager.cleanup_all()
    
    def auth(self):
        """Run Claude Code authentication."""
        self.console.print("🔐 Starting Claude Code authentication...")
        self.console.print("   Follow the prompts to authenticate with your Claude account.")
        self.workspace_manager.run_auth_container()
    
    def show_agent_logs(self, name: str):
        """View logs for a specific agent."""
        self.log_formatter = AgentLogFormatter(self.console)
        
        status = self.db.get_agent_status(name)
        if not status:
            self.console.print(f"[red]Agent '{name}' not found in database[/red]")
            return
        
        self.console.print(f"📋 Agent: [cyan]{name}[/cyan]")
        self.console.print(f"   Goal: {status['goal']}")
        self.console.print(f"   Status: {status['diff_status']}")
        self.console.print(f"   Started: {status['started_at'] or '-'}")
        self.console.print(f"   Completed: {status['completed_at'] or '-'}")
        
        self.log_manager.display_agent_logs(name, self.log_formatter)
    
    def apply_diff(self, agent_name: str):
        """Apply a specific diff by agent name."""
        diff_record = self.diff_manager.get_diff_by_agent_name(agent_name)
        if not diff_record:
            self.console.print(f"[red]No diff found for agent '{agent_name}'[/red]")
            return
        
        if not diff_record['diff_content']:
            self.console.print(f"[red]No diff content available for agent '{agent_name}'[/red]")
            return
        
        self.console.print(f"📄 Applying diff for [cyan]{diff_record['agent_name']}[/cyan]")
        self.console.print(f"   Project: {diff_record['project']}")
        self.console.print(f"   Goal: {diff_record['goal']}")
        self.console.print(f"   Completed: {diff_record['completed_at'] or '-'}")
        
        if not self.diff_manager.apply_diff(agent_name):
            self.console.print(f"[red]Failed to apply diff for agent '{agent_name}'[/red]")