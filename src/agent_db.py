#!/usr/bin/env python3
"""Agent database model for agent process tracking."""

from typing import Optional, Dict, Any, List
from .db import Database


class AgentDatabase(Database):
    """Database operations for agent management."""
    
    def _init_database(self):
        """Initialize agent-related database schema."""
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
    
    def create_request(self, agent_id: str, project: str, goal: str) -> int:
        """Create a new agent request."""
        return self.execute("""
            INSERT INTO requests (agent_name, project, goal, started_at, diff_status)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, 'AGENT_RUNNING')
        """, (agent_id, project, goal))
    
    def get_request_id(self, agent_id: str) -> Optional[int]:
        """Get the request ID for an agent."""
        result = self.fetch_one("SELECT id FROM requests WHERE agent_name = ?", (agent_id,))
        return result['id'] if result else None
    
    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of an agent."""
        return self.fetch_one("SELECT * FROM requests WHERE agent_name = ?", (agent_id,))
    
    def list_requests(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent agent requests."""
        return self.fetch_all("""
            SELECT * FROM requests 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (limit,))