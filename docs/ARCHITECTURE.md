# JobSearch Platform Architecture

## Overview

The JobSearch platform is a modular, AI-powered system that automates job search workflows using:
1. Feature-based Agent Architecture
2. Template-driven Configuration
3. Core Service Integration
4. Type-safe Interactions

## System Architecture

### Directory Structure

```
jobsearch/
├── core/                     # Core components
│   ├── feature.py           # Base feature agent
│   ├── template.py          # Template management
│   ├── database.py          # Database integration
│   ├── storage.py           # Cloud storage
│   ├── logging.py           # Logging utilities
│   └── monitoring.py        # Monitoring tools
├── features/                 # Feature implementations
│   ├── job_search/
│   │   ├── feature.py       # JobSearchAgent
│   │   ├── models.py        # Feature models
│   │   └── templates/       # Feature templates
│   ├── document_generation/
│   ├── strategy_generation/
│   └── web_presence/
├── tests/                    # Test suite
└── scripts/                  # CLI tools
```

### Core Components

1. **Base Feature Agent**
```python
class BaseFeatureAgent(Generic[T, O]):
    """Base class for all feature agents.
    
    Features inherit from this to get:
    1. AI agent capabilities
    2. Template management 
    3. Core service integration
    4. Type-safe interactions
    """
    def __init__(
        self,
        name: str,
        context_type: Type[T],
        output_type: Type[O],
        system_prompt: Optional[str] = None,
        model: str = "gemini-pro",
        templates_dir: Optional[str] = None
    ):
        # Initialize core components
        self.name = name
        self.logger = setup_logging(name)
        self.storage = GCSManager()
        self.monitoring = setup_monitoring(name)
        
        # Set up template management
        self.template_manager = TemplateManager(
            feature_name=name,
            templates_dir=templates_dir
        )
        
        # Initialize AI agent
        self.agent = Agent(
            model,
            deps_type=context_type,
            output_type=output_type,
            config=AgentConfig(
                system_prompt=system_prompt or self.template_manager.get_template('system.j2'),
                temperature=0.7,
                max_tokens=2000
            )
        )
```

2. **Template Management**
```python
class TemplateManager:
    """Manages templates for a feature."""
    
    def __init__(self, feature_name: str, templates_dir: Path):
        self.env = self._create_environment(templates_dir)
        self.feature_name = feature_name
        
    def _create_environment(self, templates_dir: Path) -> Environment:
        """Create Jinja environment with custom filters."""
        env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True
        )
        return env
        
    def render(self, template_name: str, context: dict) -> str:
        """Render a template with context."""
        template = self.env.get_template(template_name)
        return template.render(**context)
```

## Feature Implementation

### 1. Define Feature Models

```python
class JobSearchContext(BaseModel):
    """Type-safe context for job search operations."""
    query: str
    location: Optional[str] = None
    experience_level: str
    remote_only: bool = False
    company_size: Optional[str] = None
    
class JobSearchResult(BaseModel):
    """Type-safe output for job search operations."""
    jobs: List[JobListing]
    next_page_token: Optional[str]
    total_results: int
```

### 2. Create Feature Templates

```jinja
{# job_search/templates/system.j2 #}
You are a specialized job search assistant that helps candidates find and analyze job opportunities.

{# job_search/templates/search.j2 #}
You are searching for jobs matching:
Query: {{ query }}
{% if location %}Location: {{ location }}{% endif %}
Experience Level: {{ experience_level }}
{% if remote_only %}Remote Only: Yes{% endif %}
{% if company_size %}Company Size: {{ company_size }}{% endif %}
```

### 3. Implement Feature Agent

