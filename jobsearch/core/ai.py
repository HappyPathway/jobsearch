"""Core AI functionality with secure secrets and monitoring."""
import os
from typing import Any, Dict, Optional, Type, Union
import google.generativeai as genai
from pydantic import BaseModel
from pydantic_ai import Agent, Prompt
from pydantic_ai.monitoring import LogfireMonitoring

from jobsearch.core.secrets import secret_manager
from jobsearch.core.logging import setup_logger
from jobsearch.core.monitoring_config import monitoring_config

logger = setup_logger('core_ai')

def configure_gemini():
    """Configure Gemini API with secure credentials."""
    api_key = secret_manager.get_secret('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("Could not retrieve Gemini API key from Secret Manager")
    genai.configure(api_key=api_key)

class AIEngine:
    """Core AI engine with monitoring and type safety."""
    
    def __init__(self, feature_name: str = 'default'):
        """Initialize the AI engine.
        
        Args:
            feature_name: Name of the feature using the engine
        """
        self.feature_name = feature_name
        self.instrumentation = monitoring_config.get_instrumentation_config(feature_name)
        
        # Configure monitoring
        self.monitoring = LogfireMonitoring(
            project_id="jobsearch-ai",
            environment=os.getenv("ENVIRONMENT", "development"),
            service_name=feature_name
        )
        
        # Configure Gemini
        configure_gemini()
    
    def get_agent(
        self,
        model: str = 'gemini-1.5-pro',
        output_type: Optional[Type[BaseModel]] = None
    ) -> Agent:
        """Get a monitored AI agent.
        
        Args:
            model: Model to use
            output_type: Expected output type
            
        Returns:
            Configured Agent instance
        """
        return Agent(
            model=model,
            output_type=output_type,
            monitoring=self.monitoring,
            instrumentation=self.instrumentation
        )
    
    def get_prompt(
        self,
        template: str,
        example: Optional[Union[Dict, BaseModel]] = None
    ) -> Prompt:
        """Get a monitored prompt.
        
        Args:
            template: Prompt template
            example: Optional example data
            
        Returns:
            Configured Prompt instance
        """
        return Prompt(
            template=template,
            example=example,
            monitoring=self.monitoring,
            instrumentation=self.instrumentation
        )
        
    async def generate(
        self,
        prompt: str,
        output_type: Type[BaseModel],
        example: Optional[Dict[str, Any]] = None,
        max_retries: int = 3
    ) -> Optional[BaseModel]:
        """Generate content with monitoring and error handling.
        
        Args:
            prompt: The prompt to use
            output_type: Expected output type
            example: Optional example data
            max_retries: Maximum retry attempts
            
        Returns:
            Generated content or None on failure
        """
        agent = self.get_agent(output_type=output_type)
        
        for attempt in range(max_retries):
            try:
                return await agent.generate(
                    prompt=prompt,
                    example=example,
                    generation_config=monitoring_config.get_generation_config(self.feature_name)
                )
                
            except Exception as e:
                logger.error(
                    f"Generation error in {self.feature_name} "
                    f"(attempt {attempt + 1}/{max_retries}): {str(e)}"
                )
                if attempt == max_retries - 1:
                    return None
    
    async def generate_text(
        self,
        prompt: str,
        max_length: Optional[int] = None,
        max_retries: int = 3
    ) -> Optional[str]:
        """Generate free-form text with monitoring.
        
        Args:
            prompt: The prompt to use
            max_length: Optional maximum length
            max_retries: Maximum retry attempts
            
        Returns:
            Generated text or None on failure
        """
        agent = self.get_agent()
        
        for attempt in range(max_retries):
            try:
                return await agent.generate_text(
                    prompt=prompt,
                    max_length=max_length,
                    generation_config=monitoring_config.get_generation_config(self.feature_name)
                )
                
            except Exception as e:
                logger.error(
                    f"Text generation error in {self.feature_name} "
                    f"(attempt {attempt + 1}/{max_retries}): {str(e)}"
                )
                if attempt == max_retries - 1:
                    return None

# Global instance
ai_engine = AIEngine()
