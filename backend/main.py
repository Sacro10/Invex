
from __future__ import annotations
# Authenticated user info endpoint
from fastapi import HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging
import uuid
from datetime import date, datetime

import csv
import io
import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, Depends, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from database import get_db, init_db, engine
from models import (
    TenantScreening as TenantScreeningModel,
    MaintenanceRequest as MaintenanceRequestModel,
    RentCollection as RentCollectionModel,
    LeaseRenewal as LeaseRenewalModel,
    Notification as NotificationModel,
    Property as PropertyModel,
    Lease as LeaseModel,
    Organization,
    User,
    Subscription as SubscriptionModel,
    BillingUpdateRetry as BillingUpdateRetryModel,
    Plan,
    MoveInChecklist as MoveInChecklistModel,
)

from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_capability,
)

import stripe

class MeResponse(BaseModel):
    user_id: int
    org_id: int
    email: str
    role: str
    organization_name: str
    created_at: datetime
from fastapi.routing import APIRoute
def is_protected_route(route):
    path = getattr(route, 'path', None)
    return path and path.startswith("/api/") and not (path.startswith("/api/auth") or path == "/api/health")

def add_auth_dependency(app):
    for route in app.routes:
        if isinstance(route, APIRoute) and is_protected_route(route):
            if get_current_user not in [d.dependency for d in route.dependant.dependencies]:
                route.dependant.dependencies.append(Depends(get_current_user))

BASE_DIR = Path(__file__).resolve().parent


app = FastAPI(
    title="INDEX Property Management API",
    version="1.0.0",
    description="AI-powered property management system with tenant screening, maintenance routing, rent collection, and lease renewal optimization.",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "request_id": "%(request_id)s", "message": "%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S"
)

# Custom logger with request ID
class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = getattr(record, 'request_id', 'no-request-id')
        return True

logger = logging.getLogger(__name__)
logger.addFilter(RequestIdFilter())

class MeResponse(BaseModel):
    user_id: int
    org_id: int
    email: str
    role: str
    organization_name: str
    created_at: datetime

# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    # Add request ID to request state for exception handlers
    request.state.request_id = request_id

    # Add request ID to logging context
    class RequestIdFilter(logging.Filter):
        def filter(self, record):
            record.request_id = request_id
            return True

    # Apply filter to all handlers
    for handler in logging.getLogger().handlers:
        handler.addFilter(RequestIdFilter())

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

    # HSTS (HTTP Strict Transport Security) - only in production
    if os.getenv("ENVIRONMENT") == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Content Security Policy compatible with Google Fonts
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )
    response.headers["Content-Security-Policy"] = csp

    return response

add_auth_dependency(app)

# Configure CORS with environment variable
cors_origins = os.getenv("CORS_ORIGINS", "")
if cors_origins.strip() == "*":
    allow_origins = ["*"]
else:
    allow_origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ============================================================================
