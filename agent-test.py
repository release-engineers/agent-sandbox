#!/usr/bin/env python3
"""
Agent Sandbox Test Script

Tests the agent sandbox system by running a simple task in the example directory.
"""

import subprocess
import sys
import time
import os
from pathlib import Path


def run_test():
    """Run a basic test of the agent sandbox system."""
    # Navigate to example directory
    example_dir = Path(__file__).parent / "example"
    if not example_dir.exists():
        print(f"Error: Example directory not found at {example_dir}")
        return 1
    
    os.chdir(example_dir)
    
    # Define test agent name and simple goal
    agent_name = "test-agent"
    test_goal = "Add a hello world function to hello.py"
    
    print(f"Starting agent sandbox test...")
    print(f"Agent: {agent_name}")
    print(f"Goal: {test_goal}")
    print()
    
    try:
        # Start the agent
        print("Starting agent...")
        cmd = ["../agent.py", "start", agent_name, test_goal]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error starting agent:")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr}")
            return 1
        
        print("Agent completed successfully!")
        print()
        
        # List agents to verify
        print("Listing agents...")
        cmd = ["../agent.py", "list"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
        
        # Check if the agent branch exists
        cmd = ["git", "branch", "-r"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if f"agent--{agent_name}" in result.stdout:
            print(f"✓ Agent branch 'agent--{agent_name}' created successfully")
        else:
            print(f"✗ Agent branch 'agent--{agent_name}' not found")
            return 1
        
        print()
        print("Test completed successfully!")
        return 0
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(run_test())