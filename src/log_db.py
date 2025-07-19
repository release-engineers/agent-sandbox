#!/usr/bin/env python3
"""Log database model for agent process tracking."""

import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from .db import Database


class LogDatabase(Database):
    """Database operations for log management."""
    
    def _init_database(self):
        """Initialize log-related database schema."""
        self.execute("""
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
        
        self.execute("CREATE INDEX IF NOT EXISTS idx_logs_request_id ON logs(request_id)")
        self.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)")
    
    def log_message(self, request_id: int, message: str, level: str = "INFO", 
                   raw_log: Optional[str] = None):
        """Log a simple message."""
        self.execute("""
            INSERT INTO logs (request_id, level, message, raw_log)
            VALUES (?, ?, ?, ?)
        """, (request_id, level, message, raw_log))
    
    def log_tool_event(self, request_id: int, tool_name: str, hook_event: str,
                      tool_input: Dict[str, Any], timestamp: Optional[str] = None,
                      raw_log: Optional[str] = None):
        """Log a tool event with structured data."""
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp_sql = dt.strftime('%Y-%m-%d %H:%M:%S.%f')
            except:
                timestamp_sql = "CURRENT_TIMESTAMP"
        else:
            timestamp_sql = "CURRENT_TIMESTAMP"
        
        self.execute("""
            INSERT INTO logs (request_id, timestamp, tool_name, hook_event, 
                            tool_input, level, raw_log)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (request_id, timestamp_sql, tool_name, hook_event, 
             json.dumps(tool_input), "TOOL", raw_log))
    
    def get_agent_logs(self, agent_name: str) -> List[Dict[str, Any]]:
        """Get all logs for an agent."""
        return self.fetch_all("""
            SELECT l.* FROM logs l
            JOIN requests r ON l.request_id = r.id
            WHERE r.agent_name = ?
            ORDER BY l.timestamp
        """, (agent_name,))