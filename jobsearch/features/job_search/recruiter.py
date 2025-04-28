#!/usr/bin/env python3
import os
import json
from datetime import datetime
from jobsearch.core.models import RecruiterContact
from jobsearch.core.storage import GCSManager
from jobsearch.core.database import get_engine
from sqlalchemy.orm import Session
from jobsearch.core.logging import setup_logging
import google.generativeai as genai
from dotenv import load_dotenv

logger = setup_logging('recruiter_finder')

# Initialize GCS manager and load environment
storage = GCSManager()
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class RecruiterFinder:
    """Finds and tracks recruiter contacts from various sources."""
    
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-pro')
        self.engine = get_engine()
    
    def save_recruiter(self, recruiter_info):
        """Save recruiter contact to database."""
        with Session(self.engine) as session:
            recruiter = RecruiterContact(
                name=recruiter_info['name'],
                title=recruiter_info.get('title', ''),
                company=recruiter_info.get('company', ''),
                url=recruiter_info['url'],
                source=recruiter_info.get('source', 'linkedin'),
                found_date=datetime.now().isoformat(),
                status='identified'
            )
            session.add(recruiter)
            session.commit()
            storage.sync_db()
            return recruiter.id
    
    def update_recruiter_status(self, url, status, notes=None):
        """Update recruiter contact status."""
        with Session(self.engine) as session:
            recruiter = session.query(RecruiterContact).filter_by(url=url).first()
            if recruiter:
                recruiter.status = status
                if status == 'contacted':
                    recruiter.contacted_date = datetime.now().isoformat()
                if notes:
                    recruiter.notes = notes
                session.commit()
                storage.sync_db()
                return True
            return False

# Global instance
_recruiter_finder = None

def get_recruiter_finder():
    """Get a singleton instance of the RecruiterFinder"""
    global _recruiter_finder
    if _recruiter_finder is None:
        _recruiter_finder = RecruiterFinder()
    return _recruiter_finder