"""Database module for managing projects."""

import sqlite3
from typing import List, Dict, Optional
from datetime import datetime
from .db import Database


class ProjectDatabase(Database):
    """Manages project records in the database."""
    
    def __init__(self, db_path: str = None):
        super().__init__(db_path)
        self._init_tables()
    
    def _init_tables(self):
        """Initialize project tables."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    git_url TEXT NOT NULL UNIQUE,
                    short_hash TEXT NOT NULL UNIQUE,
                    local_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    status TEXT DEFAULT 'active'
                )
            """)
            conn.commit()
    
    def create_project(self, git_url: str, short_hash: str, local_path: str) -> int:
        """Create a new project record."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO projects (git_url, short_hash, local_path, created_at, last_accessed)
                VALUES (?, ?, ?, ?, ?)
            """, (git_url, short_hash, local_path, now, now))
            conn.commit()
            return cursor.lastrowid
    
    def get_project_by_url(self, git_url: str) -> Optional[Dict]:
        """Get project by Git URL."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM projects WHERE git_url = ?
            """, (git_url,))
            row = cursor.fetchone()
            
            if row:
                return {
                    "id": row[0],
                    "git_url": row[1],
                    "short_hash": row[2],
                    "local_path": row[3],
                    "created_at": row[4],
                    "last_accessed": row[5],
                    "status": row[6]
                }
            return None
    
    def get_project_by_hash(self, short_hash: str) -> Optional[Dict]:
        """Get project by short hash."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM projects WHERE short_hash = ?
            """, (short_hash,))
            row = cursor.fetchone()
            
            if row:
                return {
                    "id": row[0],
                    "git_url": row[1],
                    "short_hash": row[2],
                    "local_path": row[3],
                    "created_at": row[4],
                    "last_accessed": row[5],
                    "status": row[6]
                }
            return None
    
    def update_last_accessed(self, project_id: int):
        """Update the last accessed timestamp for a project."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE projects SET last_accessed = ? WHERE id = ?
            """, (now, project_id))
            conn.commit()
    
    def list_projects(self) -> List[Dict]:
        """List all projects."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM projects ORDER BY last_accessed DESC
            """)
            
            projects = []
            for row in cursor.fetchall():
                projects.append({
                    "id": row[0],
                    "git_url": row[1],
                    "short_hash": row[2],
                    "local_path": row[3],
                    "created_at": row[4],
                    "last_accessed": row[5],
                    "status": row[6]
                })
            return projects
    
    def delete_project(self, project_id: int):
        """Delete a project record."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()