# JobSearch Feature Design Architecture

## Overview

This document provides a comprehensive architecture for features in the jobsearch system, combining:
1. AI Agent capabilities using Pydantic AI
2. Feature-based architecture 
3. Template-driven configuration
4. Core service integration

Each feature in the system becomes a specialized AI agent that inherits from a base feature class, uses templates for configuration, and integrates with core services.

## Core Architecture

### Base Feature Agent

```python
from typing import TypeVar, Generic, Type, AsyncIterator, Optional
from pathlib import Path
from pydantic import BaseModel
from ai.pydantic import Agent, AgentConfig, RunContext, BaseMessage
from ai.pydantic.schema import AgentSchema

from jobsearch.core.logging import setup_logging
from jobsearch.core.storage import GCSManager
from jobsearch.core.database import get_session
from jobsearch.core.monitoring import setup_monitoring
from jobsearch.core.template import TemplateManager

T = TypeVar('T', bound=BaseModel)  # Feature-specific context type
O = TypeVar('O', bound=BaseModel)  # Feature-specific output type

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
            templates_dir=templates_dir or self._default_templates_dir()
        )
        
        # Initialize the AI agent
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
        
        # Register feature-specific tools
        self._register_tools()
        
    def _default_templates_dir(self) -> Path:
        """Get the default templates directory for this feature."""
        return Path(__file__).parent / 'features' / self.name / 'templates'
        
    def _register_tools(self):
        """Register feature-specific tools with the agent."""
        pass  # Override in feature implementations
        
    async def run_with_context(
        self,
        prompt: str,
        context: T,
        output_type: Optional[Type[BaseModel]] = None
    ) -> O:
        """Run the agent with context validation."""
        try:
            self.monitoring.increment(f'{self.name}_run')
            
            # Validate context
            if not isinstance(context, self.agent.deps_type):
                context = self.agent.deps_type(**context)
                
            # Run agent
            result = await self.agent.run(
                prompt,
                context=context,
                output_type=output_type or self.agent.output_type
            )
            
            self.monitoring.track_success(f'{self.name}_run')
            return result
            
        except Exception as e:
            self.monitoring.track_error(f'{self.name}_run', str(e))
            self.logger.error(f"Error running {self.name} agent: {str(e)}")
            raise

    async def stream_with_context(
        self,
        prompt: str,
        context: T,
        output_type: Optional[Type[BaseModel]] = None
    ) -> AsyncIterator[BaseMessage]:
        """Stream agent responses with context validation."""
        try:
            async for message in self.agent.stream(
                prompt,
                context=context,
                output_type=output_type or self.agent.output_type
            ):
                yield message
                
        except Exception as e:
            self.logger.error(f"Error streaming {self.name} agent: {str(e)}")
            raise
            
    async def __aenter__(self):
        """Allow features to be used as async context managers."""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up when exiting the context."""
        pass
```

## Directory Structure

```
jobsearch/
├── core/
│   ├── feature.py          # Base feature agent class
│   ├── template.py         # Template management
│   ├── database.py         # Database integration
│   ├── storage.py          # Cloud storage
│   ├── logging.py          # Logging utilities
│   └── monitoring.py       # Monitoring tools
├── features/
│   ├── job_search/
│   │   ├── feature.py      # JobSearchAgent implementation
│   │   ├── models.py       # Feature-specific models
│   │   └── templates/
│   │       ├── system.j2   # System prompt template
│   │       ├── search.j2   # Job search prompts
│   │       └── analyze.j2  # Analysis prompts
│   ├── document_generation/
│   │   ├── feature.py
│   │   └── templates/
│   │       ├── system.j2
│   │       ├── resume.j2
│   │       └── cover_letter.j2
│   └── strategy_generation/
│       ├── feature.py  
│       └── templates/
│           ├── system.j2
│           ├── daily.j2
│           └── weekly.j2
```

## Feature Implementation Pattern

### 1. Define Feature Models

