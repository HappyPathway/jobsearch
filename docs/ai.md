# AI Module

The AI module provides utilities for structured interaction with language models, primarily focused on getting well-formatted, structured responses from Gemini.

## StructuredPrompt Class

The main component of the AI module is the `StructuredPrompt` class, which helps ensure that responses from the language model are properly structured according to expected schemas.

### Features

- **Structured Response Validation**: Ensures JSON responses match an expected structure
- **Automatic Error Recovery**: Attempts to fix malformed JSON responses
- **Retry Logic**: Automatically retries failed requests with improved prompting
- **JSON Cleaning**: Handles common JSON formatting issues in model outputs

### Usage Example

```python
from jobsearch.core.ai import StructuredPrompt

# Initialize with default settings (Gemini 1.5 Pro)
prompt_helper = StructuredPrompt()

# Define the expected structure
expected_structure = {
    "job_title": str,
    "company": str,
    "skills_required": [str],
    "match_score": int
}

# Example data to guide the model
example_data = {
    "job_title": "Cloud Architect",
    "company": "TechCorp",
    "skills_required": ["Terraform", "AWS", "Kubernetes"],
    "match_score": 85
}

# Get structured response
result = prompt_helper.get_structured_response(
    prompt="Analyze this job posting and extract key information...",
    expected_structure=expected_structure,
    example_data=example_data,
    temperature=0.2
)

if result:
    # Use the structured data
    print(f"Job: {result['job_title']} at {result['company']}")
    print(f"Required skills: {', '.join(result['skills_required'])}")
    print(f"Match score: {result['match_score']}%")
```

### Parameters

- **model_name**: The Gemini model to use (default: 'gemini-1.5-pro')
- **max_retries**: Maximum number of retry attempts for failed responses (default: 3)
- **max_output_tokens**: Maximum output tokens for the model response (default: 2000)

### Methods

#### get_structured_response

```python
def get_structured_response(
    self,
    prompt: str,
    expected_structure: Union[Dict, List],
    example_data: Optional[Union[Dict, List]] = None,
    temperature: float = 0.1
) -> Optional[Any]
```

Gets a structured response from the model with validation and retry logic.

- **prompt**: The base prompt to send to the model
- **expected_structure**: Dictionary or List describing the expected JSON structure
- **example_data**: Optional example of the expected data structure
- **temperature**: Model temperature (default: 0.1 for consistent structured output)
- **Returns**: Parsed JSON data matching the expected structure, or None if failed

### Internal Methods

- **_clean_json_string**: Cleans up common JSON formatting issues
- **_validate_json_structure**: Validates that parsed JSON matches the expected structure

## Integration with Other Modules

The AI module is primarily used by strategy generation components and job analysis tools to extract structured data from job descriptions, generate customized job search strategies, and analyze career data.