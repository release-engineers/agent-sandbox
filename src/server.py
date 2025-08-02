from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path

from .project import ProjectManager
from .agent import AgentManager
from .agent_db import AgentDatabase
from .diff_db import DiffDatabase
from .log_db import LogDatabase


class ProjectRequest(BaseModel):
    git_url: str


class ProjectResponse(BaseModel):
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


class AgentGoal(BaseModel):
    goal: str
    project_id: str  # Can be project short_hash or git_url


class AgentResponse(BaseModel):
    name: str
    goal: str
    project_id: str
    started_at: str
    ended_at: Optional[str]
    status: str
    diff_status: Optional[str]


class DiffResponse(BaseModel):
    content: str
    agent_name: str


class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    tool_name: Optional[str]
    tool_type: Optional[str]


# Global instances
project_manager: Optional[ProjectManager] = None
agent_managers: Dict[str, AgentManager] = {}  # key: project_short_hash


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global project_manager
    db_path = str(Path.home() / ".ags" / "agents.db")
    Path(db_path).parent.mkdir(exist_ok=True)
    project_manager = ProjectManager(db_path)
    yield
    # Shutdown
    agent_managers.clear()
    project_manager = None


app = FastAPI(lifespan=lifespan, title="Agent Process Server", version="2.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_agent_manager(project_short_hash: str) -> AgentManager:
    """Get or create an agent manager for a project."""
    if project_short_hash not in agent_managers:
        # Get project info
        project = project_manager.db.get_project_by_hash(project_short_hash)
        if not project:
            raise ValueError(f"Project {project_short_hash} not found")
        
        # Create agent manager for this project
        db_path = str(Path.home() / ".ags" / "agents.db")
        agent_managers[project_short_hash] = AgentManager(
            db_path=db_path,
            project_path=project["local_path"]
        )
    
    return agent_managers[project_short_hash]


@app.post("/projects", response_model=ProjectResponse)
async def create_or_get_project(project_request: ProjectRequest):
    """Create a new project or get existing one."""
    if not project_manager:
        raise HTTPException(status_code=500, detail="Project manager not initialized")
    
    try:
        project = await asyncio.to_thread(
            project_manager.get_or_clone_project, 
            project_request.git_url
        )
        
        # Add extra info
        info = await asyncio.to_thread(
            project_manager.get_project_info, 
            project["local_path"]
        )
        project.update(info)
        project["exists"] = True
        
        return ProjectResponse(**project)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/projects", response_model=List[ProjectResponse])
async def list_projects():
    """List all projects."""
    if not project_manager:
        raise HTTPException(status_code=500, detail="Project manager not initialized")
    
    projects = await asyncio.to_thread(project_manager.list_projects)
    return [ProjectResponse(**p) for p in projects]


@app.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    """Get a specific project by short hash or id."""
    if not project_manager:
        raise HTTPException(status_code=500, detail="Project manager not initialized")
    
    project = project_manager.db.get_project_by_hash(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    
    # Add extra info
    if Path(project["local_path"]).exists():
        info = await asyncio.to_thread(
            project_manager.get_project_info, 
            project["local_path"]
        )
        project.update(info)
        project["exists"] = True
    else:
        project["exists"] = False
    
    return ProjectResponse(**project)


@app.post("/projects/{project_id}/pull")
async def pull_project(project_id: str):
    """Pull latest changes for a project."""
    if not project_manager:
        raise HTTPException(status_code=500, detail="Project manager not initialized")
    
    try:
        await asyncio.to_thread(project_manager.update_project, project_id)
        return {"message": f"Project {project_id} updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project and its local directory."""
    if not project_manager:
        raise HTTPException(status_code=500, detail="Project manager not initialized")
    
    try:
        await asyncio.to_thread(project_manager.cleanup_project, project_id)
        # Remove agent manager if exists
        if project_id in agent_managers:
            del agent_managers[project_id]
        return {"message": f"Project {project_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/agents", response_model=List[AgentResponse])
async def list_agents(project_id: Optional[str] = None):
    """List all agents, optionally filtered by project."""
    agent_db = AgentDatabase()
    agents = agent_db.get_all_agents()
    
    # Filter by project if specified
    if project_id:
        agents = [a for a in agents if a.get("project_id") == project_id]
    
    response = []
    for agent in agents:
        response.append(AgentResponse(
            name=agent["name"],
            goal=agent["goal"],
            project_id=agent.get("project_id", "unknown"),
            started_at=agent["started_at"],
            ended_at=agent["ended_at"],
            status=agent["status"],
            diff_status=agent.get("diff_status")
        ))
    
    return response


@app.post("/agents", response_model=AgentResponse)
async def create_agent(agent_goal: AgentGoal, background_tasks: BackgroundTasks):
    """Start a new agent with the given goal for a specific project."""
    if not project_manager:
        raise HTTPException(status_code=500, detail="Project manager not initialized")
    
    # Resolve project ID (could be short_hash or git_url)
    project = project_manager.db.get_project_by_hash(agent_goal.project_id)
    if not project:
        # Try as git_url
        project = project_manager.db.get_project_by_url(agent_goal.project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project {agent_goal.project_id} not found")
    
    # Update last accessed
    project_manager.db.update_last_accessed(project["id"])
    
    # Get agent manager for this project
    try:
        agent_manager = get_agent_manager(project["short_hash"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    # Generate unique name with timestamp
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"agent-{project['short_hash']}-{timestamp}"
    
    # Start agent in background
    background_tasks.add_task(
        run_agent_background, 
        name, 
        agent_goal.goal, 
        project["short_hash"],
        agent_manager
    )
    
    # Return immediate response
    agent_db = AgentDatabase()
    agent_db.create_agent(name, agent_goal.goal, project_id=project["short_hash"])
    
    return AgentResponse(
        name=name,
        goal=agent_goal.goal,
        project_id=project["short_hash"],
        started_at=datetime.now().isoformat(),
        ended_at=None,
        status="AGENT_RUNNING",
        diff_status=None
    )


async def run_agent_background(name: str, goal: str, project_id: str, agent_manager: AgentManager):
    """Run agent in background."""
    try:
        # Run the agent
        await asyncio.to_thread(agent_manager.start_agent, goal)
    except Exception as e:
        # Update status on error
        agent_db = AgentDatabase()
        agent_db.update_agent_status(name, "ERROR", str(e))


@app.post("/agents/{agent_name}/restart", response_model=AgentResponse)
async def restart_agent(agent_name: str, background_tasks: BackgroundTasks):
    """Restart an existing agent with the same goal."""
    if not project_manager:
        raise HTTPException(status_code=500, detail="Project manager not initialized")
    
    # Get original agent details
    agent_db = AgentDatabase()
    agents = agent_db.get_all_agents()
    original_agent = next((a for a in agents if a["name"] == agent_name), None)
    
    if not original_agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")
    
    # Get project info
    project_id = original_agent.get("project_id")
    if not project_id:
        raise HTTPException(status_code=400, detail="Original agent has no project ID")
    
    project = project_manager.db.get_project_by_hash(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    
    # Get agent manager
    try:
        agent_manager = get_agent_manager(project["short_hash"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    # Generate new name
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    new_name = f"{agent_name}-restart-{timestamp}"
    
    # Start in background
    background_tasks.add_task(
        run_agent_background, 
        new_name, 
        original_agent["goal"],
        project["short_hash"],
        agent_manager
    )
    
    # Create new agent record
    agent_db.create_agent(new_name, original_agent["goal"], project_id=project["short_hash"])
    
    return AgentResponse(
        name=new_name,
        goal=original_agent["goal"],
        project_id=project["short_hash"],
        started_at=datetime.now().isoformat(),
        ended_at=None,
        status="AGENT_RUNNING",
        diff_status=None
    )


@app.get("/agents/{agent_name}/diff", response_model=DiffResponse)
async def get_agent_diff(agent_name: str):
    """Get the diff for a specific agent."""
    diff_db = DiffDatabase()
    diff = diff_db.get_diff_by_agent_name(agent_name)
    
    if not diff:
        raise HTTPException(status_code=404, detail=f"Diff not found for agent {agent_name}")
    
    return DiffResponse(
        content=diff["content"],
        agent_name=agent_name
    )


@app.get("/agents/{agent_name}/logs", response_model=List[LogEntry])
async def get_agent_logs(agent_name: str):
    """Get logs for a specific agent."""
    log_db = LogDatabase()
    logs = log_db.get_logs_by_agent_name(agent_name)
    
    response = []
    for log in logs:
        response.append(LogEntry(
            timestamp=log["timestamp"],
            level=log["level"],
            message=log["message"],
            tool_name=log.get("tool_name"),
            tool_type=log.get("tool_type")
        ))
    
    return response


@app.delete("/agents")
async def cleanup_all_agents(project_id: Optional[str] = None):
    """Clean up all agents and their resources, optionally for a specific project."""
    if project_id:
        # Cleanup agents for specific project
        if project_id not in agent_managers:
            return {"message": f"No active agents for project {project_id}"}
        
        try:
            agent_manager = agent_managers[project_id]
            await asyncio.to_thread(agent_manager.cleanup_all)
            return {"message": f"All agents for project {project_id} cleaned up successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # Cleanup all agents for all projects
        errors = []
        for project_id, agent_manager in agent_managers.items():
            try:
                await asyncio.to_thread(agent_manager.cleanup_all)
            except Exception as e:
                errors.append(f"Project {project_id}: {str(e)}")
        
        if errors:
            raise HTTPException(status_code=500, detail="; ".join(errors))
        
        return {"message": "All agents cleaned up successfully"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "agent-process-server", "version": "2.0.0"}