# Core Library Building Blocks

## Overview

The `jobsearch/core` library provides foundational building blocks that should be used across all features. These components are designed to be generic, reusable, and maintainable. **Do not create feature-specific implementations of functionality that already exists in the core library.**

## Core Building Blocks

### AI Integration (`core/ai.py`)
- `AIEngine` - Type-safe AI interactions with monitoring
- `StructuredPrompt` - Structured output generation from language models
- Use this for all AI/LLM interactions instead of creating feature-specific implementations

### Web Scraping (`core/web_scraper.py`)
- Generic web scraping with built-in:
  - Rate limiting
  - Caching
  - Retry logic
  - Error handling
- Use this instead of implementing custom scraping logic in features

### Markdown Generation (`core/markdown.py`)
- Generic markdown formatting and generation
- Template-based content generation
- Use this for all markdown content generation needs

### Database (`core/database.py`)
- Central database configuration
- Session management
- Model base classes
- Use this for all database interactions

### Storage (`core/storage.py`)
- Generic cloud storage operations
- File management utilities
- Use this for all file storage needs

### Logging (`core/logging.py`)
- Standardized logging configuration
- Structured logging helpers
- Use this for all logging needs

## Best Practices

### ✅ Do
- Use existing core components as building blocks for new features
- Extend core components if needed, but maintain their generic nature
- Document any extensions or improvements to core components
- Add new generic functionality to core if it could be useful across features

### ❌ Don't
- Create feature-specific versions of core functionality
- Copy and modify core code into feature directories
- Add feature-specific logic to core components
- Bypass core components for similar functionality

## Example: Building a New Feature

Here's how to properly use core building blocks when creating a new feature:

```python
from jobsearch.core.ai import AIEngine
from jobsearch.core.web_scraper import WebScraper
from jobsearch.core.markdown import MarkdownGenerator
from jobsearch.core.storage import GCSManager
from jobsearch.core.logging import setup_logging

# Use core logging
logger = setup_logging('my_feature')

class MyFeature:
    def __init__(self):
        # Use core components as building blocks
        self.ai = AIEngine(feature_name='my_feature')
        self.scraper = WebScraper(rate_limit=1.0)
        self.markdown = MarkdownGenerator()
        self.storage = GCSManager()
    
    async def process_data(self, url: str):
        # Use web scraper for content retrieval
        soup = self.scraper.get_soup(url)
        if not soup:
            return None
            
        # Extract data using scraper helpers
        title = self.scraper.extract_text(soup, 'h1.title')
        description = self.scraper.extract_text(soup, 'div.description')
        
        # Use AI engine for analysis
        analysis = await self.ai.generate(
            prompt=f"Analyze this content:\n{title}\n{description}",
            output_type=MyAnalysisModel
        )
        
        # Generate markdown output
        content = self.markdown.format_header(title, level=1)
        content += self.markdown.format_blockquote(description)
        
        # Store results
        self.storage.save_markdown(f'my_feature/{title}', content)
```

## When to Extend Core

If you find yourself needing functionality that could be useful across features:

1. First, thoroughly review existing core components
2. If the functionality is truly missing, propose additions to core
3. Keep new core components generic and well-documented
4. Follow the existing patterns and standards in core
5. Add appropriate tests for new core functionality

## Questions to Ask

When building a new feature, ask yourself:

1. "Could this functionality be useful in other features?"
2. "Does something similar already exist in core?"
3. "Am I reinventing something that should be generic?"
4. "Should this be a core building block instead of feature-specific?"

Remember: The core library is our foundation. Build upon it, don't duplicate it.
