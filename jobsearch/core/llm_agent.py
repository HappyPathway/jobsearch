"""Base agent for LLM interactions using pydantic-ai.

This module provides a standardized base class for all LLM agents in the JobSearch
platform. It uses pydantic-ai for type-safe LLM interactions, with monitoring,
error handling, and structured output generation.

Example:
    ```python
    from jobsearch.core.llm_agent import BaseLLMAgent
    from jobsearch.core.schemas import JobAnalysis
    
    class JobAnalysisAgent(BaseLLMAgent):
        def __init__(self):
            super().__init__(
                feature_name='job_analysis',
                output_type=JobAnalysis
            )
            
        async def analyze_job(self, job_description: str) -> JobAnalysis:
            return await self.generate(
                prompt=f"Analyze this job description: {job_description}",
            )
    ```
"""

import os
import asyncio
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union, Tuple
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelRetry, UnexpectedModelBehavior
from pydantic_ai.usage import UsageLimits

from jobsearch.core.logging import setup_logging
from jobsearch.core.monitoring import setup_monitoring
from jobsearch.core.secrets import secret_manager

# Set up logging and monitoring
logger = setup_logging('llm_agent')
monitoring = setup_monitoring('llm_agent')

# Type variable for output types
T = TypeVar('T')

class BaseLLMAgent(Generic[T]):
    """Base class for all LLM agents in the JobSearch platform.
    
    This class provides standardized methods for interacting with language models
    using pydantic-ai. It handles structured output generation, error handling,
    and monitoring of all LLM interactions.
    
    Attributes:
        feature_name: Name of the feature using this agent
        output_type: Pydantic model for structured output
        model_name: Name of the LLM model to use
        agent: pydantic-ai Agent instance
        monitoring: Monitoring instance for tracking metrics
    """
    
    def __init__(
        self,
        feature_name: str,
        output_type: Optional[Type[BaseModel]] = None,
        model_name: str = 'openai:gpt-4-turbo',
        instructions: Optional[str] = None,
        retries: int = 2
    ):
        """Initialize the agent with configuration.
        
        Args:
            feature_name: Name of the feature using this agent
            output_type: Pydantic model type for structured output
            model_name: Name of the LLM model to use
            instructions: Optional instructions for the agent
            retries: Number of retries for failed generations
        """
        self.feature_name = feature_name
        self.output_type = output_type
        self.model_name = model_name
        self.instructions = instructions
        self.retries = retries
        
        # Set up monitoring
        self.monitoring = setup_monitoring(f'llm_{feature_name}')
        
        # Configure and create the agent
        self._setup_agent()
        
    def _setup_agent(self) -> None:
        """Configure and create the pydantic-ai agent."""
        try:
            self.monitoring.increment('setup_agent')
            
            # Create the agent with proper configuration
            self.agent = Agent(
                self.model_name,
                output_type=self.output_type,
                deps_type=None,  # No dependencies by default
                instructions=self.instructions,
                retries=self.retries
            )
            
            self.monitoring.track_success('setup_agent')
            logger.info(f"Agent for {self.feature_name} initialized successfully")
            
        except Exception as e:
            self.monitoring.track_error('setup_agent', str(e))
            logger.error(f"Error setting up agent: {str(e)}")
            raise
    
    async def generate(
        self,
        prompt: str,
        output_type: Optional[Type[BaseModel]] = None,
        model_settings: Optional[Dict[str, Any]] = None,
        usage_limits: Optional[UsageLimits] = None,
        message_history: Optional[list] = None,
        expected_type: Optional[Type[BaseModel]] = None,  # For backward compatibility
        example_data: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Generate a response from the language model.
        
        Args:
            prompt: The input prompt for the model
            output_type: Override the default output type if needed
            model_settings: Optional settings for the model (temperature, etc.)
            usage_limits: Optional usage limits for token consumption
            message_history: Optional history of previous messages
            expected_type: Alias for output_type (for backward compatibility)
            example_data: Example data to include in the prompt for better structured output
        
        Returns:
            Structured output of the type specified in output_type or during initialization
        
        Raises:
            Exception: If there is an error during generation
        """
        final_output_type = output_type or expected_type or self.output_type
        metric_name = f"generate_{self.feature_name}"
        
        try:
            self.monitoring.increment(metric_name)
            logger.info(f"Generating response with {self.model_name}")
            
            # If example data is provided, enhance the prompt
            enhanced_prompt = prompt
            if example_data and final_output_type:
                enhanced_prompt = f"{prompt}\n\nExpected output format:\n{example_data}"
            
            # Run the agent with the provided inputs
            result = await self.agent.run(
                user_prompt=enhanced_prompt,
                output_type=final_output_type,
                model_settings=model_settings,
                usage_limits=usage_limits,
                message_history=message_history
            )
            
            # Log usage statistics
            usage = result.usage()
            logger.info(
                f"Generation complete: {usage.total_tokens} tokens "
                f"({usage.request_tokens} request, {usage.response_tokens} response)"
            )
            
            self.monitoring.track_success(metric_name)
            self.monitoring.track_tokens(
                feature=self.feature_name,
                request_tokens=usage.request_tokens,
                response_tokens=usage.response_tokens,
                model=self.model_name
            )
            
            return result.output
            
        except UnexpectedModelBehavior as e:
            error_type = "model_error"
            self.monitoring.track_error(metric_name, f"{error_type}: {str(e)}")
            logger.error(f"Model error during generation: {str(e)}")
            raise
            
        except Exception as e:
            self.monitoring.track_error(metric_name, str(e))
            logger.error(f"Error during generation: {str(e)}")
            raise
    
    def add_tool(
        self,
        func: callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        retries: Optional[int] = None
    ) -> callable:
        """Add a tool function to the agent.
        
        Args:
            func: The function to add as a tool
            name: Optional custom name for the tool
            description: Optional description of the tool
            retries: Optional number of retries for the tool
            
        Returns:
            The decorated function
        """
        return self.agent.tool(
            name=name,
            description=description,
            retries=retries or self.retries
        )(func)
        
    def add_system_prompt(self, func: callable) -> callable:
        """Add a system prompt function to the agent.
        
        Args:
            func: Function that returns a system prompt string
            
        Returns:
            The decorated function
        """
        return self.agent.system_prompt(func)
    
    def run_sync(
        self, 
        prompt: str,
        **kwargs
    ) -> Any:
        """Synchronous version of generate.
        
        Args:
            prompt: Input prompt for the model
            **kwargs: Additional arguments to pass to the agent's run_sync method
            
        Returns:
            The model's output
        """
        result = self.agent.run_sync(prompt, **kwargs)
        return result.output
    
    async def generate_text(
        self,
        prompt: str,
        **kwargs
    ) -> Optional[str]:
        """Generate plain text content without structured output.
        
        This is a convenience method for agents that need to generate
        unstructured text responses (like documents, articles, etc.)
        
        Args:
            prompt: Input prompt for the model
            **kwargs: Additional arguments to pass to the generate method
            
        Returns:
            Generated text as a string, or None if generation fails
        """
        try:
            # Use str as the output type to get plain text
            return await self.generate(prompt=prompt, output_type=str, **kwargs)
        except Exception as e:
            logger.error(f"Error generating text: {str(e)}")
            return None
