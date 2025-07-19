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
from typing import Optional

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
    
    def start_agent(self, goal: str):
        """Start a new agent."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        agent_id = f"agent--{timestamp}"
        
        self.console.print(f"🚀 Starting agent [cyan]{agent_id}[/cyan]")
        self.console.print(f"   Goal: {goal}")
        
        self.workspace_manager.cleanup_existing_agent(agent_id)
        
        request_id = self.db.create_request(agent_id, self.project_name, goal)
        
        self.log_formatter = AgentLogFormatter(self.console, self.log_manager._db, request_id)
        
        try:
            workspace_path = self.workspace_manager.create_workspace(agent_id)
            self.workspace_manager.setup_claude_settings(workspace_path)
            self.workspace_manager.build_images()
            self.workspace_manager.ensure_network()
            self.workspace_manager.start_proxy_container(agent_id)
            
            exit_code = self.workspace_manager.run_agent_container(
                agent_id, goal, workspace_path, self.log_formatter
            )
            
            self.diff_manager.update_agent_status(agent_id, DiffStatus.AGENT_COMPLETE, exit_code=exit_code)
            
            if exit_code == 0:
                self.console.print("✅ Agent completed successfully")
            else:
                self.console.print(f"❌ Agent failed with exit code: {exit_code}")
                self.diff_manager.update_agent_status(
                    agent_id, DiffStatus.AGENT_COMPLETE, 
                    exit_code=exit_code, 
                    error_message=f"Agent failed with exit code {exit_code}"
                )
            
        except Exception as e:
            self.console.print(f"❌ Agent failed: {e}")
            self.diff_manager.update_agent_status(
                agent_id, DiffStatus.AGENT_COMPLETE, 
                exit_code=-1, 
                error_message=str(e)
            )
        finally:
            self._cleanup_and_commit(agent_id)
    
    def _cleanup_and_commit(self, agent_id: str):
        """Clean up containers and generate diff."""
        self.console.print("🧹 Cleaning up and generating diff...")
        
        self.workspace_manager.stop_containers(agent_id)
        
        workspace_path = self.workspace_manager.worktree_dir / agent_id
        if workspace_path.exists():
            self.diff_manager.generate_diff(agent_id, workspace_path)
            self.workspace_manager.remove_workspace(agent_id)
        
        self.console.print(f"✅ Agent {agent_id} completed successfully")
    
    def list_agents(self):
        """List agent workspaces and database records."""
        # Get all agent requests from the database
        all_requests = self.db.list_requests(limit=50)
        # Filter by current project
        requests = [req for req in all_requests if req.get('project') == self.project_name]
        
        table = Table(title=f"Agent Requests for Project: {self.project_name}", show_header=True, header_style="bold cyan", box=None)
        table.add_column("id", style="yellow", no_wrap=True)
        table.add_column("goal", style="white")
        table.add_column("status", style="magenta")
        table.add_column("project", style="cyan")
        table.add_column("timestamp", style="green")
        
        if not requests:
            self.console.print(table)
            return
        
        for req in requests:
            completed = req['completed_at'] if req['completed_at'] else None
            started = req['started_at'] if req['started_at'] else None
            most_recent = completed if completed else started if started else '-'
            
            table.add_row(
                req['agent_name'],
                req['goal'],
                req['diff_status'],
                req['project'],
                most_recent
            )
        
        self.console.print(table)
        
        if requests:
            self.console.print(f"\n[dim]To apply: ags diff <agent-id> | git apply[/dim]")
        
        active_containers = self.workspace_manager.list_active_containers()
        if active_containers:
            self.console.print(f"\n[cyan]Active containers:[/cyan] {', '.join(active_containers)}")
    
    def stop_agent(self, agent_id: str):
        """Stop and remove an agent (for backward compatibility)."""
        self.console.print(f"⏹ Stopping agent: {agent_id}")
        self._cleanup_and_commit(agent_id)
    
    def cleanup_all(self):
        """Clean up all agents and resources."""
        self.workspace_manager.cleanup_all()
    
    def auth(self):
        """Run Claude Code authentication."""
        self.console.print("🔐 Starting Claude Code authentication...")
        self.console.print("   Follow the prompts to authenticate with your Claude account.")
        self.workspace_manager.run_auth_container()
    
    def show_agent_logs(self, agent_id: str):
        """View logs for a specific agent."""
        self.log_formatter = AgentLogFormatter(self.console)
        
        status = self.db.get_agent_status(agent_id)
        if not status:
            self.console.print(f"[red]Agent '{agent_id}' not found in database[/red]")
            return
        
        self.console.print(f"📋 Agent: [cyan]{agent_id}[/cyan]")
        self.console.print(f"   Goal: {status['goal']}")
        self.console.print(f"   Status: {status['diff_status']}")
        self.console.print(f"   Started: {status['started_at'] or '-'}")
        self.console.print(f"   Completed: {status['completed_at'] or '-'}")
        
        self.log_manager.display_agent_logs(agent_id, self.log_formatter)
    
    def show_diff(self, agent_id: str):
        """Show the diff content for a specific agent."""
        diff_record = self.diff_manager.get_diff_by_agent_name(agent_id)
        if not diff_record:
            raise Exception(f"No diff found for agent '{agent_id}'")
        
        if not diff_record['diff_content']:
            raise Exception(f"No diff content available for agent '{agent_id}'")
        
        # Output only the diff content, nothing else
        print(diff_record['diff_content'], end='')
    
    def get_diff(self, agent_name: str) -> Optional[str]:
        """Get diff content for an agent."""
        diff_record = self.diff_manager.get_diff_by_agent_name(agent_name)
        if diff_record and diff_record.get('diff_content'):
            return diff_record['diff_content']
        return None
    
    def restart_agent(self, agent_name: str):
        """Restart an existing agent with the same goal."""
        # Get the existing agent record
        agent_record = self.db.get_agent_status(agent_name)
        if not agent_record:
            raise Exception(f"Agent '{agent_name}' not found")
        
        goal = agent_record['goal']
        
        self.console.print(f"🔄 Restarting agent [cyan]{agent_name}[/cyan]")
        self.console.print(f"   Goal: {goal}")
        
        # Reset the agent status and clear previous results
        self.db.execute("""
            UPDATE requests 
            SET started_at = CURRENT_TIMESTAMP, 
                completed_at = NULL,
                diff_status = 'AGENT_RUNNING',
                diff_content = NULL,
                exit_code = NULL,
                error_message = NULL
            WHERE agent_name = ?
        """, (agent_name,))
        
        request_id = self.db.get_request_id(agent_name)
        self.log_formatter = AgentLogFormatter(self.console, self.log_manager._db, request_id)
        
        try:
            workspace_path = self.workspace_manager.create_workspace(agent_name)
            self.workspace_manager.setup_claude_settings(workspace_path)
            self.workspace_manager.build_images()
            self.workspace_manager.ensure_network()
            self.workspace_manager.start_proxy_container(agent_name)
            
            exit_code = self.workspace_manager.run_agent_container(
                agent_name, goal, workspace_path, self.log_formatter
            )
            
            self.diff_manager.update_agent_status(agent_name, DiffStatus.AGENT_COMPLETE, exit_code=exit_code)
            
            if exit_code == 0:
                self.console.print("✅ Agent completed successfully")
            else:
                self.console.print(f"❌ Agent failed with exit code: {exit_code}")
                self.diff_manager.update_agent_status(
                    agent_name, DiffStatus.AGENT_COMPLETE, 
                    exit_code=exit_code, 
                    error_message=f"Agent failed with exit code {exit_code}"
                )
            
        except Exception as e:
            self.console.print(f"❌ Agent failed: {e}")
            self.diff_manager.update_agent_status(
                agent_name, DiffStatus.AGENT_COMPLETE, 
                exit_code=-1, 
                error_message=str(e)
            )
        finally:
            self._cleanup_and_commit(agent_name)