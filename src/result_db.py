"""Database operations for agent results."""
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from .db import Database


class ResultDatabase(Database):
    """Database for storing agent execution results."""
    
    def __init__(self, db_path: str = None):
        super().__init__(db_path)
        self._create_tables()
    
    def _create_tables(self):
        """Create the results table if it doesn't exist."""
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS agent_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    result_type TEXT NOT NULL,
                    target_files TEXT,
                    content TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(agent_name, phase)
                )
            ''')
            conn.commit()
    
    def save_result(self, agent_name: str, phase: str, result_type: str, 
                   content: str, target_files: Optional[List[str]] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> int:
        """Save or update a result for an agent phase."""
        with self._get_connection() as conn:
            target_files_json = json.dumps(target_files) if target_files else None
            metadata_json = json.dumps(metadata) if metadata else None
            
            cursor = conn.execute('''
                INSERT OR REPLACE INTO agent_results 
                (agent_name, phase, result_type, target_files, content, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (agent_name, phase, result_type, target_files_json, content, metadata_json))
            
            conn.commit()
            return cursor.lastrowid
    
    def get_result(self, agent_name: str, phase: str) -> Optional[Dict[str, Any]]:
        """Get a specific result by agent name and phase."""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                SELECT id, agent_name, phase, result_type, target_files, 
                       content, metadata, created_at
                FROM agent_results
                WHERE agent_name = ? AND phase = ?
            ''', (agent_name, phase))
            
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'agent_name': row[1],
                    'phase': row[2],
                    'result_type': row[3],
                    'target_files': json.loads(row[4]) if row[4] else None,
                    'content': row[5],
                    'metadata': json.loads(row[6]) if row[6] else None,
                    'created_at': row[7]
                }
            return None
    
    def get_all_results(self, agent_name: str) -> List[Dict[str, Any]]:
        """Get all results for an agent."""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                SELECT id, agent_name, phase, result_type, target_files, 
                       content, metadata, created_at
                FROM agent_results
                WHERE agent_name = ?
                ORDER BY created_at
            ''', (agent_name,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row[0],
                    'agent_name': row[1],
                    'phase': row[2],
                    'result_type': row[3],
                    'target_files': json.loads(row[4]) if row[4] else None,
                    'content': row[5],
                    'metadata': json.loads(row[6]) if row[6] else None,
                    'created_at': row[7]
                })
            return results
    
    def delete_agent_results(self, agent_name: str):
        """Delete all results for an agent."""
        with self._get_connection() as conn:
            conn.execute('DELETE FROM agent_results WHERE agent_name = ?', (agent_name,))
            conn.commit()