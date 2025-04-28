# Getting Structured Output from Gemini

This guide covers best practices for obtaining structured output from Gemini API, specifically focused on our job search automation use cases.

## Overview

While Gemini generates unstructured text by default, our application requires structured responses for automated processing. There are two main approaches to getting structured output:

1. Schema in prompt (text-based)
2. Schema through model configuration (programmatic)

## Current Implementation

Our `StructuredPrompt` class in `jobsearch/core/ai.py` currently uses the text-based approach. Here's how we can improve it using the latest best practices.

## Best Practices

### 1. Using Pydantic Models

Instead of describing schemas in text, define them as Pydantic models:

```python
from pydantic import BaseModel
from typing import List

class DailyStrategy(BaseModel):
    title: str
    primary_goal: str
    secondary_goals: List[str]
    metrics: dict[str, int]
    
class JobStrategy(BaseModel):
    daily_focus: DailyStrategy
    weekly_focus: str
    recruiters: dict[str, List[dict]] = {}
```

### 2. Model Configuration

Configure the model with explicit schema and MIME type:

```python
response = model.generate_content(
    prompt="Generate a job search strategy...",
    config={
        'response_mime_type': 'application/json',
        'response_schema': JobStrategy,
    }
)
```

### 3. Property Ordering

To improve output consistency, specify property ordering:

```python
config = {
    'response_mime_type': 'application/json',
    'response_schema': {
        'type': 'object',
        'properties': {
            'daily_focus': {...},
            'weekly_focus': {...},
            'recruiters': {...}
        },
        'propertyOrdering': ['daily_focus', 'weekly_focus', 'recruiters']
    }
}
```

### 4. Using Enums for Constrained Choices

For fields with fixed options, use enums:

```python
from enum import Enum

class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class JobApplication(BaseModel):
    title: str
    company: str
    priority: Priority
```

## Enhanced JSON Cleaning

Our current JSON cleaning can be improved with these regex patterns:

```python
def clean_json_string(json_str: str) -> str:
    # Remove markdown formatting
    json_str = re.sub(r'^```.*?\n', '', json_str)
    json_str = re.sub(r'\n```$', '', json_str)
    
    # Extract JSON if mixed with other text
    if match := re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', json_str):
        json_str = match.group(1)
    
    # Quote unquoted property names
    json_str = re.sub(r'(?<={|,)\s*([a-zA-Z_]\w*)\s*:', r'"\1":', json_str)
    
    # Fix common JSON issues
    json_str = re.sub(r'(?<!["\\])"(?![":{},\s\]])', '\\"', json_str)  # Escape quotes
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)  # Remove trailing commas
    json_str = re.sub(r'}\s*{', '},{', json_str)  # Fix object separation
    
    # Handle special values
    json_str = re.sub(r':\s*(true|false|null|\d+|\d*\.\d+)\s*([,}])', r':"\1"\2', json_str)
    
    return json_str.strip()
```

## Example Usage

Here's how to use these patterns in our code:

```python
from jobsearch.core.ai import StructuredPrompt

# Define expected structure
strategy_structure = {
    'daily_focus': {
        'title': str,
        'primary_goal': str,
        'secondary_goals': [str],
    },
    'weekly_focus': str,
}

# Create example data matching structure
example_data = {
    'daily_focus': {
        'title': 'Focus on Tech Leadership Roles',
        'primary_goal': 'Apply to senior engineering positions',
        'secondary_goals': ['Update LinkedIn profile', 'Research target companies'],
    },
    'weekly_focus': 'Building network in cloud architecture community',
}

# Get structured response
prompt_helper = StructuredPrompt()
result = prompt_helper.get_structured_response(
    prompt="Generate a job search strategy...",
    expected_structure=strategy_structure,
    example_data=example_data
)
```

## Validation and Error Handling

When using Pydantic models with Gemini:
- Pydantic validators are not yet supported
- ValidationErrors are suppressed
- The `.parsed` property may be empty/null on validation failures

Best practice is to:
1. Keep models simple
2. Validate critical fields in application code
3. Have fallback values ready for invalid responses

## Further Reading

- [Gemini API Documentation](https://ai.google.dev/gemini-api/docs/structured-output)
- [Pydantic Documentation](https://docs.pydantic.dev/latest/)