# GLOBAL EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with consistent JSON response."""
    logger.error(f"Validation error: {exc.errors()}", extra={"request_id": getattr(request.state, 'request_id', 'unknown')})
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "detail": "Invalid request data",
            "errors": exc.errors()
        }
    )

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handle database errors with consistent JSON response."""
    logger.error(f"Database error: {str(exc)}", extra={"request_id": getattr(request.state, 'request_id', 'unknown')})
    return JSONResponse(
        status_code=500,
        content={
            "error": "Database Error",
            "detail": "An internal database error occurred"
        }
    )

@app.exception_handler(stripe.error.StripeError)
async def stripe_exception_handler(request: Request, exc: stripe.error.StripeError):
    """Handle Stripe errors with consistent JSON response."""
    logger.error(f"Stripe error: {str(exc)}", extra={"request_id": getattr(request.state, 'request_id', 'unknown')})
    return JSONResponse(
        status_code=500,
        content={
            "error": "Payment Processing Error",
            "detail": "An error occurred while processing payment"
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent JSON response."""
    logger.warning(f"HTTP exception: {exc.detail}", extra={"request_id": getattr(request.state, 'request_id', 'unknown')})
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "detail": exc.detail
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors with consistent JSON response."""
    logger.error(f"Unexpected error: {str(exc)}", extra={"request_id": getattr(request.state, 'request_id', 'unknown')})
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred"
        }
    )

# ============================================================================
# STATIC FILE SERVING (commented out for production)
# ============================================================================

# app.mount("/", StaticFiles(directory=BASE_DIR, html=True), name="static")

# @app.get("/")
# def root():
#     return FileResponse(BASE_DIR / "index.html")

# @app.get("/styles.css")
# def styles():
#     return FileResponse(BASE_DIR / "styles.css")

# @app.get("/script.js")
# def script():
#     return FileResponse(BASE_DIR / "script.js")

# @app.get("/feature-pages.js")
# def feature_pages():
#     return FileResponse(BASE_DIR / "feature-pages.js")

# @app.get("/tenant-screening.html")
# def tenant_screening_page():
#     return FileResponse(BASE_DIR / "tenant-screening.html")

# @app.get("/maintenance.html")
# def maintenance_page():
#     return FileResponse(BASE_DIR / "maintenance.html")

# @app.get("/accounting.html")
# def accounting_page():
#     return FileResponse(BASE_DIR / "accounting.html")

# @app.get("/lease-renewal.html")
# def lease_renewal_page():
#     return FileResponse(BASE_DIR / "lease-renewal.html")

# @app.get("/communication.html")
# def communication_page():
#     return FileResponse(BASE_DIR / "communication.html")

# @app.get("/privacy.html")
# def privacy_page():
#     return FileResponse(BASE_DIR / "privacy.html")

# @app.get("/terms.html")
# def terms_page():
#     return FileResponse(BASE_DIR / "terms.html")

# @app.get("/properties.html")
# def properties_page():
#     return FileResponse(BASE_DIR / "properties.html")


@app.on_event("startup")
def on_startup() -> None:
    # Initialize database tables via Alembic migrations
    init_db()


# ============================================================================
# BILLING UTILITIES
# ============================================================================

def calculate_org_total_units(db: Session, org_id: int) -> int:
    """Calculate total units for an organization by summing all property units."""
    from sqlalchemy import func
    result = db.query(func.sum(PropertyModel.units)).filter(PropertyModel.org_id == org_id).scalar()
    return result or 0


def update_stripe_subscription_quantity(db: Session, org_id: int, new_quantity: int) -> bool:
    """Update Stripe subscription quantity for an organization.

    Returns True if successful, False if failed (will be queued for retry).
    """
    try:
        # Get active subscription
        sub = db.query(SubscriptionModel).filter(
            SubscriptionModel.org_id == org_id,
            SubscriptionModel.status == "active"
        ).first()

        if not sub:
            # No active subscription, nothing to update
            return True

        if sub.unit_quantity == new_quantity:
            # No change needed
            return True

        # Update Stripe subscription
        stripe.Subscription.modify(
            sub.stripe_subscription_id,
            items=[{
                'id': sub.stripe_subscription_id + '_item',  # This might need adjustment based on your Stripe setup
                'quantity': new_quantity
            }]
        )

        # Update local record
        sub.unit_quantity = new_quantity
        db.commit()

        return True

    except Exception as e:
        # Queue for retry
        retry = BillingUpdateRetryModel(
            org_id=org_id,
            stripe_subscription_id=sub.stripe_subscription_id if sub else "",
            new_quantity=new_quantity,
            error_message=str(e),
            retry_count=0,
            last_attempt=datetime.now(timezone.utc),
            next_retry_at=datetime.now(timezone.utc) + timedelta(minutes=5)  # Retry in 5 minutes
        )
        db.add(retry)
        db.commit()
        return False


def process_billing_update_retries(db: Session):
    """Process queued billing update retries."""
    from datetime import timedelta

    # Get retries ready for processing
    retries = db.query(BillingUpdateRetryModel).filter(
        BillingUpdateRetryModel.next_retry_at <= datetime.now(timezone.utc),
        BillingUpdateRetryModel.retry_count < 5  # Max 5 retries
    ).all()

    for retry in retries:
        try:
            # Attempt to update Stripe
            stripe.Subscription.modify(
                retry.stripe_subscription_id,
                items=[{
                    'id': retry.stripe_subscription_id + '_item',
                    'quantity': retry.new_quantity
                }]
            )

            # Update local subscription
            sub = db.query(SubscriptionModel).filter(
                SubscriptionModel.stripe_subscription_id == retry.stripe_subscription_id
            ).first()
            if sub:
                sub.unit_quantity = retry.new_quantity
                db.delete(retry)  # Remove successful retry
            else:
                # Subscription not found, remove retry
                db.delete(retry)

        except Exception as e:
            # Increment retry count and schedule next attempt
            retry.retry_count += 1
            retry.error_message = str(e)
            retry.last_attempt = datetime.now(timezone.utc)

            if retry.retry_count < 5:
                # Exponential backoff: 5, 15, 45, 135 minutes
                delay_minutes = 5 * (3 ** (retry.retry_count - 1))
                retry.next_retry_at = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
            else:
                # Max retries reached, log and remove
                print(f"Max retries reached for billing update: {retry.error_message}")
                db.delete(retry)

    db.commit()


# ============================================================================
# AUTH SCHEMAS & ENDPOINTS
# ============================================================================

class RegisterRequest(BaseModel):
    """Register a new user with a new organization."""
    email: str
    password: str
    organization_name: str


class LoginRequest(BaseModel):
    """Login with email and password."""
    email: str
    password: str


class AuthResponse(BaseModel):
    """Auth response with JWT token."""
    access_token: str
    token_type: str
    user_id: int
    org_id: int
    email: str
    role: str


@app.post("/api/auth/register", response_model=AuthResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user with a new organization."""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )
    
    # Create organization
    org = Organization(
        name=request.organization_name,
        created_at=datetime.utcnow()
    )
    db.add(org)
    db.flush()  # Get org ID without committing yet
    
    # Create user
    user = User(
        org_id=org.id,
        email=request.email,
        password_hash=hash_password(request.password),
        role="owner",  # First user is always owner
        created_at=datetime.utcnow()
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Generate token
    access_token = create_access_token(
        data={"sub": str(user.id), "org_id": user.org_id, "email": user.email}
    )
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        org_id=user.org_id,
        email=user.email,
        role=user.role
    )


