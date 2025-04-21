#!/usr/bin/env python3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import json
import logging
from dotenv import load_dotenv

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GOOGLE_CALENDAR_AVAILABLE = True
except ImportError:
    GOOGLE_CALENDAR_AVAILABLE = False

from models import JobApplication, CalendarEvent, get_session
from logging_utils import setup_logging

logger = setup_logging('calendar_service')
load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/calendar']

class CalendarService:
    """Service for handling calendar operations related to job applications"""
    
    def __init__(self):
        """Initialize the calendar service"""
        self.calendar_service = None
        self.credentials_path = Path(__file__).parent.parent / 'config' / 'google_credentials.json'
        self.token_path = Path(__file__).parent.parent / 'config' / 'calendar_token.json'
        
        if GOOGLE_CALENDAR_AVAILABLE:
            self._setup_google_calendar()
            
    def _setup_google_calendar(self):
        """Set up Google Calendar API credentials"""
        creds = None
        
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.credentials_path.exists():
                    logger.warning("Google Calendar credentials not found")
                    return
                    
                flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)
                
                # Save the credentials for future use
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
        
        try:
            self.calendar_service = build('calendar', 'v3', credentials=creds)
            logger.info("Google Calendar service initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Google Calendar service: {str(e)}")
            
    def create_interview_event(self, job_id: int, start_time: datetime, 
                             end_time: Optional[datetime] = None,
                             description: str = "", location: str = "",
                             attendees: List[str] = None) -> Optional[str]:
        """
        Create a calendar event for an interview
        
        Args:
            job_id: ID of the job application
            start_time: Interview start time
            end_time: Optional interview end time (defaults to start_time + 1 hour)
            description: Optional event description
            location: Optional location (can be physical address or video call link)
            attendees: Optional list of attendee email addresses
            
        Returns:
            Calendar event ID if successful, None otherwise
        """
        if not end_time:
            end_time = start_time + timedelta(hours=1)
            
        if not attendees:
            attendees = []
            
        try:
            with get_session() as session:
                # Get job application details
                application = session.query(JobApplication).filter_by(id=job_id).first()
                if not application:
                    logger.error(f"Job application {job_id} not found")
                    return None
                    
                job = application.job
                
                # Create event details
                event = {
                    'summary': f"Interview with {job.company} - {job.title}",
                    'location': location,
                    'description': description or f"Job interview for {job.title} position at {job.company}",
                    'start': {
                        'dateTime': start_time.isoformat(),
                        'timeZone': 'America/Los_Angeles',  # TODO: Make configurable
                    },
                    'end': {
                        'dateTime': end_time.isoformat(),
                        'timeZone': 'America/Los_Angeles',
                    },
                    'attendees': [{'email': email} for email in attendees],
                    'reminders': {
                        'useDefault': False,
                        'overrides': [
                            {'method': 'email', 'minutes': 24 * 60},
                            {'method': 'popup', 'minutes': 30},
                        ],
                    },
                }
                
                if self.calendar_service:
                    # Create event in Google Calendar
                    event_result = self.calendar_service.events().insert(
                        calendarId='primary',
                        body=event,
                        sendUpdates='all'
                    ).execute()
                    
                    event_id = event_result['id']
                    
                    # Store in our database
                    calendar_event = CalendarEvent(
                        job_application_id=job_id,
                        event_type='interview',
                        start_time=start_time.isoformat(),
                        end_time=end_time.isoformat(),
                        description=description,
                        location=location,
                        calendar_event_id=event_id,
                        provider='google'
                    )
                    
                    session.add(calendar_event)
                    logger.info(f"Created calendar event for interview with {job.company}")
                    
                    return event_id
                else:
                    # Store locally only
                    calendar_event = CalendarEvent(
                        job_application_id=job_id,
                        event_type='interview',
                        start_time=start_time.isoformat(),
                        end_time=end_time.isoformat(),
                        description=description,
                        location=location,
                        provider='local'
                    )
                    
                    session.add(calendar_event)
                    logger.info(f"Created local calendar event for interview with {job.company}")
                    
                    return calendar_event.id
                    
        except Exception as e:
            logger.error(f"Error creating calendar event: {str(e)}")
            return None
            
    def update_event(self, event_id: str, start_time: Optional[datetime] = None,
                    end_time: Optional[datetime] = None, description: Optional[str] = None,
                    location: Optional[str] = None, attendees: Optional[List[str]] = None) -> bool:
        """
        Update an existing calendar event
        
        Args:
            event_id: Calendar event ID to update
            start_time: Optional new start time
            end_time: Optional new end time
            description: Optional new description
            location: Optional new location
            attendees: Optional new list of attendees
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with get_session() as session:
                event = session.query(CalendarEvent).filter_by(id=event_id).first()
                if not event:
                    logger.error(f"Calendar event {event_id} not found")
                    return False
                    
                # Update local record
                if start_time:
                    event.start_time = start_time.isoformat()
                if end_time:
                    event.end_time = end_time.isoformat()
                if description:
                    event.description = description
                if location:
                    event.location = location
                    
                # Update in Google Calendar if available
                if self.calendar_service and event.provider == 'google':
                    g_event = self.calendar_service.events().get(
                        calendarId='primary',
                        eventId=event.calendar_event_id
                    ).execute()
                    
                    if start_time:
                        g_event['start']['dateTime'] = start_time.isoformat()
                    if end_time:
                        g_event['end']['dateTime'] = end_time.isoformat()
                    if description:
                        g_event['description'] = description
                    if location:
                        g_event['location'] = location
                    if attendees:
                        g_event['attendees'] = [{'email': email} for email in attendees]
                        
                    self.calendar_service.events().update(
                        calendarId='primary',
                        eventId=event.calendar_event_id,
                        body=g_event,
                        sendUpdates='all'
                    ).execute()
                    
                logger.info(f"Updated calendar event {event_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating calendar event: {str(e)}")
            return False
            
    def delete_event(self, event_id: str) -> bool:
        """
        Delete a calendar event
        
        Args:
            event_id: Calendar event ID to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with get_session() as session:
                event = session.query(CalendarEvent).filter_by(id=event_id).first()
                if not event:
                    logger.error(f"Calendar event {event_id} not found")
                    return False
                    
                # Delete from Google Calendar if available
                if self.calendar_service and event.provider == 'google':
                    self.calendar_service.events().delete(
                        calendarId='primary',
                        eventId=event.calendar_event_id
                    ).execute()
                    
                # Delete local record
                session.delete(event)
                logger.info(f"Deleted calendar event {event_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting calendar event: {str(e)}")
            return False
            
    def get_upcoming_events(self, days: int = 7) -> List[Dict]:
        """
        Get upcoming calendar events
        
        Args:
            days: Number of days to look ahead
            
        Returns:
            List of event dictionaries
        """
        try:
            with get_session() as session:
                now = datetime.now()
                end_date = now + timedelta(days=days)
                
                events = session.query(CalendarEvent).filter(
                    CalendarEvent.start_time >= now.isoformat(),
                    CalendarEvent.start_time <= end_date.isoformat()
                ).all()
                
                result = []
                for event in events:
                    result.append({
                        'id': event.id,
                        'job_application_id': event.job_application_id,
                        'type': event.event_type,
                        'start_time': event.start_time,
                        'end_time': event.end_time,
                        'description': event.description,
                        'location': event.location,
                        'provider': event.provider
                    })
                    
                logger.info(f"Found {len(result)} upcoming events")
                return result
                
        except Exception as e:
            logger.error(f"Error getting upcoming events: {str(e)}")
            return []

# Create a global instance
_calendar_service = None

def get_calendar_service() -> CalendarService:
    """Get the calendar service instance (singleton)"""
    global _calendar_service
    if _calendar_service is None:
        _calendar_service = CalendarService()
    return _calendar_service

if __name__ == "__main__":
    # When run directly, show upcoming events for next 7 days
    service = get_calendar_service()
    events = service.get_upcoming_events(7)
    print(f"Found {len(events)} upcoming events in the next 7 days:")