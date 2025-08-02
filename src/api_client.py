import requests
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Project:
    id: int
    git_url: str
    short_hash: str
    local_path: str
    created_at: str
    last_accessed: str
    status: str
    exists: Optional[bool] = None
    branch: Optional[str] = None
    latest_commit: Optional[str] = None


@dataclass
class Agent:
    name: str
    goal: str
    project_id: str
    started_at: str
    ended_at: Optional[str]
    status: str
    diff_status: Optional[str]


@dataclass
class Diff:
    content: str
    agent_name: str


@dataclass
class LogEntry:
    timestamp: str
    level: str
    message: str
    tool_name: Optional[str]
    tool_type: Optional[str]


class AgentAPIClient:
    """Client for interacting with the Agent Process Server."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
    
    # Project operations
    def create_or_get_project(self, git_url: str) -> Project:
        """Create a new project or get existing one."""
        response = self.session.post(
            f"{self.base_url}/projects",
            json={"git_url": git_url}
        )
        response.raise_for_status()
        
        data = response.json()
        return Project(**data)
    
    def list_projects(self) -> List[Project]:
        """List all projects."""
        response = self.session.get(f"{self.base_url}/projects")
        response.raise_for_status()
        
        return [Project(**p) for p in response.json()]
    
    def get_project(self, project_id: str) -> Project:
        """Get a specific project by ID or short hash."""
        response = self.session.get(f"{self.base_url}/projects/{project_id}")
        response.raise_for_status()
        
        return Project(**response.json())
    
    def pull_project(self, project_id: str) -> Dict[str, str]:
        """Pull latest changes for a project."""
        response = self.session.post(f"{self.base_url}/projects/{project_id}/pull")
        response.raise_for_status()
        return response.json()
    
    def delete_project(self, project_id: str) -> Dict[str, str]:
        """Delete a project and its local directory."""
        response = self.session.delete(f"{self.base_url}/projects/{project_id}")
        response.raise_for_status()
        return response.json()
    
    # Agent operations
    def list_agents(self, project_id: Optional[str] = None) -> List[Agent]:
        """Get list of all agents, optionally filtered by project."""
        params = {}
        if project_id:
            params["project_id"] = project_id
        
        response = self.session.get(f"{self.base_url}/agents", params=params)
        response.raise_for_status()
        
        agents = []
        for data in response.json():
            agents.append(Agent(
                name=data["name"],
                goal=data["goal"],
                project_id=data["project_id"],
                started_at=data["started_at"],
                ended_at=data["ended_at"],
                status=data["status"],
                diff_status=data["diff_status"]
            ))
        return agents
    
    def create_agent(self, goal: str, project_id: str) -> Agent:
        """Create a new agent with the given goal for a specific project."""
        response = self.session.post(
            f"{self.base_url}/agents",
            json={"goal": goal, "project_id": project_id}
        )
        response.raise_for_status()
        
        data = response.json()
        return Agent(
            name=data["name"],
            goal=data["goal"],
            project_id=data["project_id"],
            started_at=data["started_at"],
            ended_at=data["ended_at"],
            status=data["status"],
            diff_status=data["diff_status"]
        )
    
    def restart_agent(self, agent_name: str) -> Agent:
        """Restart an existing agent."""
        response = self.session.post(f"{self.base_url}/agents/{agent_name}/restart")
        response.raise_for_status()
        
        data = response.json()
        return Agent(
            name=data["name"],
            goal=data["goal"],
            project_id=data["project_id"],
            started_at=data["started_at"],
            ended_at=data["ended_at"],
            status=data["status"],
            diff_status=data["diff_status"]
        )
    
    def get_agent_diff(self, agent_name: str) -> Diff:
        """Get diff for a specific agent."""
        response = self.session.get(f"{self.base_url}/agents/{agent_name}/diff")
        response.raise_for_status()
        
        data = response.json()
        return Diff(
            content=data["content"],
            agent_name=data["agent_name"]
        )
    
    def get_agent_logs(self, agent_name: str) -> List[LogEntry]:
        """Get logs for a specific agent."""
        response = self.session.get(f"{self.base_url}/agents/{agent_name}/logs")
        response.raise_for_status()
        
        logs = []
        for data in response.json():
            logs.append(LogEntry(
                timestamp=data["timestamp"],
                level=data["level"],
                message=data["message"],
                tool_name=data.get("tool_name"),
                tool_type=data.get("tool_type")
            ))
        return logs
    
    def cleanup_all_agents(self, project_id: Optional[str] = None) -> Dict[str, str]:
        """Clean up all agents and resources, optionally for a specific project."""
        params = {}
        if project_id:
            params["project_id"] = project_id
        
        response = self.session.delete(f"{self.base_url}/agents", params=params)
        response.raise_for_status()
        return response.json()
    
    def health_check(self) -> bool:
        """Check if the server is healthy."""
        try:
            response = self.session.get(f"{self.base_url}/health")
            return response.status_code == 200
        except:
            return False
    
    def close(self):
        """Close the session."""
        self.session.close()