"""Centralized monitoring configuration for all LLM interactions."""
import os
from typing import Optional
from pydantic_ai.monitoring import LogfireMonitoring
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from jobsearch.core.logging import setup_logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = setup_logging("monitoring")

class MonitoringConfig:
    """Singleton class to manage monitoring configuration."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize monitoring configuration."""
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.slack_token = os.getenv("SLACK_API_TOKEN")
        self.slack_channel = os.getenv("SLACK_ALERT_CHANNEL", "#job-search-alerts")
        
        # Initialize Logfire monitoring
        self.monitoring = LogfireMonitoring(
            project_id="jobsearch-ai",
            environment=self.environment,
            service_name="job-search"
        )
        
        # Configure monitoring for different components
        self._setup_monitoring()
    
    def _setup_monitoring(self):
        """Configure monitoring alerts for different components."""
        # Job Search monitoring
        self.monitoring.set_alert(
            name="job_search_error_rate",
            condition="error_rate > 0.05",
            window="5m",
            channels=["slack"],
            alert_message="High error rate in job search: {error_rate:.1%}"
        )
        
        # Token usage monitoring
        self.monitoring.set_alert(
            name="high_token_usage",
            condition="hourly_tokens > 1000000",
            window="60m",
            channels=["slack"],
            alert_message="High token usage: {hourly_tokens:,} tokens in the last hour"
        )
        
        # Performance monitoring
        self.monitoring.set_alert(
            name="high_latency",
            condition="avg_latency > 5.0",
            window="15m",
            channels=["slack"],
            alert_message="High latency detected: {avg_latency:.1f}s average"
        )
        
        # Cost monitoring
        self.monitoring.set_alert(
            name="cost_spike",
            condition="hourly_cost > 10.0",  # $10 per hour threshold
            window="60m",
            channels=["slack"],
            alert_message="Cost spike detected: ${hourly_cost:.2f} in the last hour"
        )

    def get_instrumentation_config(self, feature_name: str) -> dict:
        """Get instrumentation configuration for a feature.
        
        Args:
            feature_name: Name of the feature (e.g., 'job_search', 'document_gen')
            
        Returns:
            Dict with instrumentation settings
        """
        return {
            'track_tokens': True,
            'track_latency': True,
            'track_errors': True,
            'track_retries': True,
            'track_success_rate': True,
            'feature': feature_name
        }

    def get_generation_config(self, feature_name: str) -> dict:
        """Get generation configuration for a feature.
        
        Args:
            feature_name: Name of the feature
            
        Returns:
            Dict with generation settings
        """
        # Default configurations for different features
        configs = {
            'job_search': {
                'temperature': 0.2,
                'max_output_tokens': 1000,
            },
            'document_gen': {
                'temperature': 0.3,
                'max_output_tokens': 2000,
            },
            'strategy_gen': {
                'temperature': 0.4,
                'max_output_tokens': 1500,
            }
        }
        
        return configs.get(feature_name, {
            'temperature': 0.3,
            'max_output_tokens': 1000,
        })

monitoring_config = MonitoringConfig()
