#!/usr/bin/env python3
import os
import json
from pathlib import Path
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime
from dotenv import load_dotenv
from jobsearch.core.logging import setup_logging
from jobsearch.core.database import get_session
from jobsearch.core.models import JobApplication, JobCache
import time

logger = setup_logging('slack_notifier')

# Load environment variables
load_dotenv()

# Slack API tokens and configuration
SLACK_API_TOKEN = os.getenv("SLACK_API_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")
DEFAULT_USERNAME = "Job Search Assistant"
DEFAULT_ICON_EMOJI = ":briefcase:"

# Rate limiting configuration to avoid API throttling
MIN_TIME_BETWEEN_MESSAGES = 1  # seconds


class SlackNotifier:
    """Class to handle Slack notifications for job applications"""
    
    def __init__(self, token=None, channel_id=None, username=None, icon_emoji=None):
        """Initialize the Slack client"""
        self.token = token or SLACK_API_TOKEN
        self.channel_id = channel_id or SLACK_CHANNEL_ID
        self.username = username or DEFAULT_USERNAME
        self.icon_emoji = icon_emoji or DEFAULT_ICON_EMOJI
        self.last_message_time = 0
        
        if not self.token:
            logger.warning("Slack API token not found. Notifications will be disabled.")
            self.client = None
        else:
            self.client = WebClient(token=self.token)
            logger.info(f"Slack notifier initialized for channel {self.channel_id}")
    
    def _rate_limit(self):
        """Enforce rate limiting to avoid API throttling"""
        current_time = time.time()
        time_since_last = current_time - self.last_message_time
        
        if time_since_last < MIN_TIME_BETWEEN_MESSAGES:
            sleep_time = MIN_TIME_BETWEEN_MESSAGES - time_since_last
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
            
        self.last_message_time = time.time()
    
    def send_notification(self, message, blocks=None, thread_ts=None):
        """Send a basic text notification to Slack"""
        if not self.client:
            logger.info(f"Would send notification: {message}")
            return None
            
        try:
            self._rate_limit()
            response = self.client.chat_postMessage(
                channel=self.channel_id,
                text=message,
                blocks=blocks,
                thread_ts=thread_ts,
                username=self.username,
                icon_emoji=self.icon_emoji
            )
            logger.info(f"Notification sent successfully")
            return response["ts"]  # Return timestamp for threading
        except SlackApiError as e:
            error = e.response['error']
            logger.error(f"Error sending Slack notification: {error}")
            
            if error == "channel_not_found":
                print(f"\nERROR: Channel not found: {self.channel_id}")
                print("\nPossible solutions:")
                print("1. Invite the bot to the channel:")
                print("   - Go to the channel in Slack")
                print("   - Type: /invite @JobSearch (or whatever your bot's name is)")
                print("2. For private channels, ensure your bot has groups:write permission")
                print("3. Make sure you're using a channel ID from the same workspace as your bot token")
                print("4. Try creating a new public channel and use that instead\n")
            return None
    
    def upload_file(self, file_path, title=None, initial_comment=None, thread_ts=None):
        """Upload a file to Slack (like resume or cover letter)"""
        if not self.client:
            logger.info(f"Would upload file: {file_path}")
            return None
            
        try:
            self._rate_limit()
            file_path = Path(file_path)
            
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return None
                
            # Create a title if not provided
            if title is None:
                title = f"{file_path.stem} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            response = self.client.files_upload_v2(
                channel=self.channel_id,
                file=str(file_path),
                title=title,
                initial_comment=initial_comment,
                thread_ts=thread_ts
            )
            logger.info(f"File {file_path.name} uploaded successfully")
            return response
        except SlackApiError as e:
            logger.error(f"Error uploading file to Slack: {e.response['error']}")
            return None
    
    def send_job_application_notification(self, job_info, resume_path=None, cover_letter_path=None):
        """Send a notification about a new job application with formatting"""
        # Build a rich message with job details using Slack Block Kit
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📝 New Application Generated",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Company:*\n{job_info['company']}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Position:*\n{job_info['title']}"
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Match Score:*\n{job_info.get('match_score', 'N/A')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Priority:*\n{job_info.get('application_priority', 'low')}"
                    }
                ]
            }
        ]
        
        # Add job URL if available
        if job_info.get('url'):
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{job_info['url']}|View Job Posting>*"
                }
            })
        
        # Add key requirements if available
        if job_info.get('key_requirements'):
            requirements_text = "\n• " + "\n• ".join(job_info.get('key_requirements', []))
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Key Requirements:*{requirements_text}"
                }
            })
            
        # Add a divider
        blocks.append({"type": "divider"})
        
        # Send the formatted message
        message = f"New application generated for {job_info['title']} at {job_info['company']}"
        ts = self.send_notification(message, blocks=blocks)
        
        # Upload the resume and cover letter if available
        if resume_path and Path(resume_path).exists():
            self.upload_file(
                resume_path,
                title=f"Resume for {job_info['title']} at {job_info['company']}",
                thread_ts=ts
            )
        
        if cover_letter_path and Path(cover_letter_path).exists():
            self.upload_file(
                cover_letter_path,
                title=f"Cover Letter for {job_info['title']} at {job_info['company']}",
                thread_ts=ts
            )
            
        return ts
    
    def send_application_status_update(self, job_application, old_status=None):
        """Send notification about a job application status change"""
        job = job_application.job
        
        # Skip if no status change
        if old_status and old_status == job_application.status:
            return None
            
        status_emoji = {
            "documents_generated": "📝",
            "applied": "📤",
            "interview_scheduled": "📅",
            "follow_up": "📞",
            "rejected": "❌",
            "offer": "🎉",
            "accepted": "✅"
        }.get(job_application.status, "ℹ️")
        
        message = f"{status_emoji} Application for {job.title} at {job.company} is now *{job_application.status}*"
        
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
                }
            }
        ]
        
        # Add URL if available
        if job.url:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"<{job.url}|View Job Posting>"
                    }
                ]
            })
        
        return self.send_notification(message, blocks=blocks)
    
    def send_daily_summary(self):
        """Send a daily summary of job applications and their statuses"""
        with get_session() as session:
            # Get all applications, ordered by date
            applications = session.query(JobApplication).join(JobCache).order_by(
                JobApplication.application_date.desc()
            ).all()
            
            if not applications:
                message = "No job applications found in the database."
                return self.send_notification(message)
            
            # Group applications by status
            status_groups = {}
            for app in applications:
                status = app.status
                if status not in status_groups:
                    status_groups[status] = []
                status_groups[status].append(app)
            
            # Build the summary message
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "📊 Job Application Summary",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"As of {datetime.now().strftime('%Y-%m-%d')}, you have *{len(applications)}* job applications."
                    }
                },
                {"type": "divider"}
            ]
            
            # Add sections for each status group
            for status, apps in status_groups.items():
                status_emoji = {
                    "documents_generated": "📝",
                    "applied": "📤",
                    "interview_scheduled": "📅",
                    "follow_up": "📞",
                    "rejected": "❌",
                    "offer": "🎉",
                    "accepted": "✅"
                }.get(status, "ℹ️")
                
                app_list = []
                for app in apps[:5]:  # Limit to 5 per status to avoid message size limits
                    job = app.job
                    if job.url:
                        app_list.append(f"• <{job.url}|{job.company} - {job.title}>")
                    else:
                        app_list.append(f"• {job.company} - {job.title}")
                
                # Add ellipsis if there are more than 5 applications with this status
                if len(apps) > 5:
                    app_list.append(f"• _...and {len(apps) - 5} more_")
                
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{status_emoji} *{status.replace('_', ' ').title()}* ({len(apps)})\n" + "\n".join(app_list)
                    }
                })
                
                blocks.append({"type": "divider"})
            
            # Build the fallback text message
            status_counts = [f"{len(apps)} {status}" for status, apps in status_groups.items()]
            message = f"Job Application Summary: {', '.join(status_counts)}"
            
            return self.send_notification(message, blocks=blocks)
    
    def list_channels(self):
        """List all available channels in the workspace or provide guidance on setting a channel ID manually"""
        if not self.client:
            logger.error("Slack client not initialized. Set SLACK_API_TOKEN in .env file.")
            print("ERROR: Slack API token not configured. Please add SLACK_API_TOKEN to your .env file.")
            return None
            
        try:
            # Try to list public channels (will only work with channels:read scope)
            try:
                response = self.client.conversations_list(types="public_channel")
                channels = response["channels"]
                
                for channel in channels:
                    print(f"{channel['name']} (ID: {channel['id']})")
                    
                return channels
            except SlackApiError as e:
                error = e.response['error']
                
                if error == "missing_scope":
                    # If we can't list channels due to permissions, try to help with manual configuration
                    print("\nINFO: Your Slack app doesn't have permission to list channels.")
                    print("You'll need to find your channel ID manually and add it to your .env file.\n")
                    
                    # Try to test the current configured channel
                    if self.channel_id:
                        try:
                            # Try to get channel info
                            channel_info = self.client.conversations_info(channel=self.channel_id)
                            channel = channel_info["channel"]
                            print(f"Currently configured channel: {channel['name']} (ID: {channel['id']})")
                            print("This channel appears to be valid and working.\n")
                            return [channel]
                        except SlackApiError:
                            print("Currently configured channel ID is not accessible or invalid.")
                    
                    print("\nTo find your channel ID manually:")
                    print("1. Open Slack in your web browser")
                    print("2. Navigate to the channel you want to use")
                    print("3. Look at the URL: https://app.slack.com/client/TXXXXXXXX/CXXXXXXXXX")
                    print("4. The last part of the URL (starting with 'C') is your channel ID")
                    print("5. Add this to your .env file as: SLACK_CHANNEL_ID=CXXXXXXXXX\n")
                    
                    # Try to check which permissions we actually have
                    print("The minimal required scopes for your Slack app are:")
                    print("- chat:write (to send messages)")
                    print("- files:write (to upload files like resumes/cover letters)")
                    print("\nTo add these permissions:")
                    print("1. Go to https://api.slack.com/apps")
                    print("2. Select your app")
                    print("3. Go to 'OAuth & Permissions'")
                    print("4. Add the required scopes")
                    print("5. Reinstall the app\n")
                    
                    return None
                else:
                    # Some other error occurred
                    print(f"Error accessing Slack: {error}")
                    return None
        except Exception as e:
            logger.error(f"Error listing channels: {str(e)}")
            print(f"Error: {str(e)}")
            return None


