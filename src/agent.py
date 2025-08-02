#!/usr/bin/env python3
"""Agent related operations for the agent process manager."""

from datetime import datetime
from pathlib import Path
from rich.console import Console

from .agent_db import AgentDatabase
from .diff import DiffManager, DiffStatus
from .workspace import WorkspaceManager
from .log import AgentLogFormatter, LogManager
from typing import Optional

class AgentManager:
    """Manages Claude Code agents with Docker and git worktrees."""
    
    def __init__(self, db_path: str, project_path: Optional[str] = None):
        self.console = Console()
        self.db = AgentDatabase(db_path)
        self.diff_manager = DiffManager(db_path)
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.workspace_manager = WorkspaceManager(self.project_path)
        self.log_manager = LogManager(db_path)
        self.log_formatter = None
        self.project_name = self.project_path.name
    
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
    
    
    
    def cleanup_all(self):
        """Clean up all agents and resources."""
        self.workspace_manager.cleanup_all()
    
    
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