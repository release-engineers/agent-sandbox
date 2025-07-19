#!/usr/bin/env python3
"""Database management for agent process tracking."""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from enum import Enum
import threading


class DiffStatus(Enum):
    """Status of diff generation for an agent."""
    AGENT_RUNNING = "AGENT_RUNNING"
    AGENT_COMPLETE = "AGENT_COMPLETE"
    DONE = "DONE"


class AgentDatabase:
    """Manages SQLite database for agent requests and logs."""
    
    def __init__(self, db_path: str = "agents.db"):
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create requests table
            cursor.execute("""
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
            
            # Create logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    level TEXT,
                    message TEXT,
                    tool_name TEXT,
                    hook_event TEXT,
                    tool_input TEXT,
                    raw_log TEXT,
                    FOREIGN KEY (request_id) REFERENCES requests (id)
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_request_id ON logs(request_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_requests_agent_name ON requests(agent_name)")
            
            conn.commit()
    
    def create_request(self, agent_name: str, project: str, goal: str) -> int:
        """Create a new agent request."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO requests (agent_name, project, goal, started_at, diff_status)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
                """, (agent_name, project, goal, DiffStatus.AGENT_RUNNING.value))
                return cursor.lastrowid
    
    def update_request_status(self, agent_name: str, diff_status: DiffStatus, 
                            exit_code: Optional[int] = None, 
                            error_message: Optional[str] = None):
        """Update the status of an agent request."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
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
                
                cursor.execute(f"""
                    UPDATE requests 
                    SET {', '.join(update_fields)}
                    WHERE agent_name = ?
                """, params)
                conn.commit()
    
    def save_diff(self, agent_name: str, diff_content: str):
        """Save the diff content and update status to DONE."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE requests 
                    SET diff_content = ?, diff_status = ?
                    WHERE agent_name = ?
                """, (diff_content, DiffStatus.DONE.value, agent_name))
                conn.commit()
    
    def get_request_id(self, agent_name: str) -> Optional[int]:
        """Get the request ID for an agent."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM requests WHERE agent_name = ?", (agent_name,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def log_message(self, request_id: int, message: str, level: str = "INFO", 
                   raw_log: Optional[str] = None):
        """Log a simple message."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO logs (request_id, level, message, raw_log)
                    VALUES (?, ?, ?, ?)
                """, (request_id, level, message, raw_log))
                conn.commit()
    
    def log_tool_event(self, request_id: int, tool_name: str, hook_event: str,
                      tool_input: Dict[str, Any], timestamp: Optional[str] = None,
                      raw_log: Optional[str] = None):
        """Log a tool event with structured data."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Use provided timestamp or current time
                if timestamp:
                    try:
                        # Parse ISO format timestamp
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        timestamp_sql = dt.strftime('%Y-%m-%d %H:%M:%S.%f')
                    except:
                        timestamp_sql = "CURRENT_TIMESTAMP"
                else:
                    timestamp_sql = "CURRENT_TIMESTAMP"
                
                cursor.execute("""
                    INSERT INTO logs (request_id, timestamp, tool_name, hook_event, 
                                    tool_input, level, raw_log)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (request_id, timestamp_sql, tool_name, hook_event, 
                     json.dumps(tool_input), "TOOL", raw_log))
                conn.commit()
    
    def get_agent_logs(self, agent_name: str) -> List[Dict[str, Any]]:
        """Get all logs for an agent."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT l.* FROM logs l
                JOIN requests r ON l.request_id = r.id
                WHERE r.agent_name = ?
                ORDER BY l.timestamp
            """, (agent_name,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_agent_status(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get the current status of an agent."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM requests WHERE agent_name = ?
            """, (agent_name,))
            result = cursor.fetchone()
            return dict(result) if result else None
    
    def list_requests(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent agent requests."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM requests 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def list_diffs_by_project(self, project: str, limit: int = 50) -> List[Dict[str, Any]]:
        """List diffs for a specific project, or all projects if project is empty."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if project:
                cursor.execute("""
                    SELECT agent_name, project, goal, started_at, completed_at, diff_status
                    FROM requests 
                    WHERE project = ? AND diff_status = 'DONE'
                    ORDER BY completed_at DESC 
                    LIMIT ?
                """, (project, limit,))
            else:
                cursor.execute("""
                    SELECT agent_name, project, goal, started_at, completed_at, diff_status
                    FROM requests 
                    WHERE diff_status = 'DONE'
                    ORDER BY completed_at DESC 
                    LIMIT ?
                """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_diff_by_agent_name(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific diff by agent name."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM requests WHERE agent_name = ? AND diff_status = 'DONE'
            """, (agent_name,))
            result = cursor.fetchone()
            return dict(result) if result else None