```python
class JobSearchAgent(BaseFeatureAgent[JobSearchContext, JobSearchResult]):
    """Job search and analysis agent."""
    
    def __init__(self):
        super().__init__(
            name="job_search",
            context_type=JobSearchContext,
            output_type=JobSearchResult
        )
        
    def _register_tools(self):
        """Register job search specific tools."""
        @self.agent.tool
        async def search_indeed(ctx: RunContext[JobSearchContext]) -> List[JobListing]:
            """Search Indeed for job listings."""
            pass
            
    async def search(self, query: str, **kwargs) -> JobSearchResult:
        """Perform job search with context."""
        context = JobSearchContext(query=query, **kwargs)
        return await self.run_with_context(
            prompt=self.template_manager.render('search.j2', context.dict()),
            context=context
        )
```

## Advanced Features

### 1. Pipeline Processing

The platform supports pipelining multiple feature agents for complex operations:

```python
class JobSearchPipeline:
    """Pipeline for complete job search workflow."""
    
    def __init__(self):
        self.search_agent = JobSearchAgent()
        self.analysis_agent = JobAnalysisAgent()
        self.strategy_agent = StrategyAgent()
        
    async def process_job(self, job: JobListing) -> JobStrategy:
        """Run complete job processing pipeline."""
        # Pipeline stages
        analysis = await self.analysis_agent.analyze(job)
        strategy = await self.strategy_agent.generate_strategy(analysis)
        return strategy
```

### Pipeline Design
1. Each stage is a feature agent
2. Outputs are validated between stages
3. Context is maintained throughout
4. Error handling at each stage

### 2. Conversation Management

```python
class JobSearchAgent(BaseFeatureAgent[JobSearchContext, JobSearchResult]):
    async def interactive_search(self, initial_query: str) -> AsyncIterator[BaseMessage]:
        """Interactive job search with conversation history."""
        context = JobSearchContext(query=initial_query)
        async for message in self.stream_with_context(
            prompt=self.template_manager.render('interactive_search.j2'),
            context=context
        ):
            yield message
            self.agent.add_to_history(message)
```

## Core Integration

### 1. Database Integration

```python
class JobSearchAgent(BaseFeatureAgent[JobSearchContext, JobSearchResult]):
    async def save_job(self, job: JobListing):
        """Save job to database."""
        with self.context.db() as session:
            db_job = JobCache(
                url=job.url,
                title=job.title,
                company=job.company,
                description=job.description
            )
            session.add(db_job)
            session.commit()
```

### 2. Storage Integration

```python
class DocumentGenerationAgent(BaseFeatureAgent[DocumentContext, GeneratedDocument]):
    async def save_document(self, doc: GeneratedDocument):
        """Save document to cloud storage."""
        path = f"documents/{doc.type}/{doc.id}.pdf"
        await self.storage.upload_file(
            path,
            doc.content,
            content_type="application/pdf"
        )
```

### 3. Monitoring Integration

```python
class JobSearchAgent(BaseFeatureAgent[JobSearchContext, JobSearchResult]):
    async def search(self, query: str, **kwargs):
        try:
            self.monitoring.increment('job_search')
            result = await super().search(query, **kwargs)
            self.monitoring.track_success('job_search')
            return result
        except Exception as e:
            self.monitoring.track_error('job_search', str(e))
            raise
```

## Testing

### 1. Unit Tests

```python
async def test_job_search_agent():
    """Test job search functionality."""
    agent = JobSearchAgent()
    result = await agent.search(
        query="python developer",
        location="remote"
    )
    assert isinstance(result, JobSearchResult)
    assert len(result.jobs) > 0
```

### 2. Template Tests

```python
def test_templates():
    """Test template rendering."""
    agent = JobSearchAgent()
    rendered = agent.template_manager.render(
        'search.j2',
        {'query': 'test'}
    )
    assert 'test' in rendered
```

## Best Practices

1. Use existing core components as building blocks
2. Keep features self-contained and focused
3. Validate inputs and outputs with Pydantic models
4. Use templates for all AI prompts
5. Monitor and log feature operations
6. Write comprehensive tests

## Benefits

1. **Type Safety**
- Input/output validation
- IDE support
- Runtime checks

2. **Modularity**
- Self-contained features
- Clear boundaries
- Easy testing

