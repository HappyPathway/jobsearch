# Feature Agent Architecture

## Overview

This document details how each feature in the jobsearch system becomes a specialized AI agent by combining our BaseFeature class with Pydantic's Agent class. This architecture provides type-safe AI interactions, template management, and core service integration.

## Core Architecture

### Base Feature Agent

```python
from typing import TypeVar, Generic, Type
from pydantic import BaseModel
from ai.pydantic import Agent, AgentConfig, RunContext, BaseMessage
from ai.pydantic.schema import AgentSchema

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
        system_prompt: str,
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
```

## Feature Implementation Pattern

Each feature implements its own agent by:

1. Defining Input/Output Types:
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

2. Creating Feature-Specific Agent:
```python
class JobSearchAgent(BaseFeatureAgent[JobSearchContext, JobSearchResult]):
    """Job search and analysis agent."""
    
    def __init__(self):
        super().__init__(
            name="job_search",
            context_type=JobSearchContext,
            output_type=JobSearchResult,
            templates_dir="job_search/templates"
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

3. Using Templates:
```jinja
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
```

## Advanced Features

### 1. Conversation Management

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

### 2. Tool Integration

```python
class JobSearchAgent(BaseFeatureAgent[JobSearchContext, JobSearchResult]):
    def _register_tools(self):
        # Register core tools
        self.agent.register_tool(
            self.storage.save_job,
            name="save_job",
            description="Save a job listing to storage"
        )
        
        # Register API tools
        self.agent.register_tool(
            self.indeed_client.search,
            name="search_indeed",
            description="Search Indeed API"
        )
```

### 3. Pipeline Processing

```python
class JobSearchPipeline:
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

## Type Safety and Validation

### 1. Input Validation

```python
class JobSearchAgent(BaseFeatureAgent[JobSearchContext, JobSearchResult]):
    async def search(self, **kwargs):
        # Validate input
        context = JobSearchContext(**kwargs)
        
        # Type-safe operation
        result: JobSearchResult = await self.run_with_context(
            "Search for jobs",
            context
        )
        return result
```

### 2. Output Validation

```python
class JobAnalysis(BaseModel):
    """Validated job analysis output."""
    match_score: float = Field(ge=0, le=1)
    requirements: List[str]
    missing_skills: List[str]
    growth_potential: str = Field(regex="^(high|medium|low)$")
```

## Error Handling

```python
class JobSearchAgent(BaseFeatureAgent[JobSearchContext, JobSearchResult]):
    async def safe_search(self, **kwargs) -> Optional[JobSearchResult]:
        try:
            return await self.search(**kwargs)
        except ValidationError as e:
            self.logger.error(f"Invalid input: {e}")
            return None
        except AgentError as e:
            self.logger.error(f"Agent error: {e}")
            self.monitoring.track_error("search_failed", str(e))
            return None
```

## Performance Optimization

1. Caching:
```python
class JobSearchAgent(BaseFeatureAgent[JobSearchContext, JobSearchResult]):
    @cached_property
    def templates(self):
        return self.template_manager.load_templates()
        
    @lru_cache(maxsize=100)
    async def get_company_info(self, company: str) -> CompanyInfo:
        return await self.agent.run_tool("fetch_company_info", company)
```

2. Batch Processing:
```python
class JobSearchAgent(BaseFeatureAgent[JobSearchContext, JobSearchResult]):
    async def batch_search(self, queries: List[str]) -> List[JobSearchResult]:
        tasks = [self.search(query) for query in queries]
        return await asyncio.gather(*tasks, return_exceptions=True)
```

## Testing

1. Agent Testing:
```python
async def test_job_search_agent():
    agent = JobSearchAgent()
    result = await agent.search(
        query="python developer",
        location="remote"
    )
    assert isinstance(result, JobSearchResult)
    assert len(result.jobs) > 0
```

2. Template Testing:
```python
def test_job_search_templates():
    agent = JobSearchAgent()
    rendered = agent.template_manager.render(
        'search.j2',
        {'query': 'test'}
    )
    assert 'test' in rendered
```

## Benefits of This Architecture

1. Type Safety:
- Input/output validation
- IDE support
- Runtime checks

2. Modularity:
- Each feature is a self-contained agent
- Clear interface boundaries
- Easy to test

3. Reusability:
- Share tools across agents
- Common template patterns
- Core functionality inheritance

4. Maintainability:
- Structured error handling
- Clear logging
- Performance monitoring

5. Extensibility:
- Easy to add new features
- Plugin architecture
- Template customization

## Migration Guide

1. For each feature:
- Create feature-specific agent class
- Define input/output models
- Convert prompts to templates
- Register tools
- Add tests

2. Update calling code:
```python
# Before
result = await search_jobs("python developer")

# After
agent = JobSearchAgent()
result = await agent.search(query="python developer")
```

This architecture provides a robust foundation for building AI-powered features that are:
- Type-safe
- Maintainable
- Reusable
- Testable
- Performant
