"""Slack monitoring configuration for Logfire integration."""
import os
from typing import Optional, List
from pydantic import BaseModel
from pydantic_ai.monitoring import LogfireMonitoring
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class SlackAlert(BaseModel):
    """Configuration for a Slack alert."""
    channel: str
    threshold: float
    window_minutes: int
    message_template: str

class SlackMonitoring:
    """Handles integration between Logfire and Slack."""
    
    def __init__(
        self,
        slack_token: str,
        default_channel: str = "#job-search-alerts",
        environment: str = "production"
    ):
        self.client = WebClient(token=slack_token)
        self.default_channel = default_channel.lstrip('#')  # Remove # for consistency
        self.environment = environment
        
    def ensure_channel_exists(self, channel_name: str) -> str:
        """Ensure a channel exists, create it if it doesn't.
        
        Args:
            channel_name: Channel name with or without #
            
        Returns:
            Channel ID
        """
        channel_name = channel_name.lstrip('#')
        
        try:
            # Try to find existing channel
            response = self.client.conversations_list(types="public_channel")
            for channel in response["channels"]:
                if channel["name"] == channel_name:
                    return channel["id"]
            
            # Channel not found, create it
            logger.info(f"Creating new Slack channel: #{channel_name}")
            response = self.client.conversations_create(
                name=channel_name,
                is_private=False
            )
            return response["channel"]["id"]
            
        except SlackApiError as e:
            if "name_taken" in str(e):
                # Channel exists but we couldn't see it
                logger.warning(f"Channel #{channel_name} exists but bot cannot access it")
                return None
            elif "not_allowed_token_type" in str(e):
                logger.error("Bot token doesn't have permission to create channels. Need channels:manage scope")
                return None
            else:
                logger.error(f"Error managing Slack channel: {str(e)}")
                return None
        self.monitoring = LogfireMonitoring(
            project_id="jobsearch-ai",
            environment=environment,
            service_name="job-search"
        )
        
    def setup_error_rate_alert(
        self,
        channel: Optional[str] = None,
        threshold: float = 0.05,  # 5% error rate
        window_minutes: int = 5
    ):
        """Configure alert for high error rates."""
        alert_config = SlackAlert(
            channel=channel or self.default_channel,
            threshold=threshold,
            window_minutes=window_minutes,
            message_template=(
                ":warning: *High Error Rate Alert*\n"
                "Environment: {environment}\n"
                "Error Rate: {error_rate:.1%}\n"
                "Time Window: {window} minutes\n"
                "Most Common Errors:\n{error_breakdown}"
            )
        )
        
        self.monitoring.set_alert(
            name="high_error_rate",
            condition=f"error_rate > {threshold}",
            window=f"{window_minutes}m",
            channels=["slack"],
            handler=lambda data: self._send_error_alert(data, alert_config)
        )

    def setup_cost_alert(
        self,
        channel: Optional[str] = None,
        daily_budget: float = 50.0,  # $50 per day
        window_minutes: int = 60
    ):
        """Configure alert for unusual cost spikes."""
        alert_config = SlackAlert(
            channel=channel or self.default_channel,
            threshold=daily_budget,
            window_minutes=window_minutes,
            message_template=(
                ":moneybag: *Cost Alert*\n"
                "Environment: {environment}\n"
                "Current Spend: ${current_spend:.2f}\n"
                "Budget: ${budget:.2f}\n"
                "Time Window: {window} minutes\n"
                "Cost Breakdown:\n{cost_breakdown}"
            )
        )
        
        self.monitoring.set_alert(
            name="cost_spike",
            condition=f"daily_cost > {daily_budget}",
            window=f"{window_minutes}m",
            channels=["slack"],
            handler=lambda data: self._send_cost_alert(data, alert_config)
        )

    def setup_performance_alert(
        self,
        channel: Optional[str] = None,
        latency_threshold: float = 5.0,  # 5 seconds
        window_minutes: int = 15
    ):
        """Configure alert for performance issues."""
        alert_config = SlackAlert(
            channel=channel or self.default_channel,
            threshold=latency_threshold,
            window_minutes=window_minutes,
            message_template=(
                ":snail: *Performance Alert*\n"
                "Environment: {environment}\n"
                "Average Latency: {latency:.1f}s\n"
                "Threshold: {threshold:.1f}s\n"
                "Time Window: {window} minutes\n"
                "Endpoint Breakdown:\n{latency_breakdown}"
            )
        )
        
        self.monitoring.set_alert(
            name="high_latency",
            condition=f"avg_latency > {latency_threshold}",
            window=f"{window_minutes}m",
            channels=["slack"],
            handler=lambda data: self._send_performance_alert(data, alert_config)
        )

    def setup_token_usage_alert(
        self,
        channel: Optional[str] = None,
        token_threshold: int = 1000000,  # 1M tokens
        window_minutes: int = 60
    ):
        """Configure alert for high token usage."""
        alert_config = SlackAlert(
            channel=channel or self.default_channel,
            threshold=float(token_threshold),
            window_minutes=window_minutes,
            message_template=(
                ":chart_with_upwards_trend: *Token Usage Alert*\n"
                "Environment: {environment}\n"
                "Token Usage: {tokens:,}\n"
                "Threshold: {threshold:,}\n"
                "Time Window: {window} minutes\n"
                "Usage Breakdown:\n{token_breakdown}"
            )
        )
        
        self.monitoring.set_alert(
            name="high_token_usage",
            condition=f"token_count > {token_threshold}",
            window=f"{window_minutes}m",
            channels=["slack"],
            handler=lambda data: self._send_token_alert(data, alert_config)
        )

    def _send_error_alert(self, data: dict, config: SlackAlert):
        """Send error rate alert to Slack."""
        error_breakdown = "\n".join([
            f"- {error}: {count} occurrences"
            for error, count in data.get("error_breakdown", {}).items()
        ])
        
        message = config.message_template.format(
            environment=self.environment,
            error_rate=data["error_rate"],
            window=config.window_minutes,
            error_breakdown=error_breakdown or "No error details available"
        )
        
        self._send_message(config.channel, message)

    def _send_cost_alert(self, data: dict, config: SlackAlert):
        """Send cost alert to Slack."""
        cost_breakdown = "\n".join([
            f"- {feature}: ${cost:.2f}"
            for feature, cost in data.get("cost_breakdown", {}).items()
        ])
        
        message = config.message_template.format(
            environment=self.environment,
            current_spend=data["current_spend"],
            budget=config.threshold,
            window=config.window_minutes,
            cost_breakdown=cost_breakdown or "No cost breakdown available"
        )
        
        self._send_message(config.channel, message)

    def _send_performance_alert(self, data: dict, config: SlackAlert):
        """Send performance alert to Slack."""
        latency_breakdown = "\n".join([
            f"- {endpoint}: {latency:.1f}s"
            for endpoint, latency in data.get("latency_breakdown", {}).items()
        ])
        
        message = config.message_template.format(
            environment=self.environment,
            latency=data["avg_latency"],
            threshold=config.threshold,
            window=config.window_minutes,
            latency_breakdown=latency_breakdown or "No latency breakdown available"
        )
        
        self._send_message(config.channel, message)

    def _send_token_alert(self, data: dict, config: SlackAlert):
        """Send token usage alert to Slack."""
        token_breakdown = "\n".join([
            f"- {feature}: {tokens:,} tokens"
            for feature, tokens in data.get("token_breakdown", {}).items()
        ])
        
        message = config.message_template.format(
            environment=self.environment,
            tokens=data["token_count"],
            threshold=int(config.threshold),
            window=config.window_minutes,
            token_breakdown=token_breakdown or "No token breakdown available"
        )
        
        self._send_message(config.channel, message)

    def _send_message(self, channel: str, message: str):
        """Send a message to Slack channel."""
        try:
            # Ensure channel exists first
            channel = channel.lstrip('#')
            channel_id = self.ensure_channel_exists(channel)
            
            if not channel_id:
                logger.error(f"Cannot send message - channel #{channel} is not accessible")
                return
                
            self.client.chat_postMessage(
                channel=f"#{channel}",
                text=message,
                unfurl_links=False,
                unfurl_media=False
            )
        except SlackApiError as e:
            error_message = e.response['error']
            logger.error(f"Error sending message to Slack: {error_message}")
            
            if "not_in_channel" in error_message:
                try:
                    # Try to join the channel
                    self.client.conversations_join(channel=channel_id)
                    # Retry sending message
                    self.client.chat_postMessage(
                        channel=f"#{channel}",
                        text=message,
                        unfurl_links=False,
                        unfurl_media=False
                    )
                except SlackApiError as join_error:
                    logger.error(f"Could not join channel: {str(join_error)}")
