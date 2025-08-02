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
                agent_name TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                level TEXT,
                message TEXT,
                tool_name TEXT,
                hook_event TEXT,
                tool_input TEXT,
                tool_type TEXT,
                raw_log TEXT
            )
        """)
        
        self.execute("CREATE INDEX IF NOT EXISTS idx_logs_agent_name ON logs(agent_name)")
        self.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)")
    
    def log_message(self, agent_name: str, message: str, level: str = "INFO", 
                   tool_name: str = None, tool_type: str = None, raw_log: str = None):
        """Log a message for an agent."""
        self.execute("""
            INSERT INTO logs (agent_name, level, message, tool_name, tool_type, raw_log)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (agent_name, level, message, tool_name, tool_type, raw_log))
    
    def log_tool_event(self, agent_name: str, tool_name: str, hook_event: str,
                      tool_input: Dict[str, Any], timestamp: Optional[str] = None,
                      raw_log: Optional[str] = None):
        """Log a tool event with structured data."""
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp_sql = dt.strftime('%Y-%m-%d %H:%M:%S.%f')
            except:
                timestamp_sql = None
        else:
            timestamp_sql = None
        
        if timestamp_sql:
            self.execute("""
                INSERT INTO logs (agent_name, timestamp, tool_name, hook_event, 
                                tool_input, level, raw_log)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (agent_name, timestamp_sql, tool_name, hook_event, 
                 json.dumps(tool_input), "TOOL", raw_log))
        else:
            self.execute("""
                INSERT INTO logs (agent_name, tool_name, hook_event, 
                                tool_input, level, raw_log)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (agent_name, tool_name, hook_event, 
                 json.dumps(tool_input), "TOOL", raw_log))
    
    def get_logs_by_agent_name(self, agent_name: str) -> List[Dict[str, Any]]:
        """Get all logs for an agent."""
        return self.fetch_all("""
            SELECT timestamp, level, message, tool_name, tool_type, hook_event, tool_input, raw_log
            FROM logs
            WHERE agent_name = ?
            ORDER BY timestamp
        """, (agent_name,))