```python
class JobSearchContext(BaseModel):
    """Type-safe context for job search operations."""
    query: str
    location: Optional[str] = None
    experience_level: str
    remote_only: bool = False
    company_size: Optional[str] = None
    
class JobListing(BaseModel):
    """Schema for job listings."""
    url: str
    title: str
    company: str
    location: str
    description: str
    post_date: Optional[str] = None
    
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
You have access to these tools:
{% for tool in tools %}
- {{ tool.name }}: {{ tool.description }}
{% endfor %}

{# job_search/templates/search.j2 #}
You are searching for jobs matching:
Query: {{ query }}
{% if location %}Location: {{ location }}{% endif %}
Experience Level: {{ experience_level }}
{% if remote_only %}Remote Only: Yes{% endif %}
{% if company_size %}Company Size: {{ company_size }}{% endif %}

Please search for relevant positions using the available tools.
Analyze each position for fit and requirements.
Return results in structured format.

{# job_search/templates/analyze.j2 #}
Analyze this job posting for fit:
Title: {{ job.title }}
Company: {{ job.company }}
Description: {{ job.description }}

Consider:
1. Required skills
2. Experience level
3. Culture fit
4. Growth potential
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
            query = ctx.deps.query
            # Implementation...
            
        @self.agent.tool
        async def analyze_job_fit(
            ctx: RunContext[JobSearchContext],
            job: JobListing
        ) -> JobAnalysis:
            """Analyze job fit for candidate."""
            # Implementation...
            
    async def search(self, query: str, **kwargs) -> JobSearchResult:
        """Perform job search with context."""
        context = JobSearchContext(
            query=query,
            **kwargs
        )
        return await self.run_with_context(
            prompt=self.template_manager.render(
                'search.j2',
                context=context.dict()
            ),
            context=context
        )
```

## Advanced Features

### 1. Pipeline Processing

```python
class JobSearchPipeline:
    """Pipeline multiple agents for complex operations."""
    
    def __init__(self):
        self.search_agent = JobSearchAgent()
        self.analysis_agent = JobAnalysisAgent()
        self.strategy_agent = StrategyAgent()
        
    async def process_job(self, job: JobListing) -> JobStrategy:
        # Pipeline multiple agents
        analysis = await self.analysis_agent.analyze(job)
        strategy = await self.strategy_agent.generate_strategy(analysis)
        return strategy
```

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
            
        # Update conversation history
        self.agent.add_to_history(message)
```

### 3. Template Management

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
        
        # Add custom filters
        env.filters['format_date'] = lambda d: d.strftime('%Y-%m-%d')
        env.filters['skills_list'] = lambda s: ', '.join(s)
        
        return env
        
    def render(self, template_name: str, context: dict) -> str:
        """Render a template with context."""
        template = self.env.get_template(template_name)
        return template.render(**context)
```

## Core Components Integration

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

### 3. Integration Tests

```python
async def test_job_search_pipeline():
    """Test complete job search pipeline."""
    pipeline = JobSearchPipeline()
    job = await pipeline.search_agent.search("python developer")
    analysis = await pipeline.analysis_agent.analyze(job)
    strategy = await pipeline.strategy_agent.generate_strategy(analysis)
    assert strategy.next_steps
```

## Migration Guide

1. Create Feature Agent:
```python
from jobsearch.core.feature import BaseFeatureAgent

class MyFeatureAgent(BaseFeatureAgent[MyContext, MyOutput]):
    def __init__(self):
        super().__init__(
            name="my_feature",
            context_type=MyContext,
            output_type=MyOutput
        )
```

2. Create Templates:
```jinja
{# my_feature/templates/system.j2 #}
You are a specialized assistant for {{ feature_name }}.
You have access to these tools:
{% for tool in tools %}
- {{ tool.name }}: {{ tool.description }}
{% endfor %}
```

3. Update Calling Code:
```python
# Before
result = await process_data(data)

# After
agent = MyFeatureAgent()
result = await agent.process(data)
```

## Benefits

1. Type Safety:
- Input/output validation
- IDE support
- Runtime checks

2. Modularity:
- Self-contained features
- Clear boundaries
- Easy testing

3. Reusability:
- Shared components
- Common patterns
- Core integration

4. Maintainability:
- Error handling
- Monitoring
- Logging

5. Flexibility:
- Template customization
- Feature extension
- Pipeline composition

This architecture provides a robust foundation for building AI-powered features that are:
- Type-safe
- Maintainable
- Reusable
- Testable
- Performant
