"""Example of a properly documented Python module for auto-generation.

This module shows proper documentation techniques for working with documentation
generators like Sphinx, mkdocstrings, or pydoc-markdown.

The module-level docstring provides a general overview of the module's purpose
and functionality.

Example:
    ```python
    from jobsearch.core.example_doc import ExampleClass
    
    example = ExampleClass(name="test")
    result = example.process_data({"key": "value"})
    ```

Attributes:
    DEFAULT_CONFIG (Dict[str, Any]): Default configuration settings for the module.
    MAX_RETRIES (int): Maximum number of retry attempts for operations.
"""

from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
import json
import logging

# Module level constants
DEFAULT_CONFIG = {
    "timeout": 30,
    "cache_size": 1000,
    "rate_limit": 1.0
}

MAX_RETRIES = 3

logger = logging.getLogger(__name__)

class ExampleClass:
    """A demonstration class for documentation generation.
    
    This class shows how to properly document classes, methods, and attributes
    for automatic documentation generation.
    
    Args:
        name (str): The name for this instance.
        config (Optional[Dict[str, Any]]): Configuration options.
        timeout (int, optional): Request timeout in seconds. Defaults to 30.
    
    Attributes:
        name (str): The name of this instance.
        created_at (datetime): When the instance was created.
        retry_count (int): Current retry count.
    
    Note:
        This class uses Google-style docstrings which work well with various
        documentation generators.
    """
    
    def __init__(
        self, 
        name: str, 
        config: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ):
        """Initialize the ExampleClass instance.
        
        Args:
            name: The name for this instance.
            config: Configuration options.
            timeout: Request timeout in seconds.
        """
        self.name = name
        self.config = config or DEFAULT_CONFIG
        self.timeout = timeout
        self.created_at = datetime.now()
        self.retry_count = 0
    
    def process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input data and return transformed results.
        
        This method demonstrates documentation of more complex functionality
        with parameters and return values.
        
        Args:
            data: The input data to process.
            
        Returns:
            Dict containing processed data with added metadata.
            
        Raises:
            ValueError: If the input data is empty.
            KeyError: If required keys are missing from input data.
            
        Example:
            ```python
            processor = ExampleClass("data_processor")
            result = processor.process_data({"input": "test"})
            print(result)  # {'input': 'test', 'processed_by': 'data_processor', 'timestamp': '...'}
            ```
        """
        if not data:
            raise ValueError("Input data cannot be empty")
            
        # Process the data (example implementation)
        result = data.copy()
        result.update({
            "processed_by": self.name,
            "timestamp": datetime.now().isoformat()
        })
        
        return result
        
    @property
    def config_summary(self) -> str:
        """Get a summary of the current configuration.
        
        Returns:
            String representation of the current configuration.
        """
        return json.dumps(self.config, indent=2)
        
    @classmethod
    def from_json(cls, json_data: str) -> 'ExampleClass':
        """Create a new instance from JSON data.
        
        This demonstrates documenting a class method that returns an
        instance of the class.
        
        Args:
            json_data: JSON string containing configuration data.
            
        Returns:
            A new ExampleClass instance configured with the JSON data.
            
        Raises:
            json.JSONDecodeError: If the input is not valid JSON.
        """
        data = json.loads(json_data)
        return cls(
            name=data.get("name", "default"),
            config=data.get("config")
        )
        
    def __str__(self) -> str:
        """Return string representation of the instance.
        
        Returns:
            String with the instance name and creation time.
        """
        return f"ExampleClass(name={self.name}, created={self.created_at})"


def utility_function(input_value: str, options: Optional[List[str]] = None) -> Tuple[bool, str]:
    """A standalone utility function with detailed documentation.
    
    Demonstrates documentation for a module-level function.
    
    Args:
        input_value: The primary input string to process.
        options: Optional list of processing options.
        
    Returns:
        A tuple containing:
          - success flag (bool): Whether the operation succeeded
          - result (str): The processing result or error message
        
    Raises:
        ValueError: If input_value is empty.
    """
    if not input_value:
        raise ValueError("Input value cannot be empty")
        
    # Example processing
    options = options or ["default"]
    result = f"Processed '{input_value}' with options: {', '.join(options)}"
    
    return True, result