3. **Reusability**
- Shared components
- Common patterns
- Core integration

4. **Maintainability**
- Error handling
- Monitoring
- Logging

5. **Flexibility**
- Template customization
- Feature extension
- Pipeline composition

## Error Handling

### Core Error Types
```python
class FeatureError(Exception):
    """Base error for all feature-related errors."""
    def __init__(self, feature_name: str, message: str):
        self.feature_name = feature_name
        super().__init__(f"{feature_name}: {message}")

class TemplateError(FeatureError):
    """Template-related errors."""
    pass

class AIError(FeatureError):
    """AI operation errors."""
    pass
```

### Error Handling Pattern
```python
class BaseFeature:
    async def safe_operation(self, operation_name: str):
        """Template for safe operation execution."""
        try:
            self.monitoring.increment(operation_name)
            result = await self._execute_operation()
            self.monitoring.track_success(operation_name)
            return result
        except Exception as e:
            self.monitoring.track_error(operation_name, str(e))
            self.logger.error(f"Error in {operation_name}: {str(e)}")
            raise FeatureError(self.name, str(e))
```

## Testing Infrastructure

> **Related Documentation:**
> - [Testing Patterns](DEVELOPMENT.md#testing-patterns) - Detailed testing examples and patterns
> - [Core Test Utilities](CORE.md#testing-utilities) - Shared test components
> - [CI/CD Pipeline](DEVELOPMENT.md#ci-cd-pipeline) - Automated testing workflow

### Base Test Classes
```python
class BaseFeatureTest:
    """Base class for feature tests."""
    
    @pytest.fixture
    def feature(self):
        """Create test feature instance."""
        return self.feature_class()
        
    @pytest.fixture
    def mock_ai(self):
        """Mock AI responses."""
        return MockAIEngine()
        
    @pytest.fixture
    def mock_storage(self):
        """Mock storage operations."""
        return MockStorage()

class TemplateTest(BaseFeatureTest):
    """Base class for template tests."""
    
    def validate_template(self, name: str, context: dict):
        """Validate template rendering."""
        result = self.feature.template_manager.render(name, context)
        assert result, f"Template {name} failed to render"
```

### Test Categories
1. Unit Tests
   - Feature class methods
   - Template rendering
   - Tool integration
   
2. Integration Tests
   - Complete workflows
   - Pipeline operations
   - Core service interaction
   
3. Performance Tests
   - Template rendering speed
   - AI response caching
   - Database operations

## Migration Guide

### Steps for Feature Migration

1. **Prepare Migration**
   - Review existing implementation
   - Identify core component usage
   - Plan template structure
   - Define type requirements

2. **Create Types**
```python
class FeatureContext(BaseModel):
    """Feature-specific context."""
    query: str
    options: Dict[str, Any]
    
class FeatureOutput(BaseModel):
    """Feature-specific output."""
    result: str
    metadata: Dict[str, Any]
```

3. **Convert to Templates**
```jinja
{# system.j2 #}
You are a specialized {{ feature_name }} assistant.
Available tools:
{% for tool in tools %}
- {{ tool.name }}: {{ tool.description }}
{% endfor %}
```

4. **Update Feature Class**
```python
class MyFeature(BaseFeature[MyContext, MyOutput]):
    def __init__(self):
        super().__init__(
            name="my_feature",
            context_type=MyContext,
            output_type=MyOutput
        )
```

5. **Add Tests**
```python
class TestMyFeature(BaseFeatureTest):
    def test_feature_operation(self):
        result = self.feature.process(test_input)
        assert isinstance(result, MyOutput)
```

### Migration Checklist
1. [ ] Create feature-specific types
2. [ ] Convert prompts to templates
3. [ ] Update feature class
4. [ ] Add feature-specific tools
5. [ ] Add comprehensive tests
6. [ ] Update documentation

### Common Pitfalls
1. Copying core functionality
2. Skipping type validation
3. Complex templates
4. Missing error handling
5. Insufficient testing
