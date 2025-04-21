#!/usr/bin/env python3
import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from tabulate import tabulate
import logging
import re
import icalendar
from dotenv import load_dotenv
import google.generativeai as genai

from email_service import get_email_service
from calendar_service import get_calendar_service
from utils import get_session
from models import EmailCorrespondence, CalendarEvent, JobApplication
from logging_utils import setup_logging

logger = setup_logging('email_calendar_manager')
load_dotenv()

# Configure Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("Please set GEMINI_API_KEY environment variable")
genai.configure(api_key=GEMINI_API_KEY)

class EmailCalendarManager:
    """Manager to coordinate between email and calendar services"""
    
    def __init__(self):
        """Initialize the manager with email and calendar services"""
        self.email_service = get_email_service()
        self.calendar_service = get_calendar_service()
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        
    def process_new_emails(self, days_back: int = 1) -> Tuple[int, int]:
        """Process new emails and extract calendar invites"""
        processed = 0
        calendar_count = 0
        
        # Sync new emails first
        found, stored = self.email_service.sync_emails(days_back)
        
        try:
            with get_session() as session:
                # Get unprocessed emails with calendar invites
                emails = session.query(EmailCorrespondence).filter(
                    EmailCorrespondence.has_calendar_invite == True,
                    EmailCorrespondence.processed_calendar == False,
                    EmailCorrespondence.received_date >= (datetime.now() - timedelta(days=days_back)).isoformat()
                ).all()
                
                for email in emails:
                    processed += 1
                    
                    # Extract calendar details
                    calendar_details = self._extract_calendar_details(email)
                    if calendar_details:
                        # Create calendar event
                        event_id = self.calendar_service.create_interview_event(
                            job_id=email.job_id,
                            start_time=calendar_details['start_time'],
                            end_time=calendar_details.get('end_time'),
                            description=calendar_details.get('description', ''),
                            location=calendar_details.get('location', ''),
                            attendees=calendar_details.get('attendees', [])
                        )
                        
                        if event_id:
                            calendar_count += 1
                            
                            # Update job application status
                            if email.job_id:
                                application = session.query(JobApplication).filter_by(id=email.job_id).first()
                                if application:
                                    application.status = 'interview_scheduled'
                                    
                            # Mark email as processed
                            email.processed_calendar = True
                            logger.info(f"Created calendar event from email: {email.subject}")
                            
                session.commit()
                
        except Exception as e:
            logger.error(f"Error processing emails for calendar events: {str(e)}")
            
        return processed, calendar_count
        
    def _extract_calendar_details(self, email: EmailCorrespondence) -> Optional[Dict]:
        """Extract calendar event details from an email"""
        try:
            prompt = f"""Extract calendar event details from this email. The email may contain calendar details in various formats including plain text and iCalendar (.ics) format:

Subject: {email.subject}

Body:
{email.body}

Extract and respond with a JSON object containing:
1. start_time (datetime in ISO format, required)
2. end_time (datetime in ISO format, optional)
3. location (string, optional - look for video call links or physical addresses)
4. description (string, optional)
5. attendees (list of email addresses, optional)

If you don't find valid calendar details, return null.
If you find a date but no time, don't return anything - we need both.
All dates/times should be in Pacific timezone (America/Los_Angeles).

Note: The email might contain iCalendar data (between BEGIN:VCALENDAR and END:VCALENDAR). If you find this, extract the details from it.
"""
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0,
                    "top_p": 1,
                }
            )
            
            try:
                result = json.loads(response.text)
                if not result:
                    return None
                    
                # Validate required fields
                if 'start_time' not in result:
                    return None
                    
                # Parse dates into datetime objects
                result['start_time'] = datetime.fromisoformat(result['start_time'])
                if result.get('end_time'):
                    result['end_time'] = datetime.fromisoformat(result['end_time'])
                else:
                    # Default to 1 hour duration
                    result['end_time'] = result['start_time'] + timedelta(hours=1)
                    
                return result
                
            except json.JSONDecodeError:
                logger.error("Failed to parse Gemini response as JSON")
                return None
                
        except Exception as e:
            logger.error(f"Error using Gemini to extract calendar details: {str(e)}")
            return None
            
    def send_calendar_response(self, event_id: str, response: str = 'accepted') -> bool:
        """Send a calendar response email"""
        try:
            with get_session() as session:
                event = session.query(CalendarEvent).filter_by(id=event_id).first()
                if not event:
                    logger.error(f"Calendar event {event_id} not found")
                    return False
                    
                # Get original email
                email = session.query(EmailCorrespondence).filter_by(
                    job_id=event.job_application_id,
                    has_calendar_invite=True
                ).first()
                
                if not email:
                    logger.error("Original calendar invite email not found")
                    return False
                    
                # Create response email
                subject = f"Re: {email.subject}"
                body = f"I have {response} the calendar invite for {event.description}"
                
                # Send response
                sent = self.email_service.send_email(
                    to=email.sender,
                    subject=subject,
                    body=body,
                    job_id=event.job_application_id
                )
                
                if sent:
                    logger.info(f"Sent calendar response: {response}")
                    return True
                    
                return False
                
        except Exception as e:
            logger.error(f"Error sending calendar response: {str(e)}")
            return False

# Create a global instance
_email_calendar_manager = None

def get_email_calendar_manager() -> EmailCalendarManager:
    """Get the email calendar manager instance (singleton)"""
    global _email_calendar_manager
    if _email_calendar_manager is None:
        _email_calendar_manager = EmailCalendarManager()
    return _email_calendar_manager

if __name__ == "__main__":
    # When run directly, process last day's emails
    manager = get_email_calendar_manager()
    processed, calendar_count = manager.process_new_emails(1)
    print(f"Processed {processed} emails, created {calendar_count} calendar events")