@app.post("/api/auth/login", response_model=AuthResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password."""
    from fastapi import HTTPException, status
    
    # Find user
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Generate token
    access_token = create_access_token(
        data={"sub": str(user.id), "org_id": user.org_id, "email": user.email}
    )
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        org_id=user.org_id,
        email=user.email,
        role=user.role
    )


@app.get("/api/auth/me", response_model=MeResponse)
def get_me(user_data=Depends(get_current_user), db: Session = Depends(get_db)):
    user, org_id = user_data
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return MeResponse(
        user_id=user.id,
        org_id=org.id,
        email=user.email,
        role=user.role,
        organization_name=org.name,
        created_at=user.created_at
    )


@app.get("/api/health")
def health():
    """Health check endpoint for Railway deployment."""
    return {
        "status": "ok",
        "version": app.version,
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# DOMAIN SCHEMAS
# ============================================================================

class ScreeningRequest(BaseModel):
    name: str
    income: float = Field(..., gt=0)
    credit_score: int = Field(..., ge=300, le=850)
    evictions: int = Field(..., ge=0, le=10)


class ScreeningResponse(BaseModel):
    id: int
    risk_score: float
    risk_level: str
    created_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MaintenanceRequest(BaseModel):
    property_id: str
    issue: str
    priority: str = Field(..., pattern="^(low|medium|high)$")


class MaintenanceResponse(BaseModel):
    id: int
    vendor: str
    scheduled_for: str
    status: str
    created_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class RentCollectionRequest(BaseModel):
    tenant_id: str
    amount: float = Field(..., gt=0)
    due_date: date

    @validator('due_date', pre=True)
    def parse_due_date(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v).date()
        return v


class RentCollectionResponse(BaseModel):
    id: int
    status: str
    created_at: datetime
    paid_at: Optional[datetime]

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class LeaseRenewalRequest(BaseModel):
    current_rent: float = Field(..., gt=0)
    market_rent: float = Field(..., gt=0)
    occupancy_rate: float = Field(..., ge=0, le=1)


class LeaseRenewalResponse(BaseModel):
    id: int
    suggested_rent: float
    confidence: float
    created_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class NotificationRequest(BaseModel):
    tenant_id: str
    channel: str = Field(..., pattern="^(email|sms|portal)$")
    message: str
    scheduled_for: datetime

    @validator('scheduled_for', pre=True)
    def parse_scheduled_for(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v)
        return v


class NotificationResponse(BaseModel):
    id: int
    status: str
    created_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class LeaseRequest(BaseModel):
    tenant_id: str
    property_id: str
    start_date: date
    end_date: date
    rent_amount: float
    deposit: float

    @validator('start_date', 'end_date', pre=True)
    def parse_dates(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v).date()
        return v


class LeaseResponse(BaseModel):
    id: int
    status: str
    created_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PulseResponse(BaseModel):
    occupancy: float
    rent_collected: float
    open_requests: int
    timeline: dict


class PropertyRequest(BaseModel):
    property_id: str
    address: str
    city: str
    state: str
    zip_code: str
    property_type: str = Field(..., pattern="^(apartment|house|condo|townhouse)$")
    units: int = Field(..., gt=0)


class PropertyResponse(BaseModel):
    id: int
    property_id: str
    address: str
    city: str
    state: str
    zip_code: str
    property_type: str
    units: int
    created_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CheckoutSessionRequest(BaseModel):
    plan: str  # core, growth, premium
    units: int = Field(gt=0)


class CheckoutSessionResponse(BaseModel):
    url: str


class PortalSessionResponse(BaseModel):
    url: str


class MoveInChecklistRequest(BaseModel):
    tenant_id: str
    property_id: str
    items: List[str] = Field(..., min_items=1)


class MoveInChecklistResponse(BaseModel):
    id: int
    tenant_id: str
    property_id: str
    items: List[str]
    completed_items: List[int]
    status: str
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


@app.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict:
    """
    Health check endpoint. Returns basic application status and database connectivity.
    """
    db_status = "connected"
    try:
        db.execute("SELECT 1")
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "ok",
        "version": "1.0.0",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/admin/process-billing-retries")
def process_billing_retries(
    db: Session = Depends(get_db)
):
    """Process queued billing update retries. Call this periodically (e.g., via cron)."""
    process_billing_update_retries(db)
    return {"message": "Billing retry processing completed"}


@app.get("/api/export/tenant-screenings/csv")
def export_tenant_screenings(
    user_data=Depends(require_capability("data_export_api_access")),
    db: Session = Depends(get_db),
):
    user, org_id = user_data
    screenings = (
        db.query(TenantScreeningModel)
        .filter(TenantScreeningModel.org_id == org_id)
        .order_by(TenantScreeningModel.created_at.desc())
        .all()
    )
    if not screenings:
        return Response("No data", media_type="text/plain")
    
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["id", "name", "income", "credit_score", "evictions", "risk_score", "risk_level", "created_at"]
    )
    writer.writeheader()
    for s in screenings:
        writer.writerow({
            "id": s.id,
            "name": s.name,
            "income": s.income,
            "credit_score": s.credit_score,
            "evictions": s.evictions,
            "risk_score": s.risk_score,
            "risk_level": s.risk_level,
            "created_at": s.created_at.isoformat() if s.created_at else "",
        })
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=tenant_screenings.csv"})


@app.post("/api/tenant-screening", response_model=ScreeningResponse)
def tenant_screening(
    payload: ScreeningRequest,
    user_data=Depends(require_capability("tenant_screening")),
    db: Session = Depends(get_db),
) -> ScreeningResponse:
    """Screen a tenant and calculate risk score."""
    user, org_id = user_data
    
    credit_factor = (payload.credit_score - 300) / 550
    income_factor = min(payload.income / 100000, 1)
    eviction_penalty = payload.evictions * 0.15
    score = max(0.0, min(1.0, 0.55 * credit_factor + 0.35 * income_factor - eviction_penalty))
    risk_score = round(score * 100, 1)
    if risk_score >= 75:
        level = "low"
    elif risk_score >= 55:
        level = "medium"
    else:
        level = "high"

    created_at = datetime.now(timezone.utc)
    
    screening = TenantScreeningModel(
        org_id=org_id,
        name=payload.name,
        income=payload.income,
        credit_score=payload.credit_score,
        evictions=payload.evictions,
        risk_score=risk_score,
        risk_level=level,
        created_at=created_at,
    )
    db.add(screening)
    db.commit()
    db.refresh(screening)

    return ScreeningResponse(
        id=screening.id,
        risk_score=risk_score,
        risk_level=level,
        created_at=created_at.isoformat(),
    )


@app.post("/api/maintenance-request", response_model=MaintenanceResponse)
def maintenance_request(
    payload: MaintenanceRequest,
    user_data=Depends(require_capability("maintenance_routing")),
    db: Session = Depends(get_db),
) -> MaintenanceResponse:
    """Create a maintenance request with auto vendor routing."""
    user, org_id = user_data
    
    issue_lower = payload.issue.lower()
    if any(keyword in issue_lower for keyword in ["leak", "plumbing", "sink", "toilet"]):
        vendor = "AquaFlow Plumbing"
    elif any(keyword in issue_lower for keyword in ["hvac", "heat", "ac", "cool", "thermostat"]):
        vendor = "TempSure HVAC"
    elif any(keyword in issue_lower for keyword in ["electric", "outlet", "light", "power"]):
        vendor = "BrightWire Electric"
    else:
        vendor = "GeneralFix Maintenance"

    base_days = {"high": 1, "medium": 2, "low": 4}[payload.priority]
    scheduled_for = (datetime.now(timezone.utc) + timedelta(days=base_days)).date().isoformat()
    created_at = datetime.now(timezone.utc)
    status = "scheduled"

    request = MaintenanceRequestModel(
        org_id=org_id,
        property_id=payload.property_id,
        issue=payload.issue,
        priority=payload.priority,
        vendor=vendor,
        scheduled_for=scheduled_for,
        status=status,
        created_at=created_at,
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    return MaintenanceResponse(
        id=request.id,
        vendor=vendor,
        scheduled_for=scheduled_for,
        status=status,
        created_at=created_at.isoformat(),
    )


@app.get("/api/maintenance-requests")
def get_maintenance_requests(
    user_data=Depends(require_capability("maintenance_routing")),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    '''Get paginated list of maintenance requests for user's organization.'''
    user, org_id = user_data
    requests = (
        db.query(MaintenanceRequestModel)
        .filter(MaintenanceRequestModel.org_id == org_id)
        .order_by(MaintenanceRequestModel.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [
        {
            "id": r.id,
            "property_id": r.property_id,
            "issue": r.issue,
            "priority": r.priority,
            "vendor": r.vendor,
            "scheduled_for": r.scheduled_for,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in requests
    ]


@app.get("/api/export/maintenance-requests/csv")
def export_maintenance_requests(
    user_data=Depends(require_capability("data_export_api_access")),
    db: Session = Depends(get_db)
):
    """Export all maintenance requests as CSV for user's organization."""
    user, org_id = user_data
    
    requests = (
        db.query(MaintenanceRequestModel)
        .filter(MaintenanceRequestModel.org_id == org_id)
        .order_by(MaintenanceRequestModel.created_at.desc())
        .all()
    )
    if not requests:
        return Response("No data", media_type="text/plain")
    
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["id", "property_id", "issue", "priority", "vendor", "scheduled_for", "status", "created_at"]
    )
    writer.writeheader()
    for r in requests:
        writer.writerow({
            "id": r.id,
            "property_id": r.property_id,
            "issue": r.issue,
            "priority": r.priority,
            "vendor": r.vendor,
            "scheduled_for": r.scheduled_for,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        })
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=maintenance_requests.csv"})


