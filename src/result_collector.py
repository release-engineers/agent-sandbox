"""Result collection framework for agent execution phases."""
import os
import subprocess
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, List, Dict, Any
from pathlib import Path


def get_target_files_for_phase(phase: str) -> Optional[List[str]]:
    """Get target files for a given phase."""
    phase_to_files = {
        'requirements': ['FUNCTIONAL_REQUIREMENTS.md'],
        'technical_spec': ['TECHNICAL_SPECIFICATION.md'],
        'implementation_plan': ['IMPLEMENTATION_PLAN.md']
    }
    return phase_to_files.get(phase)


class ResultType(Enum):
    """Types of results that can be collected."""
    GIT_DIFF = "git_diff"
    DOCUMENT = "document"
    QUALITY = "quality"


class AgentPhase(Enum):
    """Execution phases for agents."""
    REQUIREMENTS = "requirements"
    TECHNICAL_SPEC = "technical_spec"
    IMPLEMENTATION_PLAN = "implementation_plan"
    IMPLEMENTATION = "implementation"
    QUALITY_CHECK = "quality_check"


class ResultCollector(ABC):
    """Base class for result collectors."""
    
    @abstractmethod
    def collect(self, workspace_path: str, target_files: Optional[List[str]] = None) -> str:
        """Collect results from the workspace.
        
        Args:
            workspace_path: Path to the agent's workspace
            target_files: Optional list of specific files/patterns to collect
            
        Returns:
            The collected result as a string
        """
        pass


class GitDiffCollector(ResultCollector):
    """Collects git diff from the workspace."""
    
    def collect(self, workspace_path: str, target_files: Optional[List[str]] = None) -> str:
        """Generate git diff for the workspace or specific files."""
        # Stage changes
        if target_files:
            # Stage specific files
            for pattern in target_files:
                subprocess.run(["git", "add", pattern], 
                             cwd=workspace_path, 
                             capture_output=True)
        else:
            # Stage all changes
            subprocess.run(["git", "add", "."], 
                         cwd=workspace_path, 
                         capture_output=True)
        
        # Get the diff
        result = subprocess.run(
            ["git", "diff", "--cached"],
            cwd=workspace_path,
            capture_output=True,
            text=True
        )
        
        return result.stdout


class DocumentCollector(ResultCollector):
    """Collects document files from the workspace."""
    
    def collect(self, workspace_path: str, target_files: Optional[List[str]] = None) -> str:
        """Read and concatenate document files."""
        workspace = Path(workspace_path)
        content_parts = []
        
        if target_files:
            # Collect specific files
            for file_pattern in target_files:
                # Handle both exact paths and glob patterns
                if '*' in file_pattern:
                    files = list(workspace.glob(file_pattern))
                    if not files:
                        content_parts.append(f"=== {file_pattern} ===\n")
                        content_parts.append(f"No files matching pattern '{file_pattern}' were found.\n")
                else:
                    file_path = workspace / file_pattern
                    if file_path.exists():
                        content_parts.append(f"=== {file_path.relative_to(workspace)} ===\n")
                        try:
                            content_parts.append(file_path.read_text() + "\n")
                        except Exception as e:
                            content_parts.append(f"Error reading file: {e}\n")
                    else:
                        content_parts.append(f"=== {file_pattern} ===\n")
                        content_parts.append(f"Target file '{file_pattern}' was not created by the agent.\n")
        else:
            # Default: collect all markdown files
            for md_file in workspace.rglob("*.md"):
                content_parts.append(f"=== {md_file.relative_to(workspace)} ===\n")
                try:
                    content_parts.append(md_file.read_text() + "\n")
                except Exception as e:
                    content_parts.append(f"Error reading file: {e}\n")
        
        return "\n".join(content_parts)


class QualityScorer:
    """Dummy quality scorer that always returns 100."""
    
    def score(self, workspace_path: str, diff_content: Optional[str] = None) -> Dict[str, Any]:
        """Calculate quality score for the workspace or diff.
        
        Args:
            workspace_path: Path to the agent's workspace
            diff_content: Optional diff content to analyze
            
        Returns:
            Dictionary with quality metrics
        """
        return {
            "quality_score": 100,
            "tests_passed": True,
            "lint_errors": 0,
            "complexity": "low",
            "coverage": 100
        }


def get_collector(result_type: ResultType) -> ResultCollector:
    """Factory function to get the appropriate collector."""
    collectors = {
        ResultType.GIT_DIFF: GitDiffCollector(),
        ResultType.DOCUMENT: DocumentCollector(),
    }
    
    collector = collectors.get(result_type)
    if not collector:
        raise ValueError(f"No collector available for result type: {result_type}")
    
    return collector