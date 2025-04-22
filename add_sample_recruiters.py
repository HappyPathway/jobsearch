#!/usr/bin/env python3
from datetime import datetime
from models import RecruiterContact
from utils import session_scope

def add_sample_recruiters():
    print("Adding sample recruiter contacts to the database...")
    
    with session_scope() as session:
        # Sample companies from our job search
        companies = {
            'Stripe': [
                ('Sarah Johnson', 'Senior Technical Recruiter', 'https://linkedin.com/in/sarahjohnson'),
                ('John Smith', 'Principal Technical Recruiter', 'https://linkedin.com/in/johnsmith')
            ],
            'Oracle': [
                ('Michael Chang', 'Cloud Engineering Recruiter', 'https://linkedin.com/in/michaelchang'),
                ('Emily Brown', 'Technical Talent Acquisition Lead', 'https://linkedin.com/in/emilybrown')
            ],
            'Postman': [
                ('Rachel Lee', 'Technical Recruiting Manager', 'https://linkedin.com/in/rachellee'),
                ('David Wilson', 'Senior Technical Recruiter', 'https://linkedin.com/in/davidwilson')
            ],
            'Coinbase': [
                ('Amanda Martinez', 'Cloud Infrastructure Recruiter', 'https://linkedin.com/in/amandamartinez'),
                ('James Taylor', 'Technical Recruiting Lead', 'https://linkedin.com/in/jamestaylor')
            ]
        }

        for company, recruiters in companies.items():
            for name, title, url in recruiters:
                # Check if recruiter already exists
                existing = session.query(RecruiterContact).filter_by(url=url).first()
                if not existing:
                    recruiter = RecruiterContact(
                        name=name,
                        title=title,
                        company=company,
                        url=url,
                        source='linkedin',
                        found_date=datetime.now().isoformat(),
                        status='identified'
                    )
                    session.add(recruiter)
                    print(f"Added {name} as {title} at {company}")
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
