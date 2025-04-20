#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from datetime import datetime

# Add the parent directory to the Python path
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

from scripts.models import RecruiterContact
from scripts.utils import session_scope

# Create sample recruiter contacts
def add_sample_recruiters():
    print("Adding sample recruiter contacts to the database...")
    
    with session_scope() as session:
        # Check if we already have recruiters for these companies
        stripe_recruiters = session.query(RecruiterContact).filter_by(company='Stripe').first()
        autodesk_recruiters = session.query(RecruiterContact).filter_by(company='Autodesk').first()
        
        if not stripe_recruiters:
            session.add(RecruiterContact(
                name='John Smith',
                title='Technical Recruiter',
                company='Stripe',
                url='https://linkedin.com/in/johnsmith',
                source='linkedin',
                found_date=datetime.now().isoformat(),
                status='identified',
                notes='Specializes in cloud engineering roles'
            ))
            session.add(RecruiterContact(
                name='Sarah Johnson',
                title='Senior Technical Recruiter',
                company='Stripe',
                url='https://linkedin.com/in/sarahjohnson',
                source='linkedin',
                found_date=datetime.now().isoformat(),
                status='identified',
                notes='Focuses on principal engineer positions'
            ))
            print("Added recruiters for Stripe")
        else:
            print("Recruiters for Stripe already exist")
            
        if not autodesk_recruiters:
            session.add(RecruiterContact(
                name='Michael Chang',
                title='Talent Acquisition Specialist',
                company='Autodesk',
                url='https://linkedin.com/in/michaelchang',
                source='linkedin',
                found_date=datetime.now().isoformat(),
                status='identified'
            ))
            print("Added recruiter for Autodesk")
        else:
            print("Recruiter for Autodesk already exists")
    
    print("Sample recruiters added successfully!")

if __name__ == "__main__":
    add_sample_recruiters()
