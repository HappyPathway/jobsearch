#!/usr/bin/env python3
import os
import sys
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Base, engine
from logging_utils import setup_logging

logger = setup_logging('update_db_for_email_calendar')

def update_database():
    """Update database schema for email and calendar integration"""
    try:
        # Create new tables
        Base.metadata.create_all(engine)
        logger.info("Database schema updated successfully")
        return True
    except Exception as e:
        logger.error(f"Error updating database schema: {str(e)}")
        return False

if __name__ == "__main__":
    update_database()