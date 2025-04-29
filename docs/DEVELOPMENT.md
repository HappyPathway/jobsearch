# Development Guide

## Overview

This guide covers development tools and practices for the JobSearch platform, including:

1. VS Code Extension
2. MCP Integration
3. Structured Output
4. Development Workflow
5. Documentation with Sphinx

## VS Code Extension

### Architecture

```
┌─────────────────────────────────────────────┐
│                VS Code                       │
│  ┌─────────────┐        ┌────────────────┐  │
│  │ Job Search  │        │                │  │
│  │ Extension   │◄──────►│ WebView Panels │  │
│  │ (TypeScript)│        │ (HTML/CSS/JS)  │  │
│  └─────────────┘        └────────────────┘  │
└───────────┬─────────────────────────┬───────┘
            │                         │
            ▼                         ▼
┌───────────────────┐      ┌─────────────────────┐
│ Job Search API    │      │ Document Storage    │
│ (FastAPI)         │      │ (Local Files & GCS) │
└───────────────────┘      └─────────────────────┘
```

### Project Structure

```
jobsearch-vscode/
├── package.json            # Extension manifest
├── tsconfig.json          # TypeScript config
├── src/
│   ├── extension.ts       # Extension entry point
│   ├── panels/           # WebView implementations
│   │   ├── dashboardPanel.ts
│   │   ├── strategyPanel.ts
│   │   ├── profilePanel.ts
│   │   └── documentPanel.ts
│   ├── api/             # API client layer
│   │   ├── apiClient.ts
│   │   ├── jobsApi.ts
│   │   └── documentsApi.ts
│   └── utils/           # Utility functions
└── webview-ui/          # WebView frontend
    ├── shared/          # Shared components
    ├── dashboard/       # Panel-specific UI
    ├── strategy/
    ├── profile/
    └── documents/
```

### Key Components

1. **Dashboard Panel**
```
┌───────────────────────────────────────────────────────┐
│ Job Dashboard                                   [_][X] │
├───────────────────────────────────────────────────────┤
│ Today's Focus                                         │
│ ┌─────────────────────────────────────────┐          │
│ │ 1. Complete AWS Solutions Architect apps            │
│ │ 2. Research FinTech companies                      │
│ │ 3. Update cloud architecture portfolio             │
│ └─────────────────────────────────────────┘          │
│                                                       │
│ Priority Jobs                                         │
│ ┌───────────────────────────────────────────────────┐ │
│ │ Senior Cloud Architect - Amazon AWS               │ │
│ │ Match: 95% │ Priority: High │ Seattle, WA         │ │
│ │ [View Details] [Generate Documents] [Apply]        │ │
│ └───────────────────────────────────────────────────┘ │
```

2. **Document Generator**
```
┌───────────────────────────────────────────────────────┐
│ Document Generator                             [_][X] │
├───────────────────────────────────────────────────────┤
│ ┌─────────────────────────┐ ┌─────────────────────┐   │
│ │ Job Selection           │ │ Options             │   │
│ │ ┌─────────────────────┐ │ │                     │   │
│ │ │ [Select Job ▼]      │ │ │ ☑ Visual Resume     │   │
│ │ └─────────────────────┘ │ │ ☑ Writing Pass      │   │
│ │                         │ │ ☐ Include Projects  │   │
```

## MCP Integration

