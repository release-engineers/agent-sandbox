"""Main Textual application for Agent Sandbox."""

import asyncio
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import DataTable, Input, Static, Header, Footer, Button
from textual.reactive import reactive
from textual.screen import ModalScreen
from rich.text import Text
from rich.syntax import Syntax

from ..agent import AgentManager


class DiffModal(ModalScreen):
    """Modal screen for displaying agent diffs."""
    
    BINDINGS = [
        ("escape", "close", "Close"),
    ]
    
    CSS = """
    DiffModal {
        background: black;
    }
    
    #diff-scroller {
        width: 100%;
        height: 100%;
        background: black;
    }
    
    Footer {
        dock: bottom;
        background: black;
    }
    """
    
    def __init__(self, agent_name: str, diff_content: str):
        super().__init__()
        self.agent_name = agent_name
        self.diff_content = diff_content
    
    def compose(self) -> ComposeResult:
        """Create child widgets."""
        # Use ScrollableContainer for scrollable content
        with ScrollableContainer(id="diff-scroller"):
            # Use Syntax widget for proper diff highlighting with dark background
            syntax = Syntax(self.diff_content, "diff", theme="monokai", line_numbers=False, background_color="black")
            yield Static(syntax)
        
        yield Footer()
    
    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss()


class AgentApp(App):
    """Agent Sandbox TUI application."""
    
    CSS = """
    Screen {
        layout: vertical;
        background: transparent;
    }
    
    Container {
        border: none;
        background: transparent;
    }
    
    DataTable {
        border: none;
        background: transparent;
        width: 100%;
    }
    
    DataTable > .datatable--header {
        background: transparent;
    }
    
    Input {
        border: solid gray;
        dock: bottom;
        background: transparent;
        margin: 0 1;
    }
    
    .command-footer {
        dock: bottom;
        background: transparent;
        color: gray;
        text-align: left;
        height: 1;
        padding: 0 1;
    }
    """
    
    BINDINGS = []
    
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
                    placeholder="",
                    id="goal-input"
                )
        
        from rich.text import Text
        footer_text = Text()
        footer_text.append("  :")
        footer_text.append("q", style="bold")
        footer_text.append("uit  :")
        footer_text.append("l", style="bold") 
        footer_text.append("ogs  :")
        footer_text.append("d", style="bold")
        footer_text.append("iff  :")
        footer_text.append("r", style="bold")
        footer_text.append("estart  :")
        footer_text.append("c", style="bold")
        footer_text.append("leanup")
        yield Static(footer_text, classes="command-footer")
    
    def on_mount(self) -> None:
        """Set up the application."""
        table = self.query_one("#agents-table", DataTable)
        table.add_columns("Status", "Goal", "Started", "Completed")
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.can_focus = False
        
        # Auto-focus the input field
        input_widget = self.query_one("#goal-input", Input)
        input_widget.focus()
        
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
            # Get all agent requests, not just those with diffs
            requests = self.agent_manager.db.list_requests(limit=50)
            # Filter by current project
            self.agents_data = [
                req for req in requests 
                if req.get('project') == self.agent_manager.project_name
            ]
            self.update_table()
        except Exception as e:
            self.notify(f"Error refreshing data: {e}", severity="error")
    
    def update_table(self) -> None:
        """Update the DataTable with current agent data."""
        table = self.query_one("#agents-table", DataTable)
        
        # Save current cursor position
        current_row = table.cursor_row
        
        table.clear()
        
        for agent in self.agents_data:
            # Format timestamps
            started = self.format_timestamp(agent.get('started_at'))
            completed = self.format_timestamp(agent.get('completed_at'))
            
            # Truncate goal if too long
            goal = agent.get('goal', '')
            if len(goal) > 60:
                goal = goal[:59] + "…"
            
            # Style status
            status = agent.get('diff_status', 'UNKNOWN')
            status_text = Text(status)
            if status == 'DONE':
                status_text.stylize("green")
            elif status == 'DONE_AND_NONE':
                status_text.stylize("dim green")
            elif status == 'AGENT_RUNNING':
                status_text.stylize("yellow")
            elif status == 'AGENT_COMPLETE':
                status_text.stylize("blue")
            else:
                status_text.stylize("red")
            
            table.add_row(
                status_text,
                goal,
                started,
                completed
            )
        
        # Restore cursor position if valid
        if current_row is not None and current_row < table.row_count:
            table.move_cursor(row=current_row)
    
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
        input_text = event.value.strip()
        
        # Clear input
        event.input.value = ""
        
        if not input_text:
            # Empty input runs diff command
            self.action_show_diff()
            return
        
        # Check if it's a colon command
        if input_text.startswith(':'):
            self.handle_colon_command(input_text[1:])
        else:
            # Regular goal submission
            self.start_new_agent(input_text)
    
    def handle_colon_command(self, command: str) -> None:
        """Handle colon commands like :q, :l, :d, :c or full words."""
        command = command.lower()
        
        if command in ['q', 'quit']:
            self.exit()
            return
        
        if command in ['l', 'logs']:
            self.action_show_logs()
            return
        
        if command in ['d', 'diff']:
            self.action_show_diff()
            return
        
        if command in ['c', 'cleanup']:
            self.action_cleanup()
            return
        
        if command in ['r', 'restart']:
            self.action_restart()
            return
        
        self.notify(f"Unknown command: :{command}", severity="warning")
    
    def start_new_agent(self, goal: str) -> None:
        """Start a new agent with the given goal."""
        if len(goal) < 10:
            self.notify("Goal too short (min 10 chars).", severity="warning")
            return
        
        # Start agent in background thread
        threading.Thread(
            target=self.start_agent_background,
            args=(goal,),
            daemon=True
        ).start()
        
        # Refresh data to show the new agent
        self.refresh_data()
    
    def start_agent_background(self, goal: str) -> None:
        """Start agent in background thread."""
        try:
            self.agent_manager.start_agent(goal)
            # Refresh data after agent completes
            self.call_from_thread(self.refresh_data)
        except Exception as e:
            # Use call_from_thread to update UI from background thread
            self.call_from_thread(self.notify, f"Agent failed: {e}", severity="error")
            self.call_from_thread(self.refresh_data)
    
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
                    diff_content = self.agent_manager.get_diff(agent_id)
                    if diff_content:
                        # Show the diff in a modal
                        modal = DiffModal(agent_id, diff_content)
                        self.push_screen(modal)
                    else:
                        self.notify(f"No diff available for {agent_id}", severity="warning")
            except IndexError:
                self.notify("No agent selected", severity="warning")
            except Exception as e:
                self.notify(f"Error loading diff: {e}", severity="error")
    
    def action_cleanup(self) -> None:
        """Clean up all agents."""
        try:
            self.agent_manager.cleanup_all()
            self.notify("Cleanup completed", severity="success")
            self.refresh_data()
        except Exception as e:
            self.notify(f"Cleanup failed: {e}", severity="error")
    
    def action_restart(self) -> None:
        """Restart selected agent."""
        table = self.query_one("#agents-table", DataTable)
        if table.cursor_row is not None and self.agents_data:
            agent = self.agents_data[table.cursor_row]
            agent_name = agent.get('agent_name', '')
            
            # Start restart in background thread
            threading.Thread(
                target=self.restart_agent_background,
                args=(agent_name,),
                daemon=True
            ).start()
            
            # Refresh data to show updated status
            self.refresh_data()
    
    def restart_agent_background(self, agent_name: str) -> None:
        """Restart agent in background thread."""
        try:
            self.agent_manager.restart_agent(agent_name)
            # Refresh data after agent completes
            self.call_from_thread(self.refresh_data)
        except Exception as e:
            # Use call_from_thread to update UI from background thread
            self.call_from_thread(self.notify, f"Restart failed: {e}", severity="error")
            self.call_from_thread(self.refresh_data)
    
    
    def on_key(self, event) -> None:
        """Handle key press events."""
        input_widget = self.query_one("#goal-input", Input)
        table = self.query_one("#agents-table", DataTable)
        
        if event.key == "ctrl+c":
            input_widget.value = ""
            input_widget.focus()
            event.prevent_default()
            event.stop()
            return
        
        # Handle up/down arrows when input is empty or starts with : to control table cursor
        if event.key in ["up", "down"] and (not input_widget.value.strip() or input_widget.value.startswith(':')):
            if event.key == "up" and table.cursor_row is not None and table.cursor_row > 0:
                table.move_cursor(row=table.cursor_row - 1)
            elif event.key == "down" and table.cursor_row is not None and table.cursor_row < table.row_count - 1:
                table.move_cursor(row=table.cursor_row + 1)
            elif event.key == "up" and table.cursor_row is None and table.row_count > 0:
                table.move_cursor(row=table.row_count - 1)
            elif event.key == "down" and table.cursor_row is None and table.row_count > 0:
                table.move_cursor(row=0)
            event.prevent_default()
            event.stop()
            return
        
        # Always keep input focused
        if not input_widget.has_focus:
            input_widget.focus()
    
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