"""Base feature class for all jobsearch features."""
from typing import Optional, Type, TypeVar
from pydantic import BaseModel
from ai.pydantic import Agent, AgentConfig, RunContext

from jobsearch.core.logging import setup_logging
from jobsearch.core.storage import GCSManager
from jobsearch.core.database import get_session
from jobsearch.core.monitoring import setup_monitoring

T = TypeVar('T', bound='BaseFeature')

class FeatureContext(BaseModel):
    """Base context class for all features."""
    feature_name: str
    
    def __init__(self, feature_name: str):
        super().__init__(feature_name=feature_name)
        self.logger = setup_logging(feature_name)
        self.storage = GCSManager()
        self.monitoring = setup_monitoring(feature_name)

class BaseFeature:
    """Base class for all jobsearch features.
    
    Each feature should:
    1. Inherit from this class
    2. Define its own Context and Output types
    3. Implement the required methods
    4. Use the provided core components
    
    Example:
        ```python
        class JobSearchFeature(BaseFeature[JobSearchContext, JobSearchOutput]):
            def __init__(self):
                super().__init__(
                    name="job_search",
                    system_prompt="You are a specialized job search assistant..."
                )
        ```
    """
    
    def __init__(
        self,
        name: str,
        system_prompt: str,
        context_type: Optional[Type[FeatureContext]] = None,
        output_type: Optional[Type[BaseModel]] = None,
        model: str = "gemini-pro"
    ):
        """Initialize the feature.
        
        Args:
            name: Feature name for logging and monitoring
            system_prompt: System prompt for the AI agent
            context_type: Optional custom context type
            output_type: Optional custom output type
            model: AI model to use
        """
        self.name = name
        self.context_type = context_type or FeatureContext
        self.context = self.context_type(feature_name=name)
        
        # Set up AI agent
        self.agent = Agent(
            model,
            deps_type=self.context_type,
            output_type=output_type,
            config=AgentConfig(
                system_prompt=system_prompt
            )
        )
        
        # Initialize core components
        self.logger = self.context.logger
        self.storage = self.context.storage
        self.monitoring = self.context.monitoring
        
    async def run(self, *args, **kwargs):
        """Run the feature's main functionality.
        
        This should be implemented by each feature class.
        """
        raise NotImplementedError("Features must implement run()")
    
    def cleanup(self):
        """Clean up any resources.
        
        This should be implemented by features that need cleanup.
        """
        pass
    
    async def __aenter__(self):
        """Allow features to be used as async context managers."""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up when exiting the context."""
        self.cleanup()
        
    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}')"
