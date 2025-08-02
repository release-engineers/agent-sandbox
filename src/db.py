#!/usr/bin/env python3
"""Core database package for agent process tracking."""

import sqlite3
import threading
from pathlib import Path
from typing import Optional


class Database:
    """Base database class for SQLite operations."""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(Path.home() / ".ags" / "agents.db")
            Path(db_path).parent.mkdir(exist_ok=True)
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema. Override in subclasses."""
        pass
    
    def _get_connection(self):
        """Get a database connection."""
        return sqlite3.connect(self.db_path)
    
    def execute(self, query: str, params: tuple = (), fetch: bool = False):
        """Execute a query with proper locking."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                if fetch:
                    return cursor.fetchall()
                conn.commit()
                return cursor.lastrowid
    
    def execute_many(self, query: str, params_list: list):
        """Execute a query multiple times with different parameters."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.executemany(query, params_list)
                conn.commit()
    
    def fetch_one(self, query: str, params: tuple = ()) -> Optional[dict]:
        """Fetch a single row as a dictionary."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                result = cursor.fetchone()
                return dict(result) if result else None
    
    def fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        """Fetch all rows as a list of dictionaries."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]