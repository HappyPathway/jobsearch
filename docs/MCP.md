# Job Search Automation Platform - MCP Server Design

## Overview

This document outlines the design for a Model Context Protocol (MCP) server implementation for the Job Search Automation Platform. The MCP server will enable AI models (like GitHub Copilot) to interact directly with your job search platform's functionality, providing a conversational and natural language interface.

## What is MCP?

Model Context Protocol (MCP) is an open standard that enables AI models to interact with external tools and services through a unified interface. In our implementation:

- **MCP clients** (like VS Code with Copilot) will connect to our MCP server to perform job search tasks
- **Our MCP server** will expose job search tools (search, documents, strategy generation) through the protocol
- **The core platform** will continue to function as the backend, with the MCP server acting as a new interface layer

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  VS Code with   │     │                  │     │ Job Search      │
│  Copilot or     │◄───►│   MCP Server     │◄───►│ Automation      │
│  other MCP      │     │                  │     │ Platform        │
│  clients        │     │                  │     │ (Existing Code) │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## Project Structure

```
jobsearch/
├── mcp_server/
│   ├── __init__.py
│   ├── __main__.py         # Entry point for the MCP server
│   ├── server.py           # Main server implementation
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── job_tools.py    # Job search and application tools
│   │   ├── profile_tools.py # Profile management tools
│   │   ├── document_tools.py # Document generation tools
│   │   ├── strategy_tools.py # Strategy generation tools
│   │   └── web_presence_tools.py # GitHub Pages and Medium tools
│   └── adapters/          # Adapters to existing functionality
│       ├── __init__.py
│       ├── database.py    # SQLite/GCS database adapter
│       └── gcs_adapter.py # Google Cloud Storage adapter
└── pyproject.toml         # Updated with MCP server dependencies
```

## MCP Tools Implementation

The MCP server will expose the following tools that map to your platform's core functionality:

### 1. Job Search Tools

```python
# Tool definitions for job-related functionality
{
    "name": "search_jobs",
    "description": "Search for jobs based on keywords and criteria",
    "inputSchema": {
        "type": "object",
        "required": ["keywords"],
        "properties": {
            "keywords": {
                "type": "string",
                "description": "Job search keywords (e.g., 'cloud architect')"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of jobs to return",
                "default": 10
            }
        },
    }
}
```

### 2. Profile Management Tools

```python
# Tool definitions for profile management
{
    "name": "get_profile_summary",
    "description": "Get a summary of the user's professional profile",
    "inputSchema": {
        "type": "object",
        "properties": {
            "include_skills": {
                "type": "boolean",
                "description": "Include skills in the summary",
                "default": true
            },
            "include_experiences": {
                "type": "boolean",
                "description": "Include experiences in the summary",
                "default": true
            }
        }
    }
}
```

### 3. Document Generation Tools

```python
# Tool definitions for document generation
{
    "name": "generate_documents",
    "description": "Generate tailored resume and cover letter for a specific job",
    "inputSchema": {
        "type": "object",
        "required": ["job_id"],
        "properties": {
            "job_id": {
                "type": "integer",
                "description": "ID of the job to generate documents for"
            },
            "use_visual_resume": {
                "type": "boolean",
                "description": "Generate visual resume in addition to ATS-friendly version",
                "default": true
            }
        }
    }
}
```

### 4. Strategy Generation Tools

```python
# Tool definitions for strategy generation
{
    "name": "generate_strategy",
    "description": "Generate a job search strategy based on profile and job matches",
    "inputSchema": {
        "type": "object",
        "properties": {
            "job_limit": {
                "type": "integer",
                "description": "Maximum number of jobs to include in the strategy",
                "default": 10
            },
            "include_weekly_focus": {
                "type": "boolean",
                "description": "Include weekly focus areas in the strategy",
                "default": true
            }
        }
    }
}
```

## Implementation Details

### Server Implementation

The main server implementation will use the Python MCP SDK to:
1. Define available tools
2. Handle tool invocations
3. Return appropriate responses

