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
    DONE_AND_NONE = "DONE_AND_NONE"


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
    
    def update_request_status(self, agent_id: str, diff_status: DiffStatus, 
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
        
        params.append(agent_id)
        
        self.execute(f"""
            UPDATE requests 
            SET {', '.join(update_fields)}
            WHERE agent_name = ?
        """, tuple(params))
    
    def save_diff(self, agent_id: str, diff_content: str):
        """Save the diff content and update status to DONE or DONE_AND_NONE."""
        # Choose status based on whether diff has content
        status = DiffStatus.DONE_AND_NONE if not diff_content.strip() else DiffStatus.DONE
        self.execute("""
            UPDATE requests 
            SET diff_content = ?, diff_status = ?
            WHERE agent_name = ?
        """, (diff_content, status.value, agent_id))
    
    
    def get_diff_by_agent_name(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific diff by agent ID."""
        return self.fetch_one("""
            SELECT * FROM requests WHERE agent_name = ? AND (diff_status = 'DONE' OR diff_status = 'DONE_AND_NONE')
        """, (agent_id,))