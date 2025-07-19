#!/usr/bin/env python3
"""Diff related operations for agent process tracking."""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from rich.console import Console

from .diff_db import DiffDatabase, DiffStatus


class DiffManager:
    """Manages diff operations without exposing database internals."""
    
    def __init__(self, db_path: str):
        self._db = DiffDatabase(db_path)
        self.console = Console()
    
    def generate_diff(self, agent_name: str, workspace_path: Path) -> bool:
        """Generate a diff of agent changes."""
        try:
            result = self._run_command(["git", "-C", str(workspace_path), "diff"])
            
            if result.stdout.strip():
                self._db.save_diff(agent_name, result.stdout)
                self.console.print(f"[green]📄 Diff generated and saved to database[/green]")
                return True
            else:
                self.console.print("[dim]No changes detected[/dim]")
                self._db.save_diff(agent_name, "")
                return True
                
        except Exception as e:
            self.console.print(f"[red]⚠️  Failed to generate diff: {e}[/red]")
            self._db.update_request_status(agent_name, DiffStatus.DONE, 
                                        error_message=f"Failed to generate diff: {e}")
            return False
    
    def update_agent_status(self, agent_name: str, status: DiffStatus, 
                          exit_code: Optional[int] = None, 
                          error_message: Optional[str] = None):
        """Update agent status."""
        self._db.update_request_status(agent_name, status, exit_code, error_message)
    
    def list_diffs_by_project(self, project: str, limit: int = 50) -> List[Dict[str, Any]]:
        """List diffs for a specific project."""
        return self._db.list_diffs_by_project(project, limit)
    
    def get_diff_by_agent_name(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific diff by agent name."""
        return self._db.get_diff_by_agent_name(agent_name)
    
    def apply_diff(self, agent_name: str) -> bool:
        """Apply a specific diff by agent name."""
        diff_record = self.get_diff_by_agent_name(agent_name)
        if not diff_record:
            self.console.print(f"[red]No diff found for agent '{agent_name}'[/red]")
            return False
        
        if not diff_record['diff_content']:
            self.console.print(f"[red]No diff content available for agent '{agent_name}'[/red]")
            return False
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.diff', delete=False) as temp_file:
                temp_file.write(diff_record['diff_content'])
                temp_file_path = temp_file.name
            
            try:
                result = self._run_command(["git", "apply", temp_file_path])
                
                if result.returncode == 0:
                    self.console.print(f"[green]✅ Successfully applied diff for agent '{agent_name}'[/green]")
                    return True
                else:
                    self.console.print(f"[red]❌ Failed to apply diff: {result.stderr}[/red]")
                    return False
            finally:
                Path(temp_file_path).unlink(missing_ok=True)
                
        except Exception as e:
            self.console.print(f"[red]Failed to apply diff: {e}[/red]")
            return False
    
    def _run_command(self, cmd: list[str]) -> subprocess.CompletedProcess:
        """Run a command and return result."""
        return subprocess.run(cmd, capture_output=True, text=True)