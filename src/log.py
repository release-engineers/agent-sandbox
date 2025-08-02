#!/usr/bin/env python3
"""Logging operations and formatting."""

import json
import re
from datetime import datetime
from typing import Optional, Dict, Any, List
from rich.console import Console

from .log_db import LogDatabase


class AgentLogFormatter:
    """Formats agent logs with rich styling."""
    
    def __init__(self, console: Console, db: Optional[LogDatabase] = None, agent_name: Optional[str] = None):
        self.console = console
        self.db = db
        self.agent_name = agent_name
        
        self.tool_colors = {
            'Read': 'blue',
            'Write': 'blue', 
            'Edit': 'blue',
            'MultiEdit': 'blue',
            'LS': 'blue',
            'Grep': 'cyan',
            'Glob': 'cyan',
            'WebSearch': 'cyan',
            'WebFetch': 'cyan',
            'Bash': 'yellow',
            'Task': 'green',
            'TodoWrite': 'green'
        }
        
        self.tool_icons = {
            'Task': '🎯',
            'Read': '📖',
            'Write': '📝',
            'Edit': '✏️',
            'MultiEdit': '✏️',
            'Bash': '💻',
            'Grep': '🔍',
            'Glob': '🔍',
            'LS': '📁',
            'TodoWrite': '📋',
            'WebSearch': '🌐',
            'WebFetch': '🌐'
        }
    
    def format_log_line(self, line: str):
        """Format log lines with rich styling."""
        if not line.strip():
            return
            
        try:
            log_data = json.loads(line.strip())
            self._format_json_log(log_data)
            
            if self.db and self.agent_name:
                if 'tool_name' in log_data:
                    self.db.log_tool_event(
                        agent_name=self.agent_name,
                        tool_name=log_data.get('tool_name', 'unknown'),
                        hook_event=log_data.get('hook_event_name', 'unknown'),
                        tool_input=log_data.get('tool_input', {}),
                        timestamp=log_data.get('timestamp'),
                        raw_log=line
                    )
                else:
                    self.db.log_message(
                        agent_name=self.agent_name,
                        message=str(log_data),
                        level='INFO',
                        raw_log=line
                    )
            return
        except json.JSONDecodeError:
            pass
            
        self.console.print(line)
        
        if self.db and self.agent_name:
            self.db.log_message(
                agent_name=self.agent_name,
                message=line,
                level='INFO',
                raw_log=line
            )
    
    def _format_json_log(self, log_data: dict):
        """Format JSON log data into simple timestamp + content format."""
        timestamp = log_data.get('timestamp', '')
        tool_name = log_data.get('tool_name', 'unknown')
        hook_event = log_data.get('hook_event_name', 'unknown')
        tool_input = log_data.get('tool_input', {})
        
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        except:
            time_str = timestamp
        
        details = self._format_tool_details(tool_name, tool_input)
        self.console.print(f"[{time_str}] {hook_event}: {tool_name} - {details}")
    
    def _format_tool_details(self, tool_name: str, tool_input: dict) -> str:
        """Format tool-specific details."""
        if tool_name == "TodoWrite":
            todos = tool_input.get('todos', [])
            todo_count = len(todos)
            pending = len([t for t in todos if t.get('status') == 'pending'])
            in_progress = len([t for t in todos if t.get('status') == 'in_progress'])
            completed = len([t for t in todos if t.get('status') == 'completed'])
            return f"Todos: {todo_count} total ({pending} pending, {in_progress} in progress, {completed} completed)"
            
        elif tool_name == "Read":
            file_path = tool_input.get('file_path', 'unknown')
            display_path = self._shorten_path(file_path)
            return f"Reading: {display_path}"
            
        elif tool_name == "Write":
            file_path = tool_input.get('file_path', 'unknown')
            display_path = self._shorten_path(file_path)
            return f"Writing: {display_path}"
            
        elif tool_name in ["Edit", "MultiEdit"]:
            file_path = tool_input.get('file_path', 'unknown')
            display_path = self._shorten_path(file_path)
            return f"Editing: {display_path}"
            
        elif tool_name == "Bash":
            command = tool_input.get('command', 'unknown')
            display_cmd = command[:100].replace('\n', ' ').strip()
            display_cmd = re.sub(r'\s+', ' ', display_cmd)
            return f"Running: {display_cmd}"
            
        elif tool_name == "Task":
            description = tool_input.get('description', 'unknown')
            return description
            
        elif tool_name == "WebSearch":
            query = tool_input.get('query', 'unknown')[:80]
            return f"Searching: {query}"
            
        elif tool_name == "WebFetch":
            url = tool_input.get('url', 'unknown')
            return f"Fetching: {url}"
            
        elif tool_name == "Grep":
            pattern = tool_input.get('pattern', 'unknown')[:50]
            path = tool_input.get('path', '.')
            display_path = self._shorten_path(path)
            return f"Searching for: '{pattern}' in {display_path}"
            
        elif tool_name == "Glob":
            pattern = tool_input.get('pattern', 'unknown')
            path = tool_input.get('path', '.')
            display_path = self._shorten_path(path)
            return f"Finding: '{pattern}' in {display_path}"
            
        elif tool_name == "LS":
            path = tool_input.get('path', 'unknown')
            display_path = self._shorten_path(path)
            return f"Listing: {display_path}"
            
        else:
            return "Executing"
    
    def _shorten_path(self, path: str) -> str:
        """Shorten long paths for display."""
        return path.replace('/workspace/', '') if path.startswith('/workspace/') else path


class LogManager:
    """Manages log operations without exposing database internals."""
    
    def __init__(self, db_path: str = None):
        self._db = LogDatabase(db_path)
        self.console = Console()
    
    def log_message(self, agent_name: str, level: str, message: str, tool_name: str = None, tool_type: str = None):
        """Log a message for an agent by name."""
        self._db.log_message(agent_name, message, level, tool_name, tool_type)
    
    def get_agent_logs(self, agent_name: str) -> List[Dict[str, Any]]:
        """Get all logs for an agent."""
        return self._db.get_logs_by_agent_name(agent_name)
    
    def display_agent_logs(self, agent_name: str, formatter: AgentLogFormatter):
        """Display agent logs using the formatter."""
        logs = self.get_agent_logs(agent_name)
        if not logs:
            self.console.print("[dim]No logs found[/dim]")
            return
        
        self.console.print(f"\n[bold]Agent Logs ({len(logs)} entries):[/bold]\n")
        
        for log in logs:
            timestamp = log['timestamp']
            if log['tool_name']:
                tool_input = json.loads(log['tool_input']) if log['tool_input'] else {}
                details = formatter._format_tool_details(log['tool_name'], tool_input)
                self.console.print(
                    f"[dim]{timestamp}[/dim] [{log['hook_event']}] "
                    f"[bold blue]{log['tool_name']}[/bold blue]: {details}"
                )
            else:
                self.console.print(f"[dim]{timestamp}[/dim] {log['message']}")