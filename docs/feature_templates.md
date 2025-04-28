# Feature Template Architecture

## Overview

This document outlines the architecture for integrating Jinja2 templates with our feature-based agent system, providing a clear separation between code and configuration while maintaining type safety and reusability.

## Directory Structure

```
jobsearch/
├── core/
│   ├── feature.py          # Base feature class
│   └── template.py         # Template management utilities
├── features/
│   ├── job_search/
│   │   ├── feature.py      # JobSearchFeature implementation
│   │   └── templates/
│   │       ├── search.j2   # Job search prompts
│   │       ├── analyze.j2  # Job analysis prompts
│   │       └── score.j2    # Job scoring prompts
│   ├── document_generation/
│   │   ├── feature.py
│   │   └── templates/
│   │       ├── resume.j2
│   │       └── cover_letter.j2
│   └── strategy_generation/
│       ├── feature.py
│       └── templates/
           ├── daily.j2
           └── weekly.j2
```

## Core Components

### BaseFeature Class Enhancements

```python
class BaseFeature:
    def __init__(self, name: str):
        self.name = name
        self.template_loader = self._init_template_loader()
        self.templates = self._load_templates()
        
    def _init_template_loader(self):
        # Set up Jinja2 environment with:
        # - Custom filters
        # - Error handling
        # - Template inheritance
        # - Auto-escaping
        
    def _load_templates(self):
        # Load and validate all templates in the feature's template directory
        # Register them with type hints for better IDE support
```

### Template Management

```python
class TemplateManager:
    """Handles template loading, validation, and rendering."""
    
    def __init__(self, feature_name: str):
        self.feature_name = feature_name
        self.template_dir = self._get_template_dir()
        self.env = self._create_environment()
        
    def render(self, 
        template_name: str,
        context: dict,
        validate_schema: Optional[Type[BaseModel]] = None
    ) -> str:
        # Render template with context
        # Optionally validate against Pydantic schema
```

## Feature Implementation Pattern

Each feature should:

1. Define Template Schemas:
```python
class JobSearchPrompts(BaseModel):
    search_query: str
    analysis: str
    scoring: str
```

2. Create Templates:
```jinja
{# search.j2 #}
You are analyzing the following job posting for {{ role_type }}:
Title: {{ job.title }}
Company: {{ job.company }}

Please evaluate:
{% for criterion in criteria %}
- {{ criterion }}
{% endfor %}
```

3. Implement Feature Class:
```python
class JobSearchFeature(BaseFeature):
    def __init__(self):
        super().__init__(name="job_search")
        self.prompts = self.templates.get_prompts(JobSearchPrompts)
        
    async def analyze_job(self, job: Dict):
        context = self._prepare_context(job)
        prompt = self.prompts.analysis.render(context)
        return await self.agent.run(prompt)
```

## Template Context

Templates will have access to:

1. Feature-specific context
2. Core components (database, storage, etc.)
3. Custom filters and functions
4. Environment variables
5. Global configuration

## Type Safety

1. Template Parameters:
```python
class TemplateContext(BaseModel):
    """Define expected template parameters."""
    job: JobModel
    criteria: List[str]
    role_type: str
```

2. Template Output:
```python
class AnalysisResult(BaseModel):
    """Define expected template output."""
    score: float
    reasons: List[str]
    requirements: List[str]
```

## Error Handling

1. Template Validation:
- Syntax checking at load time
- Schema validation of context
- Output type validation

2. Runtime Validation:
- Missing variables
- Type mismatches
- Invalid output formats

## Benefits

1. Separation of Concerns:
- Code handles logic and flow
- Templates handle content and formatting
- Configuration manages settings

2. Maintainability:
- Easy to update prompts without code changes
- Version control of templates
- Clear documentation

3. Reusability:
- Share templates across features
- Template inheritance
- Common components

4. Type Safety:
- Validated inputs and outputs
- IDE support
- Runtime checks

## Implementation Plan

1. Core Components:
- [ ] Enhance BaseFeature class
- [ ] Create TemplateManager
- [ ] Add type definitions

2. Feature Updates:
- [ ] Convert existing prompts to templates
- [ ] Update feature implementations
- [ ] Add template validation

3. Documentation:
- [ ] Template writing guide
- [ ] Feature implementation guide
- [ ] Best practices

4. Testing:
- [ ] Template validation tests
- [ ] Integration tests
- [ ] Performance testing

## Migration Strategy

1. For each feature:
- Create templates directory
- Convert prompts to templates
- Update feature class
- Add tests
- Document changes

2. Validation:
- Test template loading
- Verify prompt rendering
- Check type safety
- Measure performance

## Future Enhancements

1. Template Management:
- Hot reloading
- Version control
- A/B testing

2. Development Tools:
- Template linting
- Schema generation
- Documentation generation

3. Monitoring:
- Template usage metrics
- Performance tracking
- Error reporting

## Questions to Consider

1. Template Organization:
- How to structure complex templates?
- When to split vs combine templates?
- How to handle variations?

2. Performance:
- Template caching strategy?
- Rendering optimization?
- Memory management?

3. Maintenance:
- Version control strategy?
- Review process?
- Testing requirements?

## Conclusion

This architecture provides a robust foundation for managing AI prompts as templates, ensuring:
- Clear separation of concerns
- Type safety
- Maintainability
- Reusability
- Performance

The next step is to implement the core components and migrate one feature as a proof of concept.