```python
@app.list_tools()
async def list_tools() -> list[types.Tool]:
    """Define the set of tools available through the MCP server"""
    return [
        # Job search tools
        types.Tool(
            name="search_jobs",
            description="Search for jobs based on keywords and criteria",
            inputSchema={
                "type": "object",
                "required": ["keywords"],
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "Job search keywords (e.g., 'cloud architect')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of jobs to return",
                        "default": 10
                    }
                },
            },
        ),
        # Additional tools defined here...
    ]
```

### Tool Invocation Handler

```python
@app.call_tool()
async def call_tool(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool invocation based on the tool name"""
    
    # Route the tool call to the appropriate handler
    if name == "search_jobs":
        return await job_tools.search_jobs_tool(arguments)
    elif name == "get_job_details":
        return await job_tools.get_job_details_tool(arguments)
    # Additional tool routing cases...
    else:
        raise ValueError(f"Unknown tool: {name}")
```

### Database Integration

The MCP server will integrate with your existing SQLite database that's synced with Google Cloud Storage:

```python
# Adapter for database integration
class DatabaseAdapter:
    def __init__(self):
        """Initialize database adapter using the existing session management"""
        from jobsearch.core.database import get_session
        self.get_session = get_session
        
    def query_jobs(self, keywords, limit=10):
        """Query jobs from database based on keywords"""
        with self.get_session() as session:
            # Use existing database models and query logic
            # Return formatted results
            pass
```

### Transport Configuration

The MCP server will support both stdio (for VS Code integration) and SSE (for web clients):

```python
# Setup transport and run server
if transport == "sse":
    # SSE transport setup for web clients
    from mcp.server.sse import SseServerTransport
    # Configure web server...
else:
    # Standard input/output transport for VS Code integration
    from mcp.server.stdio import stdio_server
    # Configure stdio server...
```

## VS Code Integration

To integrate with VS Code, create a `.vscode/mcp.json` file in the workspace:

```json
{
  "servers": {
    "jobsearch-mcp": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "jobsearch.mcp_server"]
    }
  }
}
```

## Example Interactions

### Job Search Example

```
User: "Find me senior cloud architect jobs in Seattle"

MCP Server:
1. Parses intent → Job Search
2. Calls search_jobs tool with params:
   - keywords="senior cloud architect Seattle"
3. Returns formatted results with job listings
```

### Document Generation Example

```
User: "Generate documents for the first job in my results"

MCP Server:
1. Tracks context from previous search
2. Calls generate_documents tool with job_id=results[0].id
3. Returns document generation status and links
```

### Strategy Generation Example

```
User: "Create a job search strategy for this week"

MCP Server:
1. Calls generate_strategy tool
2. Returns formatted strategy with daily focus areas and prioritized jobs
```

## Implementation Plan

1. **Phase 1: Core Infrastructure**
   - Set up the MCP server structure
   - Implement basic tool definitions
   - Create database adapters

2. **Phase 2: Job Search Tools**
   - Implement job search functionality
   - Add job analysis and detail tools
   - Add job application tracking

3. **Phase 3: Document Generation**
   - Connect document generation pipeline
   - Add resume and cover letter tools
   - Integrate with Google Cloud Storage for document access

4. **Phase 4: Strategy Tools**
   - Implement strategy generation tools
   - Add weekly focus and tracking tools

5. **Phase 5: Testing and Refinement**
   - Test in VS Code environment
   - Add robust error handling
   - Optimize performance

## Benefits of MCP Integration

1. **Natural Language Interface**: Users can interact with your platform using natural language
2. **AI-Powered Assistance**: Leverage Copilot to help users navigate jobs and generate strategies
3. **Contextual Awareness**: MCP tools maintain context between interactions
4. **Multi-Client Support**: Compatible with VS Code and potential future clients
5. **Structured Interaction**: Well-defined tool schemas ensure consistent, reliable interaction

## Conclusion

The MCP server will provide a natural language interface to the Job Search Automation Platform, enabling users to interact with the system using conversational queries. This integration will make the platform more accessible and user-friendly while leveraging the existing robust backend functionality.