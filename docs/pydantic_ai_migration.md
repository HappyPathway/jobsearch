# Migrating to Pydantic-AI

This document outlines the plan to migrate our job search automation platform to use Pydantic-AI for better handling of LLM interactions.

## Why Pydantic-AI?

Our current codebase uses custom structured prompts and manual validation for Gemini interactions. Migrating to Pydantic-AI would provide several key benefits:

1. **Type-Safe LLM Interactions**
   - Built-in validation of model inputs/outputs
   - Better IDE support and error catching
   - Cleaner interface to Gemini and other LLMs

2. **Structured Outputs**
   - Replace our custom validation logic with Pydantic models
   - Automatic validation and type conversion
   - Clear schema definitions for LLM responses

3. **Better Tools Integration**
   - Decorator-based approach for tools
   - Built-in dependency injection
   - Cleaner separation of concerns

4. **Monitoring & Debugging**
   - Integration with Pydantic Logfire
   - Track token usage and costs
   - Monitor performance and error patterns

## Migration Plan

### 1. Job Analysis Migration

Current structure:
```python
def analyze_job_with_gemini(job_info: JobInfo) -> Optional[Dict]:
    # Custom validation and processing
    ...
```

Pydantic-AI structure:
```python
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from enum import Enum

class LocationType(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"

class CompanySize(str, Enum):
    STARTUP = "startup"
    MIDSIZE = "midsize"
    LARGE = "large"
    ENTERPRISE = "enterprise"

class JobAnalysis(BaseModel):
    match_score: float = Field(ge=0, le=100, description="Match score between 0-100")
    key_requirements: list[str] = Field(description="Key job requirements")
    culture_indicators: list[str] = Field(description="Cultural fit indicators")
    career_growth_potential: str
    total_years_experience: int = Field(ge=0)
    candidate_gaps: list[str]
    location_type: LocationType
    company_size: CompanySize
    company_stability: str
    development_opportunities: list[str]

job_analysis_agent = Agent(
    'google-gla:gemini-1.5-pro',
    output_type=JobAnalysis,
    system_prompt='Analyze job postings for fit and potential'
)
```

### 2. Job Search Strategy Migration

Current:
```python
def generate_daily_strategy(profile_data: Dict, ...) -> Optional[Dict]
```

Pydantic-AI:
```python
class ActionItem(BaseModel):
    description: str
    priority: str = Field(pattern="^(high|medium|low)$")
    deadline: str
    metrics: list[str]

class DailyStrategy(BaseModel):
    focus_area: str
    goals: list[str]
    action_items: list[ActionItem]
    resources_needed: list[str]
    success_metrics: dict[str, str]

strategy_agent = Agent(
    'google-gla:gemini-1.5-pro',
    output_type=DailyStrategy,
    system_prompt='Generate daily job search strategy'
)
```

### 3. Dependency Management

Replace manual dependency passing with Pydantic-AI's dependency injection:

```python
@dataclass
class JobSearchDependencies:
    storage: GCSManager
    db_session: Session
    recruiter_finder: RecruiterFinder
    notifier: Optional[SlackNotifier] = None

@strategy_agent.tool
async def search_jobs(
    ctx: RunContext[JobSearchDependencies],
    query: str,
    limit: int = 5
) -> list[JobMatch]:
    """Search for jobs matching query"""
    return await search_linkedin_jobs(query, limit=limit)
```

## Implementation Steps

1. **Setup & Dependencies**
   ```bash
   pip install pydantic-ai
   ```

2. **Model Migration**
   - Convert all structured responses to Pydantic models
   - Define enums for common string fields
   - Add proper field validation

3. **Agent Creation**
   - Create agents for core functionality
   - Convert tools to use decorator pattern
   - Set up dependency injection

4. **Testing**
   - Update tests to use Pydantic-AI's testing utilities
   - Add monitoring for token usage
   - Validate outputs match expected models

5. **Documentation**
   - Update API documentation
   - Add examples of new model usage
   - Document common patterns

## Benefits

1. **Code Quality**
   - Reduced boilerplate
   - Better type safety
   - Clearer interfaces

2. **Development Experience**
   - Better IDE support
   - Easier testing
   - Simpler dependency management

3. **Maintenance**
   - Centralized validation logic
   - Easier to add new features
   - Better error handling

4. **Monitoring**
   - Built-in logging
   - Performance tracking
   - Cost management

## Risks and Mitigation

1. **Learning Curve**
   - Risk: Team needs to learn new patterns
   - Mitigation: Good documentation and examples

2. **Migration Effort**
   - Risk: Large codebase changes needed
   - Mitigation: Gradual migration, one component at a time

3. **Integration Issues**
   - Risk: Conflicts with existing code
   - Mitigation: Thorough testing during migration

## Timeline

1. Week 1: Setup and initial model migration
2. Week 2: Core job analysis and search functionality
3. Week 3: Strategy generation and tools
4. Week 4: Testing and monitoring
5. Week 5: Documentation and cleanup

## Getting Started

1. Install Pydantic-AI:
```bash
pip install pydantic-ai
```

2. Create your first agent:
```python
from pydantic_ai import Agent
from pydantic import BaseModel

class JobSearchResult(BaseModel):
    title: str
    company: str
    match_score: float

agent = Agent(
    'google-gla:gemini-1.5-pro',
    output_type=JobSearchResult
)
```

3. Run your first analysis:
```python
result = await agent.run("Analyze this job posting...", deps=dependencies)
print(result.output)  # Typed JobSearchResult
```

## Resources

- [Pydantic-AI Documentation](https://ai.pydantic.dev/)
- [Examples Repository](https://github.com/pydantic/pydantic-ai/tree/main/examples)
- [API Reference](https://ai.pydantic.dev/api/agent/)
