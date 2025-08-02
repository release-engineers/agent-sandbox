"""Project management module for handling Git repositories."""

import os
import subprocess
import hashlib
from pathlib import Path
from typing import Optional, Dict

from .projects_db import ProjectDatabase


class ProjectManager:
    """Manages Git projects for agent operations."""
    
    def __init__(self, db_path: str = None):
        self.db = ProjectDatabase(db_path)
        self.projects_dir = Path.home() / ".ags" / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_short_hash(self, git_url: str) -> str:
        """Generate a short hash from the Git URL."""
        # Create a hash from the URL
        url_hash = hashlib.sha256(git_url.encode()).hexdigest()
        # Return first 8 characters
        return url_hash[:8]
    
    def get_or_clone_project(self, git_url: str) -> Dict:
        """Get existing project or clone if it doesn't exist."""
        # Check if project already exists
        existing = self.db.get_project_by_url(git_url)
        if existing:
            # Update last accessed time
            self.db.update_last_accessed(existing["id"])
            
            # Verify the directory still exists
            if Path(existing["local_path"]).exists():
                return existing
            else:
                # Directory was deleted, need to re-clone
                self.db.delete_project(existing["id"])
        
        # Clone the project
        return self._clone_project(git_url)
    
    def _clone_project(self, git_url: str) -> Dict:
        """Clone a Git repository."""
        short_hash = self._generate_short_hash(git_url)
        project_path = self.projects_dir / f"project-{short_hash}"
        
        # If directory exists but not in DB, remove it
        if project_path.exists():
            import shutil
            shutil.rmtree(project_path)
        
        # Clone the repository
        try:
            subprocess.run(
                ["git", "clone", git_url, str(project_path)],
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to clone repository: {e.stderr}")
        
        # Create database record
        project_id = self.db.create_project(
            git_url=git_url,
            short_hash=short_hash,
            local_path=str(project_path)
        )
        
        return self.db.get_project_by_hash(short_hash)
    
    def update_project(self, project_id: int) -> None:
        """Pull latest changes for a project."""
        project = self.db.get_project_by_hash(str(project_id))
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        project_path = Path(project["local_path"])
        if not project_path.exists():
            raise ValueError(f"Project directory {project_path} does not exist")
        
        # Pull latest changes
        try:
            subprocess.run(
                ["git", "pull"],
                cwd=str(project_path),
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to update repository: {e.stderr}")
        
        # Update last accessed time
        self.db.update_last_accessed(project["id"])
    
    def get_project_info(self, project_path: str) -> Dict:
        """Get information about a Git project."""
        path = Path(project_path)
        
        if not path.exists():
            raise ValueError(f"Project path {project_path} does not exist")
        
        # Get current branch
        try:
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(path),
                check=True,
                capture_output=True,
                text=True
            )
            current_branch = branch_result.stdout.strip()
        except:
            current_branch = "unknown"
        
        # Get remote URL
        try:
            remote_result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=str(path),
                check=True,
                capture_output=True,
                text=True
            )
            remote_url = remote_result.stdout.strip()
        except:
            remote_url = "unknown"
        
        # Get latest commit
        try:
            commit_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(path),
                check=True,
                capture_output=True,
                text=True
            )
            latest_commit = commit_result.stdout.strip()[:7]
        except:
            latest_commit = "unknown"
        
        return {
            "path": str(path),
            "branch": current_branch,
            "remote_url": remote_url,
            "latest_commit": latest_commit
        }
    
    def list_projects(self) -> list:
        """List all projects with their status."""
        projects = self.db.list_projects()
        
        # Add additional info for each project
        for project in projects:
            path = Path(project["local_path"])
            project["exists"] = path.exists()
            
            if project["exists"]:
                try:
                    info = self.get_project_info(project["local_path"])
                    project.update(info)
                except:
                    project["branch"] = "error"
                    project["latest_commit"] = "error"
        
        return projects
    
    def cleanup_project(self, project_id: int) -> None:
        """Remove a project and its directory."""
        project = self.db.get_project_by_hash(str(project_id))
        if not project:
            return
        
        # Remove directory if it exists
        project_path = Path(project["local_path"])
        if project_path.exists():
            import shutil
            shutil.rmtree(project_path)
        
        # Remove from database
        self.db.delete_project(project["id"])