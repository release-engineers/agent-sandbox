#!/usr/bin/env bash
# inputs prompted:

# ?. get the project (default: git repo of the current directory)

# ?. if no CLAUDE.md exists, create one with instructions for Claude (externally, ensure it is .gitignored)

# ?. get a goal from the user
# ?. set up a git worktree of the project
# https://docs.anthropic.com/en/docs/claude-code/common-workflows#run-parallel-claude-code-sessions-with-git-worktrees


# ?. modify the docker container to include any new tools

# ?. pre tool use
#   - validate dependency whitelist
#   - validate technology whitelist

# ?. run claude code in the background, given the goal
# ?. allow it to asynchronously ask for more information on open questions


# quality controls:
# Vulnerabilities	Count by Severity
# Application Performance	Seconds by Feature
# Application Build Time	Seconds by Component
# Code Quality	Findings by Severity
# Code Change Size	Lines by File Type
# Dependencies	Count and Size
# Application Requirements	RAM and CPU use
# Unit Test Findings	Count
# Integration Test Findings	Count
# End  to End Test Findings	Count
# Application Startup Time	Seconds
# Secret Detection	Count
# Coverage	Percentage of Changed Lines
# Mutation Coverage	Percentage of Changed Lines
# Deployment Speed	Seconds
# API Changes Count by Type
# Documentation	Count by Feature
# Features Flagged	Count by Feature
# Network Interactions	Delta by Endpoint and Allow Type
