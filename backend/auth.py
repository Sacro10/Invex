"""Authentication utilities for JWT tokens, password hashing, and user dependencies."""

from datetime import datetime, timedelta
from typing import Tuple

from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from starlette.requests import Request
from sqlalchemy.orm import Session
from models import User
from database import get_db
from passlib.context import CryptContext
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET", "change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Create a JWT access token with optional expiration."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Verify a JWT token and extract claims."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> Tuple[User, int]:
    """FastAPI dependency to extract current user from JWT token.
    
    Returns:
        Tuple[User, int]: (User object, org_id)
    
    Raises:
        HTTPException: If token is invalid or user not found
    """
    # Get token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_header[7:]  # Remove "Bearer " prefix
    payload = verify_token(token)
    
    user_id: int = payload.get("sub")
    org_id: int = payload.get("org_id")
    
    if user_id is None or org_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
        )
    
    user = db.query(User).filter(User.id == user_id, User.org_id == org_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    return user, org_id
