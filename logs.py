#!/usr/bin/env python3
"""Logging utilities for the agent process manager."""

import json
import re
from datetime import datetime
from rich.console import Console


class AgentLogFormatter:
    """Formats agent logs with rich styling."""
    
    def __init__(self, console: Console):
        self.console = console
        
        self.tool_colors = {
            # File operations
            'Read': 'blue',
            'Write': 'blue', 
            'Edit': 'blue',
            'MultiEdit': 'blue',
            'LS': 'blue',
            
            # Search operations
            'Grep': 'cyan',
            'Glob': 'cyan',
            'WebSearch': 'cyan',
            'WebFetch': 'cyan',
            
            # Execution
            'Bash': 'yellow',
            
            # Task management
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
        # Skip empty lines
        if not line.strip():
            return
            
        # Try to parse as JSON first (new format)
        try:
            log_data = json.loads(line.strip())
            self._format_json_log(log_data)
            return
        except json.JSONDecodeError:
            pass
            
        # Handle legacy [LOG] prefixed lines from hooks
        if line.startswith('[LOG]'):
            self._format_legacy_log(line)
        else:
            # Regular output from the agent
            self.console.print(line)
    
    def _format_json_log(self, log_data: dict):
        """Format JSON log data."""
        timestamp = log_data.get('timestamp', '')
        tool_name = log_data.get('tool_name', 'unknown')
        hook_event = log_data.get('hook_event_name', 'unknown')
        tool_input = log_data.get('tool_input', {})
        
        # Format timestamp
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = dt.strftime('%H:%M:%S')
        except:
            time_str = timestamp[:8] if len(timestamp) >= 8 else timestamp
        
        # Get color and icon for tool
        color = self.tool_colors.get(tool_name, 'white')
        icon = self.tool_icons.get(tool_name, '🔧')
        
        # Format details based on tool type
        details = self._format_tool_details(tool_name, tool_input)
        
        # Print formatted output
        self.console.print(
            f"[dim]{time_str}[/dim] {icon} [{color}]{tool_name}[/{color}] {details}"
        )
    
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
            # Truncate and clean up command for display
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
    
    def _format_legacy_log(self, line: str):
        """Format legacy [LOG] prefixed lines (for backward compatibility)."""
        # Remove the [LOG] prefix
        line = line[5:].strip()
        
        # Parse timestamp if present
        timestamp_match = re.match(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\]\s*(.*)', line)
        if timestamp_match:
            timestamp, content = timestamp_match.groups()
            
            # Parse the hook event and tool
            event_match = re.match(r'(\w+):\s*(\w+)\s*-\s*(.*)', content)
            if event_match:
                event, tool, details = event_match.groups()
                
                color = self.tool_colors.get(tool, 'white')
                icon = self.tool_icons.get(tool, '🔧')
                
                # Format the output
                time_str = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f').strftime('%H:%M:%S')
                self.console.print(
                    f"[dim]{time_str}[/dim] {icon} [{color}]{tool}[/{color}] {details}"
                )
            else:
                # Fallback formatting
                self.console.print(f"[dim]{timestamp}[/dim] {content}")
        else:
            # No timestamp, just print the content
            self.console.print(f"[yellow]{line}[/yellow]") 