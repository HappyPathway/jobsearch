"""Monitoring configuration for job search feature."""
import os
from typing import Optional
from jobsearch.core.monitoring import SlackMonitoring

def setup_job_search_monitoring(
    slack_token: Optional[str] = None,
    environment: str = "production",
    alert_channel: Optional[str] = None
) -> SlackMonitoring:
    """Set up monitoring for job search feature with Slack integration.
    
    Args:
        slack_token: Optional Slack bot token. If not provided, uses SLACK_BOT_TOKEN env var
        environment: Environment name (development, staging, production)
        alert_channel: Optional Slack channel for alerts. If not provided, uses SLACK_ALERT_CHANNEL 
            env var or falls back to "#job-search-alerts"
    """
    
    # Get configuration from environment or defaults
    token = slack_token or os.getenv("SLACK_BOT_TOKEN")
    if not token:
        raise ValueError("Slack token must be provided or set in SLACK_BOT_TOKEN environment variable")
    
    channel = alert_channel or os.getenv("SLACK_ALERT_CHANNEL", "#job-search-alerts")
    
    # Initialize monitoring
    monitoring = SlackMonitoring(
        slack_token=token,
        default_channel=channel,
        environment=environment
    )
    
    # Configure alerts specific to job search
    
    # 1. Error rate monitoring
    monitoring.setup_error_rate_alert(
        threshold=0.05,  # Alert on 5% error rate
        window_minutes=5  # Over 5 minute window
    )
    
    # 2. Cost monitoring
    monitoring.setup_cost_alert(
        daily_budget=50.0,  # $50 daily budget
        window_minutes=60  # Check hourly
    )
    
    # 3. Performance monitoring
    monitoring.setup_performance_alert(
        latency_threshold=5.0,  # Alert if average search takes > 5s
        window_minutes=15  # Check every 15 minutes
    )
    
    # 4. Token usage monitoring
    monitoring.setup_token_usage_alert(
        token_threshold=1000000,  # 1M tokens per hour
        window_minutes=60  # Check hourly
    )
    
    return monitoring
