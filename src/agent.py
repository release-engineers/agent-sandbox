#!/usr/bin/env python3
"""Agent related operations for the agent process manager."""

from datetime import datetime
from pathlib import Path
from rich.console import Console

from .agent_db import AgentDatabase
from .diff import DiffManager, DiffStatus
from .workspace import WorkspaceManager
from .log import AgentLogFormatter, LogManager
from .result_db import ResultDatabase
from .result_collector import ResultType, AgentPhase, get_collector, QualityScorer, get_target_files_for_phase
from typing import Optional, List

class AgentManager:
    """Manages Claude Code agents with Docker and git worktrees."""
    
    def __init__(self, db_path: str = None, project_path: Optional[str] = None):
        self.console = Console()
        self.db = AgentDatabase(db_path)
        self.diff_manager = DiffManager(db_path)
        self.result_db = ResultDatabase(db_path)
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.log_manager = LogManager(db_path)
        self.workspace_manager = WorkspaceManager(self.project_path, self.log_manager)
        self.log_formatter = None
        self.project_name = self.project_path.name
        self.quality_scorer = QualityScorer()
    
    def _log_system_message(self, agent_name: str, message: str, level: str = "INFO"):
        """Log system messages to database only."""
        # Store in database as system log
        self.log_manager.log_message(agent_name, level, message, tool_name="SYSTEM", tool_type="AGS")
    
    def start_agent(self, goal: str, project_id: str, phase: str = 'implementation', 
                   result_type: str = 'git_diff', target_files: Optional[List[str]] = None):
        """Start a new agent with configurable result collection."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        agent_id = f"agent--{timestamp}"
        
        # Enhance goal with file creation instructions for document phases
        enhanced_goal = goal
        if result_type == 'document' and target_files:
            target_file = target_files[0]  # Use first target file
            enhanced_goal = f"{goal}\n\nIMPORTANT: Please create your response as a markdown document and save it to a file named '{target_file}' in the workspace."
        
        # Create agent record first so we can log to it
        agent_record_id = self.db.create_agent(agent_id, enhanced_goal, project_id=project_id, 
                                              phase=phase, result_type=result_type)
        
        self._log_system_message(agent_id, f"🚀 Starting agent {agent_id}")
        self._log_system_message(agent_id, f"   Goal: {enhanced_goal}")
        
        self.workspace_manager.cleanup_existing_agent(agent_id)
        
        
        self.log_formatter = AgentLogFormatter(self.console, self.log_manager._db, agent_id)
        
        try:
            workspace_path = self.workspace_manager.create_workspace(agent_id)
            self.workspace_manager.setup_claude_settings(workspace_path)
            self.workspace_manager.build_images()
            self.workspace_manager.ensure_network()
            self.workspace_manager.start_proxy_container(agent_id)
            
            self._log_system_message(agent_id, "🤖 Starting agent container...")
            
            exit_code = self.workspace_manager.run_agent_container(
                agent_id, enhanced_goal, workspace_path
            )
            
            self.diff_manager.update_agent_status(agent_id, DiffStatus.AGENT_COMPLETE, exit_code=exit_code)
            
            if exit_code == 0:
                self._log_system_message(agent_id, "✅ Agent completed successfully")
            else:
                self._log_system_message(agent_id, f"❌ Agent failed with exit code: {exit_code}", "ERROR")
                self.diff_manager.update_agent_status(
                    agent_id, DiffStatus.AGENT_COMPLETE, 
                    exit_code=exit_code, 
                    error_message=f"Agent failed with exit code {exit_code}"
                )
            
        except Exception as e:
            self._log_system_message(agent_id, f"❌ Agent failed: {e}", "ERROR")
            self.diff_manager.update_agent_status(
                agent_id, DiffStatus.AGENT_COMPLETE, 
                exit_code=-1, 
                error_message=str(e)
            )
        finally:
            self._cleanup_and_commit(agent_id)
    
    def _cleanup_and_commit(self, agent_id: str):
        """Clean up containers and collect results."""
        self._log_system_message(agent_id, "🧹 Cleaning up and collecting results...")
        
        self.workspace_manager.stop_containers(agent_id)
        
        workspace_path = self.workspace_manager.worktree_dir / agent_id
        if workspace_path.exists():
            # Get agent info to determine collection method
            agent_info = self.db.get_agent_by_name(agent_id)
            if agent_info:
                phase = agent_info.get('phase', 'implementation')
                result_type_str = agent_info.get('result_type', 'git_diff')
                
                # Collect results based on type
                try:
                    if result_type_str == 'quality':
                        # Run quality scoring
                        metadata = self.quality_scorer.score(str(workspace_path))
                        content = f"Quality Score: {metadata['quality_score']}"
                        self.result_db.save_result(agent_id, phase, result_type_str, 
                                                 content, metadata=metadata)
                    else:
                        # Use appropriate collector
                        result_type = ResultType(result_type_str)
                        collector = get_collector(result_type)
                        
                        # Determine target files for document collection
                        target_files = None
                        if result_type_str == 'document':
                            target_files = get_target_files_for_phase(phase)
                        
                        content = collector.collect(str(workspace_path), target_files)
                        self.result_db.save_result(agent_id, phase, result_type_str, content, target_files=target_files)
                    
                    # Update status based on content
                    if content:
                        self.db.update_agent_diff_status(agent_id, 'DONE')
                    else:
                        self.db.update_agent_diff_status(agent_id, 'DONE_AND_NONE')
                        
                except Exception as e:
                    self._log_system_message(agent_id, f"❌ Result collection failed: {e}", "ERROR")
                    self.db.update_agent_diff_status(agent_id, 'ERROR')
            
            # Still maintain backward compatibility for diff generation
            if agent_info and agent_info.get('result_type') == 'git_diff':
                self.diff_manager.generate_diff(agent_id, workspace_path)
            
            self.workspace_manager.remove_workspace(agent_id)
        
        self._log_system_message(agent_id, f"✅ Agent {agent_id} processing completed")
    
    
    
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
    
    def get_agent_results(self, agent_name: str) -> List[dict]:
        """Get all results for an agent."""
        return self.result_db.get_all_results(agent_name)
    
    def get_agent_result(self, agent_name: str, phase: str) -> Optional[dict]:
        """Get a specific phase result for an agent."""
        return self.result_db.get_result(agent_name, phase)
    
    def run_quality_check(self, agent_name: str) -> dict:
        """Run quality check on an agent's results."""
        # Get the implementation phase result if exists
        impl_result = self.result_db.get_result(agent_name, AgentPhase.IMPLEMENTATION.value)
        if impl_result and impl_result['result_type'] == ResultType.GIT_DIFF.value:
            # Score based on the diff
            metadata = self.quality_scorer.score(None, impl_result['content'])
            
            # Save quality result
            self.result_db.save_result(
                agent_name, 
                AgentPhase.QUALITY_CHECK.value,
                ResultType.QUALITY.value,
                f"Quality Score: {metadata['quality_score']}",
                metadata=metadata
            )
            return metadata
        else:
            return {"quality_score": 100, "message": "No implementation to check"}
    