@app.put("/api/maintenance-requests/{request_id}")
def update_maintenance_request(
    request_id: int,
    payload: dict,
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    _=Depends(require_capability("maintenance_routing")),
):
    """Update maintenance request status."""
    user, org_id = user_data
    
    request = db.query(MaintenanceRequestModel).filter(
        MaintenanceRequestModel.id == request_id,
        MaintenanceRequestModel.org_id == org_id
    ).first()
    if not request:
        return {"message": "Request not found"}
    
    if "status" in payload:
        request.status = payload["status"]
        db.commit()
    
    return {"message": "Status updated"}


@app.post("/api/rent-collection", response_model=RentCollectionResponse)
def rent_collection(
    payload: RentCollectionRequest,
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    _=Depends(require_capability("rent_collection")),
) -> RentCollectionResponse:
    """Record a rent collection."""
    user, org_id = user_data
    
    created_at = datetime.now(timezone.utc)
    status = "scheduled"
    paid_at = None

    if payload.auto_pay:
        status = "paid"
        paid_at = created_at

    collection = RentCollectionModel(
        org_id=org_id,
        tenant_id=payload.tenant_id,
        amount=payload.amount,
        due_date=payload.due_date,
        status=status,
        created_at=created_at,
        paid_at=paid_at,
    )
    db.add(collection)
    db.commit()
    db.refresh(collection)

    return RentCollectionResponse(
        id=collection.id,
        status=status,
        created_at=created_at.isoformat(),
        paid_at=paid_at.isoformat() if paid_at else None,
    )


