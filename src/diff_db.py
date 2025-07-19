#!/usr/bin/env python3
"""Diff database model for agent process tracking."""

from enum import Enum
from typing import Optional, Dict, Any, List
from .db import Database


class DiffStatus(Enum):
    """Status of diff generation for an agent."""
    AGENT_RUNNING = "AGENT_RUNNING"
    AGENT_COMPLETE = "AGENT_COMPLETE"
    DONE = "DONE"


class DiffDatabase(Database):
    """Database operations for diff management."""
    
    def _init_database(self):
        """Initialize diff-related database schema."""
        self.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL UNIQUE,
                project TEXT NOT NULL,
                goal TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                diff_status TEXT DEFAULT 'AGENT_RUNNING',
                diff_content TEXT,
                exit_code INTEGER,
                error_message TEXT
            )
        """)
        
        self.execute("CREATE INDEX IF NOT EXISTS idx_requests_agent_name ON requests(agent_name)")
    
    def update_request_status(self, agent_name: str, diff_status: DiffStatus, 
                            exit_code: Optional[int] = None, 
                            error_message: Optional[str] = None):
        """Update the status of an agent request."""
        update_fields = ["diff_status = ?"]
        params = [diff_status.value]
        
        if diff_status == DiffStatus.AGENT_COMPLETE:
            update_fields.append("completed_at = CURRENT_TIMESTAMP")
        
        if exit_code is not None:
            update_fields.append("exit_code = ?")
            params.append(exit_code)
        
        if error_message is not None:
            update_fields.append("error_message = ?")
            params.append(error_message)
        
        params.append(agent_name)
        
        self.execute(f"""
            UPDATE requests 
            SET {', '.join(update_fields)}
            WHERE agent_name = ?
        """, tuple(params))
    
    def save_diff(self, agent_name: str, diff_content: str):
        """Save the diff content and update status to DONE."""
        self.execute("""
            UPDATE requests 
            SET diff_content = ?, diff_status = ?
            WHERE agent_name = ?
        """, (diff_content, DiffStatus.DONE.value, agent_name))
    
    def list_diffs_by_project(self, project: str, limit: int = 50) -> List[Dict[str, Any]]:
        """List diffs for a specific project, or all projects if project is empty."""
        if project:
            return self.fetch_all("""
                SELECT agent_name, project, goal, started_at, completed_at, diff_status
                FROM requests 
                WHERE project = ? AND diff_status = 'DONE'
                ORDER BY completed_at DESC 
                LIMIT ?
            """, (project, limit))
        else:
            return self.fetch_all("""
                SELECT agent_name, project, goal, started_at, completed_at, diff_status
                FROM requests 
                WHERE diff_status = 'DONE'
                ORDER BY completed_at DESC 
                LIMIT ?
            """, (limit,))
    
    def get_diff_by_agent_name(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific diff by agent name."""
        return self.fetch_one("""
            SELECT * FROM requests WHERE agent_name = ? AND diff_status = 'DONE'
        """, (agent_name,))