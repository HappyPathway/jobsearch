"""Logging configuration for the jobsearch package."""
import logging

def setup_logging(logger_name: str) -> logging.Logger:
    """Set up logging configuration."""
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