from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class EmailCorrespondence(Base):
    """Model for tracking email correspondence related to job applications"""
    __tablename__ = 'email_correspondence'
    
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey('job_cache.id'), nullable=False)
    direction = Column(String, nullable=False)  # 'incoming' or 'outgoing'
    sender = Column(String, nullable=False)
    recipients = Column(Text, nullable=False)  # JSON list of recipients
    subject = Column(String)
    body = Column(Text)
    received_date = Column(DateTime)
    sent_date = Column(DateTime)
    thread_id = Column(String)  # Email thread ID for grouping conversations
    status = Column(String)  # 'read', 'unread', 'replied', etc.
    has_calendar_invite = Column(Boolean, default=False)
    
    # Relationships
    job = relationship("JobCache", back_populates="emails")
    calendar_events = relationship("CalendarEvent", back_populates="email")
    
    def __repr__(self):
        return f"<EmailCorrespondence(id={self.id}, direction='{self.direction}', subject='{self.subject}')>"

class CalendarEvent(Base):
    """Model for tracking calendar events/meetings related to job applications"""
    __tablename__ = 'calendar_events'
    
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey('job_cache.id'), nullable=True)
    email_id = Column(Integer, ForeignKey('email_correspondence.id'), nullable=True)
    event_id = Column(String)  # Calendar provider's event ID
    title = Column(String, nullable=False)
    description = Column(Text)
    location = Column(String)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    attendees = Column(Text)  # JSON list of attendees
    status = Column(String)  # 'confirmed', 'tentative', 'cancelled'
    event_type = Column(String)  # 'interview', 'screening', 'follow-up', etc.
    reminder_set = Column(Boolean, default=True)
    notes = Column(Text)
    
    # Relationships
    job = relationship("JobCache", back_populates="calendar_events")
    email = relationship("EmailCorrespondence", back_populates="calendar_events")
    
    def __repr__(self):
        return f"<CalendarEvent(id={self.id}, title='{self.title}', start_time='{self.start_time}')>"

# Add relationship to JobCache
JobCache.emails = relationship("EmailCorrespondence", back_populates="job")
JobCache.calendar_events = relationship("CalendarEvent", back_populates="job")