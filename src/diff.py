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
    
    def generate_diff(self, agent_id: str, workspace_path: Path) -> bool:
        """Generate a diff of agent changes."""
        try:
            result = self._run_command(["git", "-C", str(workspace_path), "diff"])
            
            if result.stdout.strip():
                self._db.save_diff(agent_id, result.stdout)
                self.console.print("📄 Diff generated and saved to database")
                return True
            else:
                self.console.print("[dim]No changes detected[/dim]")
                self._db.save_diff(agent_id, "")
                return True
                
        except Exception as e:
            self.console.print(f"⚠️ Failed to generate diff: {e}")
            self._db.update_request_status(agent_id, DiffStatus.DONE, 
                                        error_message=f"Failed to generate diff: {e}")
            return False
    
    def update_agent_status(self, agent_id: str, status: DiffStatus, 
                          exit_code: Optional[int] = None, 
                          error_message: Optional[str] = None):
        """Update agent status."""
        self._db.update_request_status(agent_id, status, exit_code, error_message)
    
    
    def get_diff_by_agent_name(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific diff by agent ID."""
        return self._db.get_diff_by_agent_name(agent_id)
    
    def apply_diff(self, agent_id: str) -> bool:
        """Apply a specific diff by agent ID."""
        diff_record = self.get_diff_by_agent_name(agent_id)
        if not diff_record:
            self.console.print(f"[red]No diff found for agent '{agent_id}'[/red]")
            return False
        
        if not diff_record['diff_content']:
            self.console.print(f"[red]No diff content available for agent '{agent_id}'[/red]")
            return False
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.diff', delete=False) as temp_file:
                temp_file.write(diff_record['diff_content'])
                temp_file_path = temp_file.name
            
            try:
                result = self._run_command(["git", "apply", temp_file_path])
                
                if result.returncode == 0:
                    self.console.print(f"✅ Successfully applied diff for agent '{agent_id}'")
                    return True
                else:
                    self.console.print(f"❌ Failed to apply diff: {result.stderr}")
                    return False
            finally:
                Path(temp_file_path).unlink(missing_ok=True)
                
        except Exception as e:
            self.console.print(f"[red]Failed to apply diff: {e}[/red]")
            return False
    
    def _run_command(self, cmd: list[str]) -> subprocess.CompletedProcess:
        """Run a command and return result."""
        return subprocess.run(cmd, capture_output=True, text=True)