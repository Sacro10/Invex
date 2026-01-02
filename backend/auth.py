"""Authentication utilities for JWT tokens, password hashing, and user dependencies."""

import os
from datetime import datetime, timedelta
from typing import Tuple

from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from starlette.requests import Request
from sqlalchemy.orm import Session
from models import User, Subscription
from database import get_db
from passlib.context import CryptContext
from dotenv import load_dotenv
from settings import settings

# Load environment variables from .env if present
load_dotenv()

# Configuration
SECRET_KEY = settings.jwt_secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing context
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"], 
    deprecated="auto",
    pbkdf2_sha256__default_rounds=30000
)

def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-SHA256 (more reliable than bcrypt)."""
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
    
    to_encode.update({"exp": int(expire.timestamp())})
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
    
    user_id_str: str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
        )
    user_id = int(user_id_str)
    org_id: int = payload.get("org_id")
    if org_id is None:
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


# Plan-based feature capabilities
PLAN_CAPABILITIES = {
    "core": [
        "tenant_screening",
        "maintenance_routing", 
        "tenant_portal_reminders",  # notifications
        "digital_lease_storage",    # leases
        "move_in_checklist",
        "basic_reporting",         # pulse metrics
        "property_management",     # basic property CRUD
    ],
    "growth": [
        "tenant_screening",
        "maintenance_routing",
        "tenant_portal_reminders",
        "digital_lease_storage",
        "move_in_checklist", 
        "basic_reporting",
        "integrated_accounting",   # accounting endpoints
        "automated_rent_collection",
        "portfolio_reporting",
        "vendor_sla_tracking",
        "custom_workflow_rules",
        "multi_property_dashboards",
        "property_management",     # property CRUD
    ],
    "premium": [
        "tenant_screening",
        "maintenance_routing",
        "tenant_portal_reminders",
        "digital_lease_storage",
        "move_in_checklist",
        "basic_reporting",
        "integrated_accounting",
        "automated_rent_collection", 
        "portfolio_reporting",
        "vendor_sla_tracking",
        "custom_workflow_rules",
        "multi_property_dashboards",
        "market_pricing_intelligence",
        "advanced_analytics",
        "lease_renewal_intelligence",  # AI lease renewal suggestions
        "dedicated_onboarding",
        "predictive_vacancy_alerts",
        "priority_support",
        "data_export_api_access",
        "property_management",     # property CRUD
    ]
}

# Plan hierarchy for comparison
PLAN_HIERARCHY = {
    "core": 1,
    "growth": 2,
    "premium": 3
}


def get_org_plan(db: Session, org_id: int) -> str:
    """Get the current subscription plan for an organization."""
    subscription = db.query(Subscription).filter(
        Subscription.org_id == org_id,
        Subscription.status == "active"
    ).first()
    
    if subscription:
        return subscription.plan
    else:
        # Default to core for organizations without active subscriptions
        return "core"


def require_capability(capability: str):
    """Factory function that returns a FastAPI dependency for capability checking.
    
    Args:
        capability: The capability name to check
        
    Returns:
        Dependency function that can be used with Depends()
    """
    async def dependency(
        user_data=Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> Tuple[User, int]:
        """Actual dependency function that checks capability access."""
        user, org_id = user_data
        
        # Get current plan
        plan = get_org_plan(db, org_id)
        
        # Check if capability is available in plan
        if capability not in PLAN_CAPABILITIES.get(plan, []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires a higher plan. Current plan: {plan}. Required capability: {capability}",
            )
        
        return user, org_id
    
    return dependency


def require_plan(minimum_plan: str):
    """Factory function that returns a FastAPI dependency for minimum plan checking.
    
    Args:
        minimum_plan: The minimum plan required (core, growth, premium)
        
    Returns:
        Dependency function that can be used with Depends()
    """
    async def dependency(
        user_data=Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> Tuple[User, int]:
        """Actual dependency function that checks minimum plan access."""
        user, org_id = user_data
        
        # Get current plan
        current_plan = get_org_plan(db, org_id)
        current_level = PLAN_HIERARCHY.get(current_plan, 0)
        required_level = PLAN_HIERARCHY.get(minimum_plan, 999)
        
        if current_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires {minimum_plan} plan or higher. Current plan: {current_plan}",
            )
        
        return user, org_id
    
    return dependency


def has_feature(user: User, org_id: int, feature_name: str, db: Session) -> bool:
    """Check if a user has access to a specific feature.
    
    Args:
        user: The user object
        org_id: The organization ID
        feature_name: The feature/capability name to check
        db: Database session
        
    Returns:
        bool: True if user has access to the feature
    """
    plan = get_org_plan(db, org_id)
    return feature_name in PLAN_CAPABILITIES.get(plan, [])
