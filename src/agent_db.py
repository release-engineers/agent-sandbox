#!/usr/bin/env python3
"""Agent database model for agent process tracking."""

from typing import Optional, Dict, Any, List
from datetime import datetime
from .db import Database


class AgentDatabase(Database):
    """Database operations for agent management."""
    
    def __init__(self, db_path: str = None):
        super().__init__(db_path)
        self._init_tables()
    
    def _init_tables(self):
        """Initialize agent-related database schema."""
        # Update schema to include project_id
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    project_id TEXT,
                    goal TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    status TEXT DEFAULT 'AGENT_RUNNING',
                    diff_status TEXT,
                    error_message TEXT
                )
            """)
            
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agents_name ON agents(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agents_project ON agents(project_id)")
            conn.commit()
    
    def create_agent(self, name: str, goal: str, project_id: Optional[str] = None) -> int:
        """Create a new agent record."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO agents (name, project_id, goal, started_at, status)
                VALUES (?, ?, ?, ?, 'AGENT_RUNNING')
            """, (name, project_id, goal, now))
            conn.commit()
            return cursor.lastrowid
    
    def get_all_agents(self) -> List[Dict[str, Any]]:
        """Get all agents."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM agents ORDER BY started_at DESC
            """)
            
            agents = []
            for row in cursor.fetchall():
                agents.append({
                    "id": row[0],
                    "name": row[1],
                    "project_id": row[2],
                    "goal": row[3],
                    "started_at": row[4],
                    "ended_at": row[5],
                    "status": row[6],
                    "diff_status": row[7],
                    "error_message": row[8]
                })
            return agents
    
    def get_agent_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get agent by name."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM agents WHERE name = ?", (name,))
            row = cursor.fetchone()
            
            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "project_id": row[2],
                    "goal": row[3],
                    "started_at": row[4],
                    "ended_at": row[5],
                    "status": row[6],
                    "diff_status": row[7],
                    "error_message": row[8]
                }
            return None
    
    def update_agent_status(self, name: str, status: str, error_message: Optional[str] = None):
        """Update agent status."""
        with self._get_connection() as conn:
            if error_message:
                conn.execute("""
                    UPDATE agents SET status = ?, error_message = ? WHERE name = ?
                """, (status, error_message, name))
            else:
                conn.execute("""
                    UPDATE agents SET status = ? WHERE name = ?
                """, (status, name))
            conn.commit()
    
    def update_agent_ended(self, name: str):
        """Update agent ended timestamp."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE agents SET ended_at = ? WHERE name = ?
            """, (now, name))
            conn.commit()
    
    def update_agent_diff_status(self, name: str, diff_status: str):
        """Update agent diff status."""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE agents SET diff_status = ? WHERE name = ?
            """, (diff_status, name))
            conn.commit()
    
    def get_agent_status(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get the current status of an agent."""
        return self.get_agent_by_name(agent_name)