@app.get("/api/rent-collections")
def get_rent_collections(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _=Depends(require_capability("rent_collection")),
):
    """Get paginated list of rent collections for user's organization."""
    user, org_id = user_data
    
    collections = (
        db.query(RentCollectionModel)
        .filter(RentCollectionModel.org_id == org_id)
        .order_by(RentCollectionModel.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [
        {
            "id": c.id,
            "tenant_id": c.tenant_id,
            "amount": c.amount,
            "due_date": c.due_date,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "paid_at": c.paid_at.isoformat() if c.paid_at else None,
        }
        for c in collections
    ]


@app.get("/api/export/rent-collections/csv")
def export_rent_collections(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    _=Depends(require_capability("data_export_api_access")),
):
    """Export all rent collections as CSV for user's organization."""
    user, org_id = user_data
    
    collections = (
        db.query(RentCollectionModel)
        .filter(RentCollectionModel.org_id == org_id)
        .order_by(RentCollectionModel.created_at.desc())
        .all()
    )
    if not collections:
        return Response("No data", media_type="text/plain")
    
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["id", "tenant_id", "amount", "due_date", "status", "created_at", "paid_at"]
    )
    writer.writeheader()
    for c in collections:
        writer.writerow({
            "id": c.id,
            "tenant_id": c.tenant_id,
            "amount": c.amount,
            "due_date": c.due_date,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else "",
            "paid_at": c.paid_at.isoformat() if c.paid_at else "",
        })
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=rent_collections.csv"})


@app.post("/api/lease-renewal", response_model=LeaseRenewalResponse)
def lease_renewal(
    payload: LeaseRenewalRequest,
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    _=Depends(require_capability("lease_renewal_intelligence")),
) -> LeaseRenewalResponse:
    """Get AI lease renewal suggestion."""
    user, org_id = user_data
    market_delta = payload.market_rent - payload.current_rent
    adjustment = market_delta * (0.5 + 0.4 * payload.occupancy_rate)
    suggested = max(payload.current_rent, payload.current_rent + adjustment)
    confidence = round(0.6 + 0.3 * payload.occupancy_rate, 2)
    suggested_rent = round(suggested, 2)

    created_at = datetime.now(timezone.utc)
    
    renewal = LeaseRenewalModel(
        org_id=org_id,
        current_rent=payload.current_rent,
        market_rent=payload.market_rent,
        occupancy_rate=payload.occupancy_rate,
        suggested_rent=suggested_rent,
        confidence=confidence,
        created_at=created_at,
    )
    db.add(renewal)
    db.commit()
    db.refresh(renewal)

    return LeaseRenewalResponse(
        id=renewal.id,
        suggested_rent=suggested_rent,
        confidence=confidence,
        created_at=created_at.isoformat(),
    )


@app.get("/api/lease-renewals")
def get_lease_renewals(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _=Depends(require_capability("lease_renewal_intelligence")),
):
    """Get paginated list of lease renewals for user's organization."""
    user, org_id = user_data
    
    renewals = (
        db.query(LeaseRenewalModel)
        .filter(LeaseRenewalModel.org_id == org_id)
        .order_by(LeaseRenewalModel.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [
        {
            "id": r.id,
            "current_rent": r.current_rent,
            "market_rent": r.market_rent,
            "occupancy_rate": r.occupancy_rate,
            "suggested_rent": r.suggested_rent,
            "confidence": r.confidence,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in renewals
    ]


@app.get("/api/export/lease-renewals/csv")
def export_lease_renewals(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    _=Depends(require_capability("data_export_api_access")),
):
    """Export all lease renewals as CSV for user's organization."""
    user, org_id = user_data
    
    renewals = (
        db.query(LeaseRenewalModel)
        .filter(LeaseRenewalModel.org_id == org_id)
        .order_by(LeaseRenewalModel.created_at.desc())
        .all()
    )
    if not renewals:
        return Response("No data", media_type="text/plain")
    
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["id", "current_rent", "market_rent", "occupancy_rate", "suggested_rent", "confidence", "created_at"]
    )
    writer.writeheader()
    for r in renewals:
        writer.writerow({
            "id": r.id,
            "current_rent": r.current_rent,
            "market_rent": r.market_rent,
            "occupancy_rate": r.occupancy_rate,
            "suggested_rent": r.suggested_rent,
            "confidence": r.confidence,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        })
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=lease_renewals.csv"})


@app.post("/api/notifications", response_model=NotificationResponse)
def notification(
    payload: NotificationRequest,
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    _=Depends(require_capability("tenant_communications")),
) -> NotificationResponse:
    """Queue a notification for a tenant."""
    user, org_id = user_data
    
    created_at = datetime.now(timezone.utc)
    status = "queued"

    notif = NotificationModel(
        org_id=org_id,
        tenant_id=payload.tenant_id,
        channel=payload.channel,
        message=payload.message,
        scheduled_for=payload.scheduled_for,
        status=status,
        created_at=created_at,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)

    return NotificationResponse(
        id=notif.id,
        status=status,
        created_at=created_at.isoformat(),
    )


@app.get("/api/notifications")
def get_notifications(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _=Depends(require_capability("tenant_communications")),
):
    """Get paginated list of notifications for user's organization."""
    user, org_id = user_data
    
    notifications = (
        db.query(NotificationModel)
        .filter(NotificationModel.org_id == org_id)
        .order_by(NotificationModel.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [
        {
            "id": n.id,
            "tenant_id": n.tenant_id,
            "channel": n.channel,
            "message": n.message,
            "scheduled_for": n.scheduled_for,
            "status": n.status,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifications
    ]


@app.get("/api/export/notifications/csv")
def export_notifications(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    _=Depends(require_capability("data_export_api_access")),
):
    """Export all notifications as CSV for user's organization."""
    user, org_id = user_data
    
    notifications = (
        db.query(NotificationModel)
        .filter(NotificationModel.org_id == org_id)
        .order_by(NotificationModel.created_at.desc())
        .all()
    )
    if not notifications:
        return Response("No data", media_type="text/plain")
    
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["id", "tenant_id", "channel", "message", "scheduled_for", "status", "created_at"]
    )
    writer.writeheader()
    for n in notifications:
        writer.writerow({
            "id": n.id,
            "tenant_id": n.tenant_id,
            "channel": n.channel,
            "message": n.message,
            "scheduled_for": n.scheduled_for,
            "status": n.status,
            "created_at": n.created_at.isoformat() if n.created_at else "",
        })
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=notifications.csv"})


@app.post("/api/properties", response_model=PropertyResponse)
def add_property(
    payload: PropertyRequest,
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    _=Depends(require_capability("property_management")),
) -> PropertyResponse:
    """Add a new property."""
    user, org_id = user_data
    
    created_at = datetime.now(timezone.utc)
    
    prop = PropertyModel(
        org_id=org_id,
        property_id=payload.property_id,
        address=payload.address,
        city=payload.city,
        state=payload.state,
        zip_code=payload.zip_code,
        property_type=payload.property_type,
        units=payload.units,
        created_at=created_at,
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)

    # Update billing with new total units
    total_units = calculate_org_total_units(db, org_id)
    update_stripe_subscription_quantity(db, org_id, total_units)

    return PropertyResponse(
        id=prop.id,
        property_id=prop.property_id,
        address=payload.address,
        city=payload.city,
        state=payload.state,
        zip_code=payload.zip_code,
        property_type=prop.property_type,
        units=prop.units,
        created_at=created_at,
    )


@app.get("/api/properties")
def get_properties(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _=Depends(require_capability("property_management")),
):
    """Get paginated list of properties for user's organization."""
    user, org_id = user_data
    
    properties = (
        db.query(PropertyModel)
        .filter(PropertyModel.org_id == org_id)
        .order_by(PropertyModel.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [
        {
            "id": p.id,
            "property_id": p.property_id,
            "address": p.address,
            "city": p.city,
            "state": p.state,
            "zip_code": p.zip_code,
            "property_type": p.property_type,
            "units": p.units,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in properties
    ]


@app.put("/api/properties/{property_id}", response_model=PropertyResponse)
def update_property(
    property_id: int,
    payload: PropertyRequest,
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    _=Depends(require_capability("property_management")),
) -> PropertyResponse:
    """Update a property and recalculate billing if units changed."""
    user, org_id = user_data

    # Get existing property
    prop = db.query(PropertyModel).filter(
        PropertyModel.id == property_id,
        PropertyModel.org_id == org_id
    ).first()

    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    old_units = prop.units
    new_units = payload.units

    # Update property
    prop.address = payload.address
    prop.city = payload.city
    prop.state = payload.state
    prop.zip_code = payload.zip_code
    prop.property_type = payload.property_type
    prop.units = new_units

    db.commit()
    db.refresh(prop)

    # If units changed, update billing
    if old_units != new_units:
        total_units = calculate_org_total_units(db, org_id)
        update_stripe_subscription_quantity(db, org_id, total_units)

    return PropertyResponse(
        id=prop.id,
        address=prop.address,
        city=prop.city,
        state=prop.state,
        zip_code=prop.zip_code,
        property_type=prop.property_type,
        units=prop.units,
        created_at=prop.created_at.isoformat(),
    )


@app.get("/api/export/properties/csv")
def export_properties(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    _=Depends(require_capability("data_export_api_access")),
):
    """Export all properties as CSV for user's organization."""
    user, org_id = user_data
    
    properties = (
        db.query(PropertyModel)
        .filter(PropertyModel.org_id == org_id)
        .order_by(PropertyModel.created_at.desc())
        .all()
    )
    if not properties:
        return Response("No data", media_type="text/plain")
    
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["id", "address", "city", "state", "zip_code", "property_type", "units", "created_at"]
    )
    writer.writeheader()
    for p in properties:
        writer.writerow({
            "id": p.id,
            "address": p.address,
            "city": p.city,
            "state": p.state,
            "zip_code": p.zip_code,
            "property_type": p.property_type,
            "units": p.units,
            "created_at": p.created_at.isoformat() if p.created_at else "",
        })
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=properties.csv"})


@app.post("/api/leases", response_model=LeaseResponse)
def create_lease(
    payload: LeaseRequest,
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    _=Depends(require_capability("lease_management")),
) -> LeaseResponse:
    """Create a new lease."""
    user, org_id = user_data
    
    created_at = datetime.now(timezone.utc)
    status = "active"

    lease = LeaseModel(
        org_id=org_id,
        tenant_id=payload.tenant_id,
        property_id=payload.property_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        rent_amount=payload.rent_amount,
        deposit=payload.deposit,
        status=status,
        created_at=created_at,
    )
    db.add(lease)
    db.commit()
    db.refresh(lease)

    return LeaseResponse(
        id=lease.id,
        status=status,
        created_at=created_at.isoformat(),
    )


@app.get("/api/leases")
def get_leases(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _=Depends(require_capability("lease_management")),
):
    """Get paginated list of leases for user's organization."""
    user, org_id = user_data
    
    leases = (
        db.query(LeaseModel)
        .filter(LeaseModel.org_id == org_id)
        .order_by(LeaseModel.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [
        {
            "id": l.id,
            "tenant_id": l.tenant_id,
            "property_id": l.property_id,
            "start_date": l.start_date,
            "end_date": l.end_date,
            "rent_amount": l.rent_amount,
            "deposit": l.deposit,
            "status": l.status,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in leases
    ]


@app.get("/api/export/leases/csv")
def export_leases(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    _=Depends(require_capability("data_export_api_access")),
):
    """Export all leases as CSV for user's organization."""
    user, org_id = user_data
    
    leases = (
        db.query(LeaseModel)
        .filter(LeaseModel.org_id == org_id)
        .order_by(LeaseModel.created_at.desc())
        .all()
    )
    if not leases:
        return Response("No data", media_type="text/plain")
    
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["id", "tenant_id", "property_id", "start_date", "end_date", "rent_amount", "deposit", "status", "created_at"]
    )
    writer.writeheader()
    for l in leases:
        writer.writerow({
            "id": l.id,
            "tenant_id": l.tenant_id,
            "property_id": l.property_id,
            "start_date": l.start_date,
            "end_date": l.end_date,
            "rent_amount": l.rent_amount,
            "deposit": l.deposit,
            "status": l.status,
            "created_at": l.created_at.isoformat() if l.created_at else "",
        })
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=leases.csv"})


@app.post("/api/move-in-checklists", response_model=MoveInChecklistResponse)
def create_move_in_checklist(
    payload: MoveInChecklistRequest,
    user_data=Depends(require_capability("move_in_checklist")),
    db: Session = Depends(get_db),
) -> MoveInChecklistResponse:
    """Create a move-in checklist for a tenant."""
    user, org_id = user_data
    
    created_at = datetime.now(timezone.utc)
    
    # Default checklist items if none provided
    if not payload.items:
        payload.items = [
            "Keys received",
            "Lease signed",
            "Security deposit paid",
            "Utilities transferred",
            "Move-in inspection completed",
            "Welcome packet provided"
        ]
    
    checklist = MoveInChecklistModel(
        org_id=org_id,
        tenant_id=payload.tenant_id,
        property_id=payload.property_id,
        items=json.dumps(payload.items),
        completed_items=json.dumps([]),
        status="pending",
        created_at=created_at,
    )
    db.add(checklist)
    db.commit()
    db.refresh(checklist)

    return MoveInChecklistResponse(
        id=checklist.id,
        tenant_id=checklist.tenant_id,
        property_id=checklist.property_id,
        items=json.loads(checklist.items),
        completed_items=json.loads(checklist.completed_items),
        status=checklist.status,
        created_at=created_at.isoformat(),
        completed_at=checklist.completed_at.isoformat() if checklist.completed_at else None,
    )


@app.get("/api/move-in-checklists")
def get_move_in_checklists(
    user_data=Depends(require_capability("move_in_checklist")),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get paginated list of move-in checklists for user's organization."""
    user, org_id = user_data
    
    checklists = (
        db.query(MoveInChecklistModel)
        .filter(MoveInChecklistModel.org_id == org_id)
        .order_by(MoveInChecklistModel.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [
        {
            "id": c.id,
            "tenant_id": c.tenant_id,
            "property_id": c.property_id,
            "items": json.loads(c.items),
            "completed_items": json.loads(c.completed_items),
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "completed_at": c.completed_at.isoformat() if c.completed_at else None,
        }
        for c in checklists
    ]


@app.put("/api/move-in-checklists/{checklist_id}")
def update_move_in_checklist(
    checklist_id: int,
    payload: dict,
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    _=Depends(require_capability("move_in_checklist")),
):
    """Update move-in checklist status or completed items."""
    user, org_id = user_data
    
    checklist = db.query(MoveInChecklistModel).filter(
        MoveInChecklistModel.id == checklist_id,
        MoveInChecklistModel.org_id == org_id
    ).first()
    if not checklist:
        return {"message": "Checklist not found"}
    
    if "completed_items" in payload:
        checklist.completed_items = json.dumps(payload["completed_items"])
        # Update status based on completion
        items = json.loads(checklist.items)
        completed = payload["completed_items"]
        if len(completed) == len(items):
            checklist.status = "completed"
            checklist.completed_at = datetime.now(timezone.utc)
        elif len(completed) > 0:
            checklist.status = "in_progress"
        else:
            checklist.status = "pending"
        db.commit()
    
    return {"message": "Checklist updated"}


@app.get("/api/pulse", response_model=PulseResponse)
def pulse(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    _=Depends(require_capability("basic_reporting")),
) -> PulseResponse:
    """Get dashboard metrics for user's organization: occupancy, rent collected, open requests, recent timeline."""
    user, org_id = user_data
    
    from sqlalchemy import func
    
    # Get average occupancy from recent renewals (filtered by org_id)
    occ_row = db.query(func.avg(LeaseRenewalModel.occupancy_rate)).filter(
        LeaseRenewalModel.org_id == org_id
    ).first()
    occupancy = occ_row[0] if occ_row[0] is not None else 0.964

    # Get total rent collected (filtered by org_id)
    rent_row = db.query(func.sum(RentCollectionModel.amount)).filter(
        RentCollectionModel.status == "paid",
        RentCollectionModel.org_id == org_id
    ).first()
    rent_collected = rent_row[0] if rent_row[0] is not None else 0.0

    # Get count of open maintenance requests (filtered by org_id)
    open_req_count = db.query(func.count(MaintenanceRequestModel.id)).filter(
        MaintenanceRequestModel.status != "closed",
        MaintenanceRequestModel.org_id == org_id
    ).scalar() or 0

    # Get most recent maintenance, renewal, screening for timeline (filtered by org_id)
    maint = db.query(MaintenanceRequestModel).filter(
        MaintenanceRequestModel.org_id == org_id
    ).order_by(MaintenanceRequestModel.created_at.desc()).first()
    renewal = db.query(LeaseRenewalModel).filter(
        LeaseRenewalModel.org_id == org_id
    ).order_by(LeaseRenewalModel.created_at.desc()).first()
    screening = db.query(TenantScreeningModel).filter(
        TenantScreeningModel.org_id == org_id
    ).order_by(TenantScreeningModel.created_at.desc()).first()

    def maintenance_text() -> str:
        if not maint:
            return "Auto-routed to vendor in minutes"
        return f"{maint.vendor} scheduled {maint.scheduled_for}"

    def renewal_text() -> str:
        if not renewal:
            return "AI suggested a 4.2% market update"
        delta = renewal.suggested_rent - renewal.market_rent
        change = (delta / renewal.market_rent * 100) if renewal.market_rent else 0
        return f"Suggested ${renewal.suggested_rent:.0f} ({change:+.1f}% vs market)"

    def screening_text() -> str:
        if not screening:
            return "Risk score 82, approved"
        return f"Risk score {screening.risk_score:.0f}, {screening.risk_level}"

    return PulseResponse(
        occupancy=round(occupancy * 100, 1),
        rent_collected=rent_collected,
        open_requests=open_req_count,
        timeline={
            "maintenance": maintenance_text(),
            "renewal": renewal_text(),
            "screening": screening_text(),
        },
    )


@app.post("/api/billing/create-checkout-session", response_model=CheckoutSessionResponse)
def create_checkout_session(
    payload: CheckoutSessionRequest,
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CheckoutSessionResponse:
    """Create a Stripe checkout session for subscription."""
    user, org_id = user_data
    
    # Validate plan
    if payload.plan not in [p.value for p in Plan]:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    # Get price ID from env
    price_map = {
        "core": os.getenv("STRIPE_PRICE_CORE"),
        "growth": os.getenv("STRIPE_PRICE_GROWTH"),
        "premium": os.getenv("STRIPE_PRICE_PREMIUM"),
    }
    price_id = price_map.get(payload.plan)
    if not price_id:
        raise HTTPException(status_code=500, detail="Price not configured")
    
    # Get or create Stripe customer
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    customer_id = None
    existing_sub = db.query(SubscriptionModel).filter(SubscriptionModel.org_id == org_id).first()
    if existing_sub:
        customer_id = existing_sub.stripe_customer_id
    else:
        # Create new customer
        customer = stripe.Customer.create(
            email=user.email,
            name=org.name,
            metadata={"org_id": str(org_id)}
        )
        customer_id = customer.id
    
    # Create checkout session
    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{
            "price": price_id,
            "quantity": payload.units,
        }],
        mode="subscription",
        success_url=os.getenv("FRONTEND_URL", "http://localhost:8000") + "/billing-success.html",
        cancel_url=os.getenv("FRONTEND_URL", "http://localhost:8000") + "/payment.html",
        metadata={"org_id": str(org_id), "plan": payload.plan, "units": str(payload.units)},
    )
    
    return CheckoutSessionResponse(url=session.url)


@app.post("/api/billing/create-portal-session", response_model=PortalSessionResponse)
def create_portal_session(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PortalSessionResponse:
    """Create a Stripe billing portal session."""
    user, org_id = user_data
    
    # Get subscription
    sub = db.query(SubscriptionModel).filter(SubscriptionModel.org_id == org_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription found")
    
    # Create portal session
    session = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=os.getenv("FRONTEND_URL", "http://localhost:8000") + "/index.html",
    )
    
    return PortalSessionResponse(url=session.url)


@app.post("/api/billing/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Handle Stripe webhooks."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle the event
    if event.type == "customer.subscription.created":
        subscription = event.data.object
        org_id = int(subscription.metadata.get("org_id"))
        plan = subscription.metadata.get("plan")
        units = int(subscription.metadata.get("units"))
        
        # Create or update subscription record
        db_sub = SubscriptionModel(
            org_id=org_id,
            stripe_customer_id=subscription.customer,
            stripe_subscription_id=subscription.id,
            plan=plan,
            unit_quantity=units,
            status=subscription.status,
            current_period_end=datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc),
        )
        db.add(db_sub)
        db.commit()
    
    elif event.type in ["customer.subscription.updated", "customer.subscription.deleted"]:
        subscription = event.data.object
        db_sub = db.query(SubscriptionModel).filter(
            SubscriptionModel.stripe_subscription_id == subscription.id
        ).first()
        if db_sub:
            db_sub.status = subscription.status
            db_sub.current_period_end = datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc)
            if hasattr(subscription, 'quantity'):
                db_sub.unit_quantity = subscription.quantity
            db.commit()
    
    return {"status": "ok"}


app.mount("/", StaticFiles(directory=BASE_DIR, html=True), name="static")