def get_notifier(token=None, channel_id=None, username=None, icon_emoji=None):
    """Get a configured instance of the Slack notifier"""
    return SlackNotifier(token, channel_id, username, icon_emoji)


def main():
    """CLI entry point for sending notifications"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Send Slack notifications about job applications")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Daily summary command
    summary_parser = subparsers.add_parser("summary", help="Send a daily summary of job applications")
    summary_parser.add_argument("--channel", help="Override the default Slack channel")
    
    # Test notification command
    test_parser = subparsers.add_parser("test", help="Send a test notification")
    test_parser.add_argument("--message", default="Test notification from the job search automation system",
                          help="Message to send")
    test_parser.add_argument("--channel", help="Override the default Slack channel")
    
    # List channels command
    list_channels_parser = subparsers.add_parser("list-channels", help="List all available Slack channels")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Create a notifier with the specified or default channel
    channel_id = args.channel if hasattr(args, 'channel') and args.channel else None
    notifier = get_notifier(channel_id=channel_id)
    
    if args.command == "summary":
        notifier.send_daily_summary()
    elif args.command == "test":
        notifier.send_notification(args.message)
    elif args.command == "list-channels":
        channels = notifier.list_channels()
        if channels:
            for channel in channels:
                print(f"{channel['name']} (ID: {channel['id']})")
        else:
            print("No channels found or unable to list channels.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()