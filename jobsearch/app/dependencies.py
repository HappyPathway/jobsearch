from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional
import jwt
from datetime import datetime, timedelta

# Import from installed package
from jobsearch.core.database import get_session as jobsearch_get_session
from jobsearch.core.storage import GCSManager

# Configure OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
SECRET_KEY = "your-secret-key-here"  # Move to environment variables
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Initialize storage manager
storage = GCSManager()

def get_db():
    """Get database session from installed jobsearch package"""
    db = jobsearch_get_session()
    try:
        yield db
    finally:
        db.close()

def verify_token(token: str = Depends(oauth2_scheme)) -> dict:
    """Verify JWT token and return decoded payload"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        raise credentials_exception

async def get_current_user(payload: dict = Depends(verify_token)) -> str:
    """Get current authenticated user from token payload"""
    return payload.get("sub")