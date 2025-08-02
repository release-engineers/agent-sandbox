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
            CREATE TABLE IF NOT EXISTS diffs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL UNIQUE,
                content TEXT,
                status TEXT DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.execute("CREATE INDEX IF NOT EXISTS idx_diffs_agent_name ON diffs(agent_name)")
    
    def update_agent_status(self, agent_name: str, diff_status: DiffStatus, 
                            exit_code: Optional[int] = None, 
                            error_message: Optional[str] = None):
        """Update the status of an agent."""
        from .agent_db import AgentDatabase
        agent_db = AgentDatabase()
        
        # Update agent status
        if diff_status == DiffStatus.AGENT_COMPLETE:
            agent_db.update_agent_ended(agent_name)
        
        agent_db.update_agent_diff_status(agent_name, diff_status.value)
        
        if error_message:
            agent_db.update_agent_status(agent_name, "ERROR", error_message)
    
    def save_diff(self, agent_name: str, diff_content: str):
        """Save the diff content and update status to DONE or DONE_AND_NONE."""
        # Choose status based on whether diff has content
        status = DiffStatus.DONE_AND_NONE if not diff_content.strip() else DiffStatus.DONE
        
        # Insert or replace diff record
        self.execute("""
            INSERT OR REPLACE INTO diffs (agent_name, content, status)
            VALUES (?, ?, ?)
        """, (agent_name, diff_content, status.value))
        
        # Update agent diff status
        from .agent_db import AgentDatabase
        agent_db = AgentDatabase()
        agent_db.update_agent_diff_status(agent_name, status.value)
    
    
    def get_diff_by_agent_name(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific diff by agent name."""
        return self.fetch_one("""
            SELECT * FROM diffs WHERE agent_name = ? AND (status = 'DONE' OR status = 'DONE_AND_NONE')
        """, (agent_name,))