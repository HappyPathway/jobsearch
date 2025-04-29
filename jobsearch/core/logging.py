"""Logging configuration for the jobsearch package.

This module provides a standardized logging configuration for the entire
jobsearch package. It ensures consistent log formatting and behavior
across all components of the application.

Example:
    ```python
    from jobsearch.core.logging import setup_logging
    
    logger = setup_logging('my_module')
    logger.info('This is an info message')
    logger.error('This is an error message')
    ```
"""
import logging

def setup_logging(logger_name: str) -> logging.Logger:
    """Set up standardized logging configuration.
    
    Creates and configures a logger with consistent formatting and behavior.
    If the logger already has handlers, it will not be reconfigured.
    
    Args:
        logger_name: The name for the logger, typically the module name
    
    Returns:
        A configured logger instance
    """
    # Get or create logger
    logger = logging.getLogger(logger_name)
    
    # Only configure if it hasn't been configured already
    if not logger.handlers:
        # Set default level
        logger.setLevel(logging.INFO)
        
        # Create console handler
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Add formatter to handler
        handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(handler)

    return logger

# Make sure the root logger has a handler to avoid "no handler found" warnings
logging.getLogger().addHandler(logging.NullHandler())