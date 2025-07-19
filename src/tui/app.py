"""Main Textual application for Agent Sandbox."""

import asyncio
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import DataTable, Input, Static, Header, Footer
from textual.reactive import reactive
from rich.text import Text

from ..agent import AgentManager


class AgentApp(App):
    """Agent Sandbox TUI application."""
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    Container {
        border: none;
    }
    
    DataTable {
        border: none;
    }
    
    Input {
        border: none;
        dock: bottom;
    }
    
    Footer {
        dock: bottom;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("l", "show_logs", "Logs"),
        ("d", "show_diff", "Diff"),
        ("c", "cleanup", "Cleanup"),
        ("r", "refresh", "Refresh"),
    ]
    
    TITLE = "Agent Sandbox"
    
    agents_data = reactive([])
    
    def __init__(self):
        super().__init__()
        self.db_path = str(Path.home() / ".ags" / "agents.db")
        Path(self.db_path).parent.mkdir(exist_ok=True)
        self.agent_manager = AgentManager(self.db_path)
        self.refresh_timer = None
        
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        with Container(classes="main-container"):
            with Container(classes="table-container"):
                yield DataTable(id="agents-table")
            
            with Container(classes="input-container"):
                yield Input(
                    placeholder="Enter agent goal and press Enter to start...",
                    id="goal-input"
                )
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Set up the application."""
        table = self.query_one("#agents-table", DataTable)
        table.add_columns("Agent ID", "Goal", "Status", "Started", "Completed")
        table.cursor_type = "row"
        table.zebra_stripes = True
        
        self.refresh_data()
        self.start_refresh_timer()
    
    def start_refresh_timer(self) -> None:
        """Start periodic data refresh."""
        if self.refresh_timer:
            self.refresh_timer.stop()
        
        # Use set_interval for repeating timer
        self.refresh_timer = self.set_interval(2.0, self.refresh_data)
    
    def refresh_data(self) -> None:
        """Refresh agent data from database."""
        try:
            requests = self.agent_manager.diff_manager.list_diffs_by_project(
                self.agent_manager.project_name, limit=50
            )
            self.agents_data = requests
            self.update_table()
        except Exception as e:
            self.notify(f"Error refreshing data: {e}", severity="error")
    
    def update_table(self) -> None:
        """Update the DataTable with current agent data."""
        table = self.query_one("#agents-table", DataTable)
        table.clear()
        
        for agent in self.agents_data:
            # Format timestamps
            started = self.format_timestamp(agent.get('started_at'))
            completed = self.format_timestamp(agent.get('completed_at'))
            
            # Truncate goal if too long
            goal = agent.get('goal', '')
            if len(goal) > 50:
                goal = goal[:47] + "..."
            
            # Style status
            status = agent.get('diff_status', 'UNKNOWN')
            status_text = Text(status)
            if status == 'DONE':
                status_text.stylize("green")
            elif status == 'AGENT_RUNNING':
                status_text.stylize("yellow")
            elif status == 'AGENT_COMPLETE':
                status_text.stylize("blue")
            else:
                status_text.stylize("red")
            
            table.add_row(
                agent.get('agent_name', ''),
                goal,
                status_text,
                started,
                completed
            )
    
    def format_timestamp(self, timestamp: str) -> str:
        """Format timestamp for display."""
        if not timestamp:
            return "-"
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime("%m/%d %H:%M")
        except:
            return timestamp[:10] if timestamp else "-"
    
    @on(Input.Submitted, "#goal-input")
    def on_goal_submitted(self, event: Input.Submitted) -> None:
        """Handle goal input submission."""
        goal = event.value.strip()
        if not goal:
            self.notify("Please enter a goal", severity="warning")
            return
        
        # Clear input
        event.input.value = ""
        
        # Start agent in background thread
        threading.Thread(
            target=self.start_agent_background,
            args=(goal,),
            daemon=True
        ).start()
        
        self.notify(f"Starting agent with goal: {goal}", timeout=3)
    
    def start_agent_background(self, goal: str) -> None:
        """Start agent in background thread."""
        try:
            self.agent_manager.start_agent(goal)
        except Exception as e:
            # Use call_from_thread to update UI from background thread
            self.call_from_thread(self.notify, f"Agent failed: {e}", severity="error")
    
    def action_show_logs(self) -> None:
        """Show logs for selected agent."""
        table = self.query_one("#agents-table", DataTable)
        if table.cursor_row is not None and self.agents_data:
            try:
                agent = self.agents_data[table.cursor_row]
                agent_id = agent.get('agent_name', '')
                if agent_id:
                    # For now, show a notification. Later we can add a log viewer
                    self.notify(f"Logs for {agent_id} (feature coming soon)", timeout=3)
            except IndexError:
                self.notify("No agent selected", severity="warning")
    
    def action_show_diff(self) -> None:
        """Show diff for selected agent."""
        table = self.query_one("#agents-table", DataTable)
        if table.cursor_row is not None and self.agents_data:
            try:
                agent = self.agents_data[table.cursor_row]
                agent_id = agent.get('agent_name', '')
                if agent_id:
                    # For now, show a notification. Later we can add a diff viewer
                    self.notify(f"Diff for {agent_id} (feature coming soon)", timeout=3)
            except IndexError:
                self.notify("No agent selected", severity="warning")
    
    def action_cleanup(self) -> None:
        """Clean up all agents."""
        try:
            self.agent_manager.cleanup_all()
            self.notify("Cleanup completed", severity="success")
            self.refresh_data()
        except Exception as e:
            self.notify(f"Cleanup failed: {e}", severity="error")
    
    def action_refresh(self) -> None:
        """Manually refresh data."""
        self.refresh_data()
        self.notify("Data refreshed", timeout=1)
    
    def on_unmount(self) -> None:
        """Clean up when app closes."""
        if self.refresh_timer:
            self.refresh_timer.stop()


def run_tui():
    """Run the Textual TUI application."""
    app = AgentApp()
    app.run()


if __name__ == "__main__":
    run_tui()