> **Related Documentation:**
> - [Feature Agent System](ARCHITECTURE.md#core-components) - Base feature agent that MCP builds on
> - [Core AI Integration](CORE.md#ai-integration) - AI capabilities used by MCP
> - [Template System](CORE.md#template-best-practices) - Template patterns for MCP responses

### Complete MCP Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  VS Code with   │     │                  │     │ Job Search      │
│  Copilot or     │◄───►│   MCP Server     │◄───►│ Automation      │
│  other MCP      │     │                  │     │ Platform        │
│  clients        │     │                  │     │ (Existing Code) │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

### MCP Server Implementation

```python
from mcp_python import Agent, Tool, AgentConfig

class JobSearchMCPServer:
    """MCP server implementation."""
    
    def __init__(self):
        self.job_feature = JobSearchFeature()
        self.doc_feature = DocumentFeature()
        self.strategy_feature = StrategyFeature()
        
    async def list_tools(self) -> List[Tool]:
        """Define available tools."""
        return [
            Tool(
                name="search_jobs",
                description="Search for jobs",
                input_schema=JobSearchSchema,
                handler=self.job_feature.search
            ),
            Tool(
                name="generate_documents",
                description="Generate application documents",
                input_schema=DocumentGenSchema,
                handler=self.doc_feature.generate
            )
        ]
        
    async def handle_call(self, tool_name: str, args: dict):
        """Handle tool invocation."""
        tool = self.get_tool(tool_name)
        return await tool.handler(**args)
```

### Tool Definitions

```python
job_search_tool = Tool(
    name="search_jobs",
    description="Search for jobs based on criteria",
    input_schema={
        "type": "object",
        "required": ["keywords"],
        "properties": {
            "keywords": {"type": "string"},
            "location": {"type": "string"},
            "remote": {"type": "boolean"},
            "experience": {"type": "string"}
        }
    }
)

document_tool = Tool(
    name="generate_documents",
    description="Generate application documents",
    input_schema={
        "type": "object",
        "required": ["job_id"],
        "properties": {
            "job_id": {"type": "string"},
            "document_type": {"enum": ["resume", "cover_letter"]},
            "customize": {"type": "boolean"}
        }
    }
)
```

## Testing Patterns

> **Related Documentation:**
> - [Test Infrastructure](ARCHITECTURE.md#testing-infrastructure) - Base test classes and utilities
> - [Core Test Utilities](CORE.md#testing-utilities) - Shared testing components
> - [Testing Best Practices](ARCHITECTURE.md#best-practices) - Testing guidelines and patterns

### Test Categories

1. **Unit Tests**
```python
class TestJobSearchFeature:
    # See ARCHITECTURE.md#testing-infrastructure for base test class implementation
    def test_search_validation(self):
        """Test input validation."""
        with pytest.raises(ValidationError):
            JobSearchContext(invalid_field="test")
            
    def test_search_execution(self):
        """Test search execution."""
        result = self.feature.search("python developer")
        assert isinstance(result, List[JobListing])
```

2. **Integration Tests**
```python
class TestJobSearchWorkflow:
    async def test_complete_workflow(self):
        """Test complete job search workflow."""
        # Search for jobs
        jobs = await self.feature.search("python")
        assert jobs
        
        # Analyze first job
        analysis = await self.analyzer.analyze(jobs[0])
        assert analysis.match_score > 0
        
        # Generate documents
        docs = await self.doc_generator.generate(jobs[0])
        assert docs.resume and docs.cover_letter
```

3. **Template Tests**
```python
class TestTemplateSystem:
    def test_template_rendering(self):
        """Test template rendering."""
        result = self.templates.render(
            "search.j2",
            {"query": "test"}
        )
        assert "test" in result
        
    def test_template_inheritance(self):
        """Test template inheritance."""
        result = self.templates.render(
            "custom_search.j2",
            {"query": "test", "location": "remote"}
        )
        assert "test" in result
        assert "remote" in result
```

### Test Utilities

1. **Mock AI Responses**
```python
class MockAIEngine:
    """Mock AI engine for testing."""
    
    def __init__(self, responses: Dict[str, Any]):
        self.responses = responses
        
    async def generate(self, prompt: str, **kwargs):
        """Return mock response."""
        for pattern, response in self.responses.items():
            if pattern in prompt:
                return response
        raise ValueError("No mock response found")
```

2. **Test Fixtures**
```python
@pytest.fixture
def mock_storage():
    """Mock storage for testing."""
    return MockStorage()
    
@pytest.fixture
def mock_db():
    """In-memory test database."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()
```

## Structured Output

### Output Schema Definition

```python
class JobAnalysis(BaseModel):
    """Job analysis output schema."""
    match_score: float = Field(ge=0, le=1)
    required_skills: List[str]
    missing_skills: List[str]
    experience_match: bool
    location_match: bool
    salary_range: Optional[str]
    
class DocumentOutput(BaseModel):
    """Document generation output schema."""
    resume: str
    cover_letter: str
    customization_score: float = Field(ge=0, le=1)
    ats_score: float = Field(ge=0, le=1)
```

### Schema Validation

```python
def validate_output(data: dict, schema: Type[BaseModel]) -> BaseModel:
    """Validate output against schema."""
    try:
        return schema(**data)
    except ValidationError as e:
        raise OutputValidationError(str(e))
```

## Development Workflow

### Setup Development Environment

```bash
# Clone repository
git clone git@github.com:username/jobsearch.git
cd jobsearch

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Set up pre-commit hooks
pre-commit install
```

### Development Process

1. Create feature branch
```bash
git checkout -b feature/new-feature
```

2. Implement changes
```bash
# Update feature code
vim jobsearch/features/new_feature/feature.py

# Add tests
vim tests/test_new_feature.py

# Run tests
pytest tests/test_new_feature.py
```

3. Update documentation
```bash
# Update feature docs
vim docs/features/new_feature.md

# Update architecture if needed
vim docs/ARCHITECTURE.md
```

### Code Review Process

1. Run pre-commit checks
```bash
pre-commit run --all-files
```

2. Run test suite
```bash
pytest tests/
```

3. Create pull request
```bash
gh pr create --title "Add new feature" --body "Description"
```

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run tests
        run: pytest tests/
      - name: Run type checks
        run: mypy jobsearch/

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v2
      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v0
      - name: Deploy
        run: |
          gcloud functions deploy job-strategy \
            --runtime python311 \
            --trigger-http \
            --allow-unauthenticated
```

### Deployment Process

1. **Development**
   - Local testing
   - Code review
   - Documentation updates

2. **Staging**
   - Integration testing
   - Performance testing
   - Security scanning

3. **Production**
   - Blue-green deployment
   - Monitoring setup
   - Backup verification

## Documentation with Sphinx

The JobSearch project uses Sphinx to generate API documentation from docstrings. This allows us to maintain accurate and up-to-date documentation directly from the code.

### Sphinx AutoAPI

We use the `sphinx-autoapi` extension to automatically generate API documentation from our codebase. This extension:

1. **Automatically discovers modules**: No need to manually document each module or class
2. **Preserves code structure**: Maintains the same hierarchical structure as your code
3. **Extracts docstrings**: Pulls properly formatted docstrings to create comprehensive documentation
4. **Includes type hints**: Shows parameter and return types in the documentation

AutoAPI is configured in our `conf.py` as follows:

```python
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'autoapi.extension',
    'myst_parser',
]

# AutoAPI settings
autoapi_type = 'python'
autoapi_dirs = ['../jobsearch']
autoapi_output = 'api'
autoapi_options = [
    'members', 
    'undoc-members',
    'private-members',
    'show-inheritance',
    'show-module-summary',
    'special-members',
]
```

### Core Library Agent Framework

The JobSearch platform uses pydantic-ai for all LLM interactions through the `BaseLLMAgent` class in the core library. This provides a standardized way to build feature-specific agents that inherit from this base class.

```python
from jobsearch.core.llm_agent import BaseLLMAgent
from jobsearch.core.schemas import JobAnalysis

class JobAnalysisAgent(BaseLLMAgent):
    def __init__(self):
        super().__init__(
            feature_name='job_analysis',
            output_type=JobAnalysis
        )
        
    async def analyze_job(self, job_description: str) -> JobAnalysis:
        return await self.generate(
            prompt=f"Analyze this job description: {job_description}",
        )
```

The `BaseLLMAgent` handles:

1. **Structured Output**: Type-safe responses using pydantic models
2. **Error Handling**: Standardized error handling and retries
3. **Monitoring**: Automatic tracking of token usage and performance metrics
4. **Tool Registration**: Easy registration of tool functions the LLM can use

All feature-specific agents should inherit from `BaseLLMAgent` to ensure consistency and maintainability.

### Setup and Generation

To set up and generate documentation:

```bash
# Install Sphinx and required extensions
python scripts/sphinx_setup.py

# Generate documentation
cd docs
sphinx-build -b html . _build/html
```

The generated documentation will be available in the `docs/_build/html` directory.

### Docstring Format

We use Google-style docstrings for Sphinx. Every module, class, and function should include appropriate docstrings:

```python
def function_name(param1: type, param2: type) -> return_type:
    """Short description of function.
    
    More detailed description of what this function does, its purpose,
    and any other relevant information.
    
    Args:
        param1: Description of first parameter
        param2: Description of second parameter
    
    Returns:
        Description of what is returned
        
    Raises:
        ExceptionType: When and why this exception is raised
    
    Example:
        ```python
        result = function_name("value", 42)
        ```
    """
```

### Documentation Guidelines

1. **Module Docstrings**: Every module should have a docstring explaining its purpose and providing usage examples
2. **Class Docstrings**: Classes should document their purpose, attributes, and include usage examples
3. **Method Docstrings**: Methods should describe parameters, return values, exceptions, and behavior
4. **Type Hints**: All functions should use type hints to improve documentation
5. **Examples**: Include examples in docstrings for complex functions

See our core library modules for examples of properly documented code.

### Fixing Core Module Documentation

When improving documentation in core modules, follow these steps:

1. **Identify Missing Documentation**: Use Sphinx warnings to identify modules, classes, or functions with missing or incomplete docstrings

2. **Follow the Google Style**: Ensure all docstrings follow the Google format:
   - Module docstrings should include purpose, examples, and any important notes
   - Class docstrings should document purpose and attributes
   - Method docstrings should cover parameters, return values, and exceptions

3. **Add Examples**: Include practical usage examples in docstrings for complex functionality

4. **Test Documentation Build**: After updating docstrings, rebuild the documentation to verify:
   ```bash
   cd docs
   sphinx-build -b html . _build/html
   ```

5. **Validate in Browser**: Open `docs/_build/html/index.html` in your browser to verify the documentation renders correctly

6. **Documentation PR Templates**: Use the docstring template from our standards when creating pull requests that update documentation:

```markdown
## Documentation Updates
- [ ] Module docstrings updated
- [ ] Class docstrings updated
- [ ] Method/function docstrings updated
- [ ] Examples added where appropriate
- [ ] Documentation builds without warnings
```

7. **Specific Areas to Focus**: When documenting core modules, pay special attention to:
   - Public APIs exposed to feature developers
   - Complex functionality that might be difficult to understand
   - Integration points between different core components
   - Configuration options and their effects
