#!/usr/bin/env python3
import os
import json
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from email.message import EmailMessage
import smtplib
import email
import imaplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from models import EmailCorrespondence, JobCache
from utils import session_scope
from logging_utils import setup_logging

logger = setup_logging('email_service')

class EmailService:
    """Service for handling email operations related to job applications"""
    
    def __init__(self, gmail_service=None, use_gemini=False, gemini_api_key=None):
        """
        Initialize the email service
        
        Args:
            gmail_service: Optional preconfigured Gmail service
            use_gemini: Whether to use Gemini AI for enhanced email processing
            gemini_api_key: API key for Google Gemini if use_gemini is True
        """
        self.gmail_service = gmail_service
        self.use_gemini = use_gemini
        self.gemini_model = None
        
        # Initialize Gemini if requested
        if use_gemini:
            try:
                import google.generativeai as genai
                
                genai.configure(api_key=gemini_api_key)
                self.gemini_model = genai.GenerativeModel('gemini-pro')
                logger.info("Gemini AI initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini AI: {str(e)}")
                self.use_gemini = False
        
        self.email_address = os.getenv('EMAIL_ADDRESS')
        self.password = os.getenv('EMAIL_PASSWORD')
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.imap_server = os.getenv('IMAP_SERVER', 'imap.gmail.com')
        self.server = None
        
        # Optional alternative sending name
        self.send_as_name = os.getenv('EMAIL_SEND_AS_NAME')
        
    def send_email(self, to: str or List[str], subject: str, body: str, 
                  job_id: Optional[int] = None, cc: List[str] = None, 
                  bcc: List[str] = None, html_body: Optional[str] = None) -> bool:
        """
        Send an email and store it in the database
        
        Args:
            to: Recipient email or list of emails
            subject: Email subject
            body: Plain text email body
            job_id: Optional job ID to associate with this email
            cc: Optional list of CC recipients
            bcc: Optional list of BCC recipients
            html_body: Optional HTML version of the email body
            
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not self.email_address or not self.password:
            logger.error("Email credentials not configured")
            return False
            
        # Convert single recipient to list
        if isinstance(to, str):
            to = [to]
            
        # Default empty lists for cc/bcc
        if cc is None:
            cc = []
        if bcc is None:
            bcc = []
            
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            
            # Add sender info (with optional display name)
            if self.send_as_name:
                msg['From'] = f"{self.send_as_name} <{self.email_address}>"
            else:
                msg['From'] = self.email_address
                
            msg['To'] = ', '.join(to)
            
            # Add CC if provided
            if cc:
                msg['Cc'] = ', '.join(cc)
                
            msg['Subject'] = subject
            
            # Attach text body
            part1 = MIMEText(body, 'plain')
            msg.attach(part1)
            
            # Attach HTML body if provided
            if html_body:
                part2 = MIMEText(html_body, 'html')
                msg.attach(part2)
            
            # Connect to SMTP server
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(self.email_address, self.password)
                
                # All recipients including cc and bcc
                all_recipients = to + cc + bcc
                
                # Send email
                server.send_message(msg)
                logger.info(f"Email sent to {', '.join(to)}")
                
                # Store in database
                with session_scope() as session:
                    # Check if job exists if job_id provided
                    if job_id:
                        job = session.query(JobCache).filter_by(id=job_id).first()
                        if not job:
                            logger.warning(f"Job with ID {job_id} not found")
                            job_id = None
                    
                    # Check for calendar invite in the body
                    has_calendar_invite = self._detect_calendar_invite(body)
                    
                    # Add email record
                    email_record = EmailCorrespondence(
                        job_id=job_id,
                        direction='outgoing',
                        sender=self.email_address,
                        recipients=json.dumps(all_recipients),
                        subject=subject,
                        body=body,
                        sent_date=datetime.now(),
                        status='sent',
                        has_calendar_invite=has_calendar_invite
                    )
                    
                    session.add(email_record)
                    logger.info(f"Email stored in database")
                    
                return True
                
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False
    
    def sync_emails(self, days: int = 7) -> Tuple[int, int]:
        """
        Sync emails from the email server to the database
        
        Args:
            days: Number of days to look back
            
        Returns:
            Tuple of (emails_found, emails_stored)
        """
        if not self.email_address or not self.password:
            logger.error("Email credentials not configured")
            return 0, 0
            
        logger.info(f"Syncing emails from the last {days} days")
        
        try:
            # Connect to IMAP server
            mail = imaplib.IMAP4_SSL(self.imap_server)
            mail.login(self.email_address, self.password)
            mail.select('inbox')
            
            # Calculate date for search (n days ago)
            date_since = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
            
            # Search for emails since date
            status, messages = mail.search(None, f'(SINCE {date_since})')
            
            if status != 'OK':
                logger.error("Failed to search emails")
                return 0, 0
                
            message_ids = messages[0].split()
            
            if not message_ids:
                logger.info("No emails found in the specified date range")
                return 0, 0
                
            found_count = len(message_ids)
            stored_count = 0
            
            # Get list of email IDs we already have
            with session_scope() as session:
                existing_thread_ids = {
                    row[0] for row in session.query(EmailCorrespondence.thread_id).all() 
                    if row[0] is not None
                }
            
            # Process each email
            for message_id in message_ids:
                status, msg_data = mail.fetch(message_id, '(RFC822)')
                
                if status != 'OK':
                    logger.warning(f"Failed to fetch message {message_id}")
                    continue
                    
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                # Get thread ID (Message-ID or similar)
                thread_id = msg.get('Message-ID') or msg.get('References') or message_id.decode()
                
                # Skip if we already have this email
                if thread_id in existing_thread_ids:
                    logger.debug(f"Skipping already stored email with thread ID: {thread_id}")
                    continue
                
                # Extract email details
                subject = msg.get('Subject', '(No Subject)')
                from_email = self._parse_email_address(msg.get('From', ''))
                to_emails = self._parse_email_addresses(msg.get('To', ''))
                cc_emails = self._parse_email_addresses(msg.get('Cc', ''))
                all_recipients = to_emails + cc_emails
                
                # Parse date
                date_str = msg.get('Date')
                received_date = None
                if date_str:
                    try:
                        # This is simplified - email date parsing can be complex
                        received_date = email.utils.parsedate_to_datetime(date_str)
                    except:
                        logger.warning(f"Could not parse date: {date_str}")
                        received_date = datetime.now()
                else:
                    received_date = datetime.now()
                
                # Get email body
                body = self._get_email_body(msg)
                
                # Detect if this is related to a job application
                job_id, reasoning = self._match_email_to_job_with_gemini(from_email, subject, body)
                
                # Only store job-related emails if we can identify the job
                if job_id:
                    # Check for calendar invite
                    has_calendar_invite, invite_reasoning = self._detect_calendar_invite_with_gemini(subject, body)
                    
                    # Store email in database
                    with session_scope() as session:
                        email_record = EmailCorrespondence(
                            job_id=job_id,
                            direction='incoming',
                            sender=from_email,
                            recipients=json.dumps(all_recipients),
                            subject=subject,
                            body=body,
                            received_date=received_date,
                            thread_id=thread_id,
                            status='unread',
                            has_calendar_invite=has_calendar_invite
                        )
                        
                        session.add(email_record)
                        stored_count += 1
                        logger.debug(f"Stored email: {subject}")
            
            mail.close()
            mail.logout()
            
            logger.info(f"Email sync complete: {found_count} emails found, {stored_count} emails stored")
            return found_count, stored_count
            
        except Exception as e:
            logger.error(f"Error syncing emails: {str(e)}")
            return 0, 0
    
    def get_emails_for_job(self, job_id: int) -> List[Dict]:
        """
        Get all emails related to a specific job
        
        Args:
            job_id: Job ID to get emails for
            
        Returns:
            List of email dictionaries
        """
        result = []
        
        try:
            with session_scope() as session:
                # Verify job exists
                job = session.query(JobCache).filter_by(id=job_id).first()
                if not job:
                    logger.error(f"Job with ID {job_id} not found")
                    return []
                
                # Get emails for this job
                emails = session.query(EmailCorrespondence).filter_by(
                    job_id=job_id
                ).order_by(
                    desc(EmailCorrespondence.received_date),
                    desc(EmailCorrespondence.sent_date)
                ).all()
                
                # Format result
                for email in emails:
                    result.append({
                        'id': email.id,
                        'job_id': email.job_id,
                        'direction': email.direction,
                        'sender': email.sender,
                        'recipients': json.loads(email.recipients) if email.recipients else [],
                        'subject': email.subject,
                        'body': email.body,
                        'received_date': email.received_date.isoformat() if email.received_date else None,
                        'sent_date': email.sent_date.isoformat() if email.sent_date else None,
                        'thread_id': email.thread_id,
                        'status': email.status,
                        'has_calendar_invite': email.has_calendar_invite
                    })
                
                logger.info(f"Found {len(result)} emails for job {job_id}")
                return result
                
        except Exception as e:
            logger.error(f"Error getting emails for job {job_id}: {str(e)}")
            return []
    
    def mark_email_read(self, email_id: int) -> bool:
        """
        Mark an email as read
        
        Args:
            email_id: Email ID to mark as read
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with session_scope() as session:
                email = session.query(EmailCorrespondence).filter_by(id=email_id).first()
                if not email:
                    logger.error(f"Email with ID {email_id} not found")
                    return False
                
                email.status = 'read'
                logger.info(f"Marked email {email_id} as read")
                return True
                
        except Exception as e:
            logger.error(f"Error marking email as read: {str(e)}")
            return False
    
    # Helper methods
    def _get_email_body(self, msg) -> str:
        """Extract the email body from a message"""
        body = ""
        
        # Multi-part email (HTML + plain text)
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disp = str(part.get('Content-Disposition'))
                
                # Skip attachments
                if 'attachment' in content_disp:
                    continue
                
                # Get the body - prefer plain text over HTML
                if content_type == 'text/plain':
                    try:
                        charset = part.get_content_charset() or 'utf-8'
                        body = part.get_payload(decode=True).decode(charset)
                        break
                    except:
                        pass
                elif content_type == 'text/html' and not body:
                    try:
                        charset = part.get_content_charset() or 'utf-8'
                        body = part.get_payload(decode=True).decode(charset)
                        # Could convert HTML to plain text here if needed
                    except:
                        pass
        else:
            # Simple email with just one part
            try:
                charset = msg.get_content_charset() or 'utf-8'
                body = msg.get_payload(decode=True).decode(charset)
            except:
                body = msg.get_payload()
        
        return body
    
    def _parse_email_address(self, address_str: str) -> str:
        """Parse a single email address from a string"""
        if not address_str:
            return ""
            
        # Try to extract email from "Name <email@example.com>" format
        match = re.search(r'<([^<>]+)>', address_str)
        if match:
            return match.group(1).strip()
            
        # Otherwise return the whole string
        return address_str.strip()
    
    def _parse_email_addresses(self, addresses_str: str) -> List[str]:
        """Parse multiple email addresses from a string"""
        if not addresses_str:
            return []
            
        # Split by commas and parse each address
        return [self._parse_email_address(addr) for addr in addresses_str.split(',')]
    
    def _detect_calendar_invite(self, body: str) -> bool:
        """Detect if an email contains a calendar invite using Gemini"""
        if not self.use_gemini or not self.gemini_model:
            logger.warning("Gemini not available for calendar detection")
            # Fallback to checking for iCal format
            return 'BEGIN:VCALENDAR' in body
            
        try:
            prompt = f"""Analyze this email content and determine if it contains a calendar invite or meeting details.
            The email might have an iCal attachment (containing BEGIN:VCALENDAR), a meeting link (Zoom, Teams, etc),
            or natural language suggesting a meeting time and date.

            Email content:
            {body[:2000]}  # Truncate for token limit

            Respond with only "true" if you detect any calendar/meeting details, or "false" if not.
            """
            
            response = self.gemini_model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0,
                    "top_p": 1,
                }
            )
            
            return response.text.strip().lower() == "true"
            
        except Exception as e:
            logger.error(f"Error detecting calendar invite with Gemini: {str(e)}")
            # Fallback to checking for iCal format
            return 'BEGIN:VCALENDAR' in body

    def _match_email_to_job(self, sender: str, subject: str, body: str) -> Optional[int]:
        """
        Match an email to a job based on content
        
        Returns the job ID if a match is found, None otherwise
        """
        try:
            with session_scope() as session:
                # Get all active jobs
                jobs = session.query(JobCache).all()
                
                # Extract email domain
                sender_domain = None
                if '@' in sender:
                    sender_domain = sender.split('@')[1].lower()
                
                for job in jobs:
                    company = job.company.lower()
                    company_parts = company.split()
                    
                    # Check the sender domain against the company name
                    if sender_domain:
                        # Look for company name in domain
                        for part in company_parts:
                            if len(part) > 3 and part.lower() in sender_domain:
                                logger.info(f"Matched email to job {job.id} by sender domain")
                                return job.id
                    
                    # Check if company name appears in subject or body
                    subject_body = (subject + " " + body[:500]).lower()
                    
                    # Check for company name
                    if company in subject_body:
                        logger.info(f"Matched email to job {job.id} by company name")
                        return job.id
                    
                    # Check for position title
                    if job.title.lower() in subject_body:
                        logger.info(f"Matched email to job {job.id} by job title")
                        return job.id
                    
                    # Check for application ID or reference numbers in common formats
                    # This works if your job applications have IDs that might be referenced
                    if job.url and '/' in job.url:
                        job_ref = job.url.split('/')[-1]
                        if job_ref.isalnum() and len(job_ref) > 5 and job_ref in subject_body:
                            logger.info(f"Matched email to job {job.id} by reference number")
                            return job.id
                
                # If no match found
                logger.warning(f"Could not match email from {sender} with subject '{subject}' to any job")
                return None
                
        except Exception as e:
            logger.error(f"Error matching email to job: {str(e)}")
            return None

    def _match_email_to_job_with_gemini(self, email: EmailCorrespondence, jobs: List[JobCache]) -> Optional[JobCache]:
        """
        Use Gemini AI to match an email to the most relevant job in the database
        
        Args:
            email: The EmailCorrespondence object
            jobs: List of JobCache objects to match against
            
        Returns:
            The matched JobCache object or None
        """
        if not self.use_gemini or not self.gemini_model:
            logger.warning("Gemini not available for email-job matching")
            return None
            
        try:
            # Extract the structured data first
            structured_data = self._extract_structured_email_data_with_gemini(email)
            
            # If we got company and position directly, try to match first
            if structured_data.get("company") and structured_data.get("position"):
                for job in jobs:
                    if (self._is_similar(structured_data["company"], job.company) and 
                        self._is_similar(structured_data["position"], job.title)):
                        logger.info(f"Gemini matched email to job based on structured data: {job.id} - {job.title} at {job.company}")
                        return job
            
            # If no match or structured data extraction failed, use semantic matching
            prompt = f"""
            I need to determine which job posting this email is related to.
            
            EMAIL:
            From: {email.sender}
            Subject: {email.subject}
            Body: {email.body[:1000]}  # Truncate for token limitations
            
            POSSIBLE JOB MATCHES:
            """
            
            # Add job details to prompt
            for i, job in enumerate(jobs[:10]):  # Limit to 10 jobs to stay within token limits
                prompt += f"""
                Job {i+1}:
                ID: {job.id}
                Title: {job.title}
                Company: {job.company}
                Description: {job.description[:200] if job.description else "N/A"}
                URL: {job.url}
                Status: {job.status}
                
                """
                
            prompt += """
            Return only the ID of the job that best matches the email. If there is no clear match, return "NO_MATCH".
            Only respond with the job ID number or "NO_MATCH" - no other text.
            """
            
            response = self.gemini_model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Check if response is a job ID
            if response_text.isdigit():
                job_id = int(response_text)
                # Find the job with this ID
                for job in jobs:
                    if job.id == job_id:
                        logger.info(f"Gemini matched email to job ID {job_id}")
                        return job
                        
            logger.info("Gemini could not match email to any job")
            return None
            
        except Exception as e:
            logger.error(f"Error matching email to job with Gemini: {str(e)}")
            return None

    def generate_reply_with_gemini(self, email: EmailCorrespondence, job: Optional[JobCache] = None) -> str:
        """
        Use Gemini AI to generate an intelligent reply to a recruiter email
        
        Args:
            email: The EmailCorrespondence object
            job: Optional JobCache object if the email is associated with a specific job
            
        Returns:
            A generated email reply text
        """
        if not self.use_gemini or not self.gemini_model:
            logger.warning("Gemini not available for email reply generation")
            return "Gemini AI is not available for generating email replies."
            
        try:
            # Get job details if available
            job_context = ""
            if job:
                job_context = f"""
                This email is related to the following job:
                Title: {job.title}
                Company: {job.company}
                Description: {job.description[:500] if job.description else "N/A"}
                Status: {job.status}
                """
            
            # Get user profile info
            user_profile = self._get_user_profile()
            
            prompt = f"""
            I need to draft a professional reply to a recruiter email. 
            
            ORIGINAL EMAIL:
            From: {email.sender}
            Subject: {email.subject}
            Date: {email.received_date}
            Body: {email.body}
            
            {job_context}
            
            MY PROFILE:
            {user_profile}
            
            Draft a professional, enthusiastic but not overly eager response. 
            Be specific to the content of their email. If they asked questions, answer them.
            If they mentioned specific job details, acknowledge them.
            Don't make up information about my availability if not mentioned in my profile.
            Format the response as a complete email (including greeting and signature) that I can send.
            Keep it concise and professional.
            """
            
            response = self.gemini_model.generate_content(prompt)
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Error generating email reply with Gemini: {str(e)}")
            return f"Error generating reply: {str(e)}"

    def _get_user_profile(self) -> str:
        """Get the user's profile information from the database or file"""
        try:
            # First try to load from the profile.json file
            profile_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                       'docs', 'profile.json')
            
            if os.path.exists(profile_path):
                with open(profile_path, 'r') as f:
                    profile_data = json.load(f)
                    
                profile_text = f"""
                Name: {profile_data.get('name', 'N/A')}
                Current title: {profile_data.get('current_title', 'N/A')}
                Years of experience: {profile_data.get('years_of_experience', 'N/A')}
                Skills: {', '.join(profile_data.get('skills', []))}
                """
                
                if 'job_preferences' in profile_data:
                    pref = profile_data['job_preferences']
                    profile_text += f"""
                    Preferred roles: {', '.join(pref.get('roles', []))}
                    Preferred locations: {', '.join(pref.get('locations', []))}
                    Preferred work types: {', '.join(pref.get('work_types', []))}
                    """
                    
                return profile_text
            else:
                return "No profile information available."
                
        except Exception as e:
            logger.error(f"Error loading user profile: {str(e)}")
            return "Error loading profile information."
            
    def summarize_email_thread_with_gemini(self, emails: List[EmailCorrespondence], job: Optional[JobCache] = None) -> str:
        """
        Use Gemini AI to summarize an email thread related to a job application
        
        Args:
            emails: List of EmailCorrespondence objects in the thread
            job: Optional JobCache object if the emails are associated with a specific job
            
        Returns:
            A summary of the email thread
        """
        if not self.use_gemini or not self.gemini_model:
            logger.warning("Gemini not available for email thread summarization")
            return "Gemini AI is not available for summarizing email threads."
            
        try:
            # Sort emails by date
            sorted_emails = sorted(emails, key=lambda x: x.received_date if x.received_date else datetime.min)
            
            # Get job details if available
            job_context = ""
            if job:
                job_context = f"""
                These emails are related to the following job:
                Title: {job.title}
                Company: {job.company}
                Description: {job.description[:200] if job.description else "N/A"}
                Status: {job.status}
                """
            
            # Format the email thread
            email_thread = ""
            for i, email in enumerate(sorted_emails):
                email_thread += f"""
                EMAIL {i+1}:
                Date: {email.received_date}
                From: {email.sender}
                To: {email.recipient}
                Subject: {email.subject}
                Body: {email.body[:500]}  # Truncate long emails
                
                """
            
            prompt = f"""
            I need a concise summary of this email thread related to a job application.
            
            {job_context}
            
            EMAIL THREAD:
            {email_thread}
            
            Please provide:
            1. A summary of the key points discussed in the thread
            2. Any action items or next steps mentioned
            3. Important dates or deadlines mentioned
            4. The current status of the job application based on the emails
            
            Format the summary in a clear, organized manner.
            """
            
            response = self.gemini_model.generate_content(prompt)
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Error summarizing email thread with Gemini: {str(e)}")
            return f"Error summarizing email thread: {str(e)}"

# Create a global instance
_email_service = None

def get_email_service() -> EmailService:
    """Get the email service instance (singleton)"""
    global _email_service
    if _email_service is None:
        email_address = os.getenv('EMAIL_ADDRESS')
        email_password = os.getenv('EMAIL_PASSWORD')
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        _email_service = EmailService(email_address, email_password, use_gemini=True, gemini_api_key=gemini_api_key)
    return _email_service

if __name__ == "__main__":
    # When run directly, sync emails from last 7 days
    service = get_email_service()
    found, stored = service.sync_emails(7)
    print(f"Email sync complete: {found} emails found, {stored} emails stored")