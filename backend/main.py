
from __future__ import annotations
# Authenticated user info endpoint
from fastapi import HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging
import uuid
from datetime import date, datetime

from contextlib import asynccontextmanager
import io
import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Tuple

from fastapi import FastAPI, Depends, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
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
    Vendor,
    VendorAssignmentCounter,
    MaintenanceDispatchLog,
    Subscription as SubscriptionModel,
    Plan,
    MoveInChecklist as MoveInChecklistModel,
)
from settings import settings

from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_capability,
    get_org_plan,
)

import stripe
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
from jose import JWTError, jwt

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET", "change-this-in-production")
ALGORITHM = "HS256"

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with production safety checks."""
    # CRITICAL: Validate settings BEFORE any other initialization
    # This ensures the app fails fast on startup if configuration is invalid
    try:
        # Force settings validation by accessing properties
        _ = settings.jwt_secret  # Triggers JWT_SECRET validation
        _ = settings.database_url  # Triggers DATABASE_URL validation
        _ = settings.environment  # Triggers ENVIRONMENT validation

        logger.info(f"✅ Environment validation passed: {settings.environment}")

    except ValueError as e:
        # Fail fast with clear error message for Railway logs
        error_msg = f"❌ CRITICAL CONFIGURATION ERROR: {e}"
        logger.error(error_msg)
        print(error_msg, flush=True)  # Ensure it appears in Railway logs
        raise RuntimeError(error_msg) from e

    # Initialize database (runs migrations)
    try:
        init_db()
        if settings.is_production:
            logger.info("✅ Database schema verified via Alembic (production)")
        else:
            logger.info(f"✅ Database initialized ({settings.environment})")
    except Exception as e:
        error_msg = f"❌ DATABASE INITIALIZATION FAILED: {e}"
        logger.error(error_msg)
        print(error_msg, flush=True)
        raise RuntimeError(error_msg) from e

    yield
    # Shutdown (if needed in the future)


app = FastAPI(
    title="INDEX Property Management API",
    version="1.0.0",
    description="AI-powered property management system with tenant screening, maintenance routing, rent collection, and lease renewal optimization.",
    docs_url="/api/docs" if settings.is_development else None,
    redoc_url="/api/redoc" if settings.is_development else None,
    openapi_url="/api/openapi.json" if settings.is_development else None,
    lifespan=lifespan,
)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S"
)

logger = logging.getLogger(__name__)

# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to all requests for correlation."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    # Add to logger context
    logging_context = {"request_id": request_id}
    logger_with_id = logging.LoggerAdapter(logger, logging_context)

    # Log request start
    logger_with_id.info(f"→ {request.method} {request.url.path}")

    try:
        response = await call_next(request)
        # Log request completion
        logger_with_id.info(f"← {request.method} {request.url.path} {response.status_code}")
        return response
    except Exception as e:
        # Log errors with request ID
        logger_with_id.error(f"💥 {request.method} {request.url.path} failed: {str(e)}")
        raise

class MeResponse(BaseModel):
    user_id: int
    org_id: int
    email: str
    role: str
    organization_name: str
    created_at: datetime

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

# Configure CORS with settings
allow_origins = settings.get_cors_origins_for_fastapi()
allow_credentials = settings.cors_allow_credentials

# Log CORS configuration (without secrets)
logger.info(
    f"CORS configured: allow_origins={allow_origins}, "
    f"allow_credentials={allow_credentials}, environment={settings.environment}"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=allow_credentials,
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


# ============================================================================
# BILLING UTILITIES
# ============================================================================

# ============================================================================
# EMAIL UTILITIES
# ============================================================================

def send_vendor_dispatch_email(db: Session, request: MaintenanceRequestModel, vendor: Vendor) -> bool:
    """Send dispatch email to vendor for maintenance request.
    
    Returns True if successful, False if failed.
    """
    try:
        sg = sendgrid.SendGridAPIClient(api_key=os.getenv("SENDGRID_API_KEY"))
        from_email = Email(os.getenv("FROM_EMAIL", "noreply@indexpm.com"))
        to_email = To(vendor.email)
        subject = f"New Maintenance Request - {request.property_id}"
        
        # Generate signed tokens for accept/decline links
        accept_token = create_access_token(
            data={
                "request_id": request.id,
                "vendor_id": vendor.id,
                "action": "accept",
                "exp": datetime.now(timezone.utc) + timedelta(days=7)  # 7 days expiry
            }
        )
        decline_token = create_access_token(
            data={
                "request_id": request.id,
                "vendor_id": vendor.id,
                "action": "decline", 
                "exp": datetime.now(timezone.utc) + timedelta(days=7)  # 7 days expiry
            }
        )
        
        base_url = os.getenv("FRONTEND_URL", "http://localhost:8000")
        accept_url = f"{base_url}/api/maintenance-requests/{request.id}/accept?token={accept_token}"
        decline_url = f"{base_url}/api/maintenance-requests/{request.id}/decline?token={decline_token}"
        
        html_content = f"""
        <html>
        <body>
            <h2>New Maintenance Request</h2>
            <p><strong>Property:</strong> {request.property_id}</p>
            <p><strong>Issue:</strong> {request.issue}</p>
            <p><strong>Priority:</strong> {request.priority.title()}</p>
            <p><strong>Scheduled For:</strong> {request.scheduled_for}</p>
            <p><strong>Status:</strong> {request.status.title()}</p>
            
            <p>Please respond to this request:</p>
            <p>
                <a href="{accept_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; margin-right: 10px;">Accept Request</a>
                <a href="{decline_url}" style="background-color: #f44336; color: white; padding: 10px 20px; text-decoration: none;">Decline Request</a>
            </p>
            
            <p>If the links don't work, you can manually accept or decline at: {base_url}</p>
        </body>
        </html>
        """
        
        content = Content("text/html", html_content)
        mail = Mail(from_email, to_email, subject, content)
        response = sg.client.mail.send.post(request_body=mail.get())
        
        # Log successful dispatch
        log_entry = MaintenanceDispatchLog(
            org_id=request.org_id,
            request_id=request.id,
            vendor_id=vendor.id,
            channel="email",
            status="sent"
        )
        db.add(log_entry)
        db.commit()
        
        return True
        
    except Exception as e:
        # Log failed dispatch
        log_entry = MaintenanceDispatchLog(
            org_id=request.org_id,
            request_id=request.id,
            vendor_id=vendor.id,
            channel="email",
            status="failed",
            error=str(e)
        )
        db.add(log_entry)
        db.commit()
        return False


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
    from datetime import datetime, timezone, timedelta
    
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
        created_at=datetime.now(timezone.utc)
    )
    db.add(org)
    db.flush()  # Get org ID without committing yet
    
    # Create user
    user = User(
        org_id=org.id,
        email=request.email,
        password_hash=hash_password(request.password),
        role="owner",  # First user is always owner
        created_at=datetime.now(timezone.utc)
    )
    db.add(user)
    
    # Create core plan subscription (free tier)
    core_subscription = SubscriptionModel(
        org_id=org.id,
        stripe_customer_id="free-tier",  # Special identifier for free core plan
        stripe_subscription_id="core-plan-free",
        plan="core",
        unit_quantity=1,  # Default for core plan
        status="active",
        current_period_end=datetime.now(timezone.utc) + timedelta(days=365*100),  # Effectively never expires
        created_at=datetime.now(timezone.utc)
    )
    db.add(core_subscription)
    
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
def health(db: Session = Depends(get_db)) -> dict:
    """
    Health check endpoint. Returns basic application status and database connectivity.
    """
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "version": "1.0.0",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
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


class MaintenanceUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(scheduled|in_progress|completed|cancelled)$")
    vendor_rating: Optional[float] = Field(None, ge=1, le=5)  # Rating when completing job


@app.put("/api/maintenance-requests/{request_id}")
def update_maintenance_request(
    request_id: int,
    payload: MaintenanceUpdateRequest,
    user_data=Depends(require_capability("maintenance_routing")),
    db: Session = Depends(get_db),
):
    """Update maintenance request status and handle vendor performance tracking."""
    user, org_id = user_data
    
    # Get the maintenance request
    request = db.query(MaintenanceRequestModel).filter(
        MaintenanceRequestModel.id == request_id,
        MaintenanceRequestModel.org_id == org_id
    ).first()
    
    if not request:
        raise HTTPException(status_code=404, detail="Maintenance request not found")
    
    old_status = request.status
    request.status = payload.status
    
    # Handle vendor performance tracking when job is completed
    if payload.status == "completed" and old_status != "completed" and request.vendor_id:
        vendor = db.query(Vendor).filter(Vendor.id == request.vendor_id).first()
        if vendor:
            vendor.jobs_completed += 1
            # Update average rating if provided
            if payload.vendor_rating is not None:
                if vendor.average_rating is None:
                    vendor.average_rating = payload.vendor_rating
                else:
                    # Calculate new average: (old_avg * completed_jobs + new_rating) / (completed_jobs + 1)
                    total_ratings = vendor.jobs_completed
                    vendor.average_rating = (
                        (vendor.average_rating * (total_ratings - 1)) + payload.vendor_rating
                    ) / total_ratings
    
    db.commit()
    
    return {
        "id": request.id,
        "status": request.status,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }


class VendorRequest(BaseModel):
    name: str
    email: str = None
    phone: str = None
    specialties: List[str] = Field(..., min_items=1)
    service_zip_codes: List[str] = None


class VendorResponse(BaseModel):
    id: int
    name: str
    email: str = None
    phone: str = None
    specialties: List[str]
    service_zip_codes: List[str] = None
    total_jobs_assigned: int
    jobs_completed: int
    average_rating: Optional[float]
    is_active: bool
    created_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class RentCollectionRequest(BaseModel):
    tenant_id: str
    amount: float = Field(..., gt=0)
    due_date: date

    @field_validator('due_date', mode='before')
    @classmethod
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

    @field_validator('scheduled_for', mode='before')
    @classmethod
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

    @field_validator('start_date', 'end_date', mode='before')
    @classmethod
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


class PropertyResponse(BaseModel):
    id: int
    property_id: str
    address: str
    city: str
    state: str
    zip_code: str
    property_type: str
    created_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CheckoutSessionRequest(BaseModel):
    plan: str  # core, growth, premium


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


@app.get("/api/tenant-screenings")
def get_tenant_screenings(
    user_data=Depends(require_capability("tenant_screening")),
    db: Session = Depends(get_db),
):
    """Get all tenant screenings for the user's organization."""
    user, org_id = user_data
    screenings = (
        db.query(TenantScreeningModel)
        .filter(TenantScreeningModel.org_id == org_id)
        .order_by(TenantScreeningModel.created_at.desc())
        .all()
    )
    
    return [
        {
            "id": s.id,
            "name": s.name,
            "income": s.income,
            "credit_score": s.credit_score,
            "evictions": s.evictions,
            "risk_score": s.risk_score,
            "risk_level": s.risk_level,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in screenings
    ]


@app.post("/api/tenant-screening", response_model=ScreeningResponse)
def tenant_screening(
    payload: ScreeningRequest,
    user_data=Depends(require_capability("tenant_screening")),
    db: Session = Depends(get_db),
) -> ScreeningResponse:
    """Screen a tenant and calculate risk score."""
    user, org_id = user_data
    
    # Check screening limits based on plan
    plan = get_org_plan(db, org_id)
    if plan == "core":
        # Free plan: 5 screenings per month
        from datetime import datetime, timezone, timedelta
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_count = db.query(TenantScreeningModel).filter(
            TenantScreeningModel.org_id == org_id,
            TenantScreeningModel.created_at >= month_start
        ).count()
        
        if monthly_count >= 5:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Free plan is limited to 5 tenant screenings per month. Upgrade to screen more tenants."
            )
    # growth and premium plans have unlimited screenings

    from datetime import datetime, timezone
    
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
    
    # Determine category from issue keywords
    issue_lower = payload.issue.lower()
    category = "general"
    if any(keyword in issue_lower for keyword in ["leak", "plumbing", "sink", "toilet", "pipe", "faucet"]):
        category = "plumbing"
    elif any(keyword in issue_lower for keyword in ["hvac", "heat", "ac", "cool", "thermostat", "furnace", "air"]):
        category = "hvac"
    elif any(keyword in issue_lower for keyword in ["electric", "outlet", "light", "power", "circuit", "wiring"]):
        category = "electrical"
    
    # Get property ZIP code for geographic matching
    property_zip = None
    property_obj = db.query(PropertyModel).filter(
        PropertyModel.org_id == org_id,
        PropertyModel.property_id == payload.property_id
    ).first()
    if property_obj:
        property_zip = property_obj.zip_code
    
    # Enhanced vendor selection with round-robin and geographic matching
    selected_vendor = None
    vendor_name = "GeneralFix Maintenance"  # Default fallback
    
    # Get or create assignment counter for this category
    counter = db.query(VendorAssignmentCounter).filter(
        VendorAssignmentCounter.org_id == org_id,
        VendorAssignmentCounter.category == category
    ).first()
    
    if not counter:
        counter = VendorAssignmentCounter(
            org_id=org_id,
            category=category,
            assignment_count=0
        )
        db.add(counter)
        db.flush()  # Get the ID without committing
    
    # Find eligible vendors
    eligible_vendors = []
    active_vendors = db.query(Vendor).filter(
        Vendor.org_id == org_id,
        Vendor.is_active == True
    ).all()
    
    for vendor in active_vendors:
        specialties = json.loads(vendor.specialties) if vendor.specialties else []
        
        # Check specialty match
        specialty_match = category in specialties or category == "general"
        
        # Check geographic match if we have property ZIP
        geo_match = True
        if property_zip and vendor.service_zip_codes:
            service_zips = json.loads(vendor.service_zip_codes)
            geo_match = property_zip in service_zips
        
        if specialty_match and geo_match:
            eligible_vendors.append(vendor)
    
    if eligible_vendors:
        # Sort vendors by last assignment time for round-robin
        # Use the counter to determine which vendor to pick next
        vendor_index = counter.assignment_count % len(eligible_vendors)
        selected_vendor = eligible_vendors[vendor_index]
        
        # Update assignment counter
        counter.assignment_count += 1
        counter.last_assigned_vendor_id = selected_vendor.id
        counter.updated_at = datetime.now(timezone.utc)
        
        # Update vendor performance metrics
        selected_vendor.total_jobs_assigned += 1
        
        vendor_name = selected_vendor.name
    elif active_vendors:
        # Fallback: use any active vendor if no eligible ones found
        selected_vendor = active_vendors[0]
        vendor_name = selected_vendor.name
        if selected_vendor:
            selected_vendor.total_jobs_assigned += 1

    base_days = {"high": 1, "medium": 2, "low": 4}[payload.priority]
    scheduled_for = (datetime.now(timezone.utc) + timedelta(days=base_days)).date().isoformat()
    created_at = datetime.now(timezone.utc)
    status = "scheduled"

    # Calculate SLA due time based on priority (hours)
    sla_hours = {"high": 2, "medium": 8, "low": 24}[payload.priority]
    sla_due_at = created_at + timedelta(hours=sla_hours)

    request = MaintenanceRequestModel(
        org_id=org_id,
        property_id=payload.property_id,
        issue=payload.issue,
        priority=payload.priority,
        vendor_id=selected_vendor.id if selected_vendor else None,
        vendor=vendor_name,
        scheduled_for=scheduled_for,
        status=status,
        created_at=created_at,
        sla_due_at=sla_due_at,
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    # Send dispatch email to vendor if assigned
    if selected_vendor and selected_vendor.email:
        send_vendor_dispatch_email(db, request, selected_vendor)

    return MaintenanceResponse(
        id=request.id,
        vendor=vendor_name,
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
            "vendor_id": r.vendor_id,
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
        fieldnames=["id", "property_id", "issue", "priority", "vendor_id", "vendor", "scheduled_for", "status", "created_at"]
    )
    writer.writeheader()
    for r in requests:
        writer.writerow({
            "id": r.id,
            "property_id": r.property_id,
            "issue": r.issue,
            "priority": r.priority,
            "vendor_id": r.vendor_id,
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
        old_status = request.status
        request.status = payload["status"]
        # Set resolved_at when status changes to completed
        if payload["status"] == "completed" and old_status != "completed":
            request.resolved_at = datetime.now(timezone.utc)
        db.commit()
    
    return {"message": "Status updated"}


@app.post("/api/maintenance-requests/{request_id}/accept")
def accept_maintenance_request(
    request_id: int,
    token: str = Query(..., description="JWT token for vendor authentication"),
    db: Session = Depends(get_db),
):
    """Accept maintenance request via signed token (vendor action)."""
    try:
        # Decode and verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        if payload.get("action") != "accept" or payload.get("request_id") != request_id:
            raise HTTPException(status_code=400, detail="Invalid token")
        
        vendor_id = payload.get("vendor_id")
        
        # Get the maintenance request
        request = db.query(MaintenanceRequestModel).filter(
            MaintenanceRequestModel.id == request_id
        ).first()
        
        if not request:
            raise HTTPException(status_code=404, detail="Maintenance request not found")
        
        # Verify vendor assignment
        if request.vendor_id != vendor_id:
            raise HTTPException(status_code=403, detail="Not authorized for this request")
        
        # Update status
        request.status = "accepted"
        request.accepted_at = datetime.now(timezone.utc)
        db.commit()
        
        return {"message": "Request accepted successfully", "status": "accepted"}
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.post("/api/maintenance-requests/{request_id}/decline")
def decline_maintenance_request(
    request_id: int,
    token: str = Query(..., description="JWT token for vendor authentication"),
    db: Session = Depends(get_db),
):
    """Decline maintenance request via signed token (vendor action)."""
    try:
        # Decode and verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        if payload.get("action") != "decline" or payload.get("request_id") != request_id:
            raise HTTPException(status_code=400, detail="Invalid token")
        
        vendor_id = payload.get("vendor_id")
        
        # Get the maintenance request
        request = db.query(MaintenanceRequestModel).filter(
            MaintenanceRequestModel.id == request_id
        ).first()
        
        if not request:
            raise HTTPException(status_code=404, detail="Maintenance request not found")
        
        # Verify vendor assignment
        if request.vendor_id != vendor_id:
            raise HTTPException(status_code=403, detail="Not authorized for this request")
        
        # Update status and clear vendor assignment
        request.status = "open"
        request.vendor_id = None
        request.vendor = "GeneralFix Maintenance"  # Reset to default
        
        # Decrement vendor job count since they declined
        vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
        if vendor and vendor.total_jobs_assigned > 0:
            vendor.total_jobs_assigned -= 1
        
        db.commit()
        
        return {"message": "Request declined. Will be reassigned.", "status": "open"}
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ============================================================================
# VENDOR MANAGEMENT ENDPOINTS
# ============================================================================

@app.post("/api/vendors", response_model=VendorResponse)
def create_vendor(
    payload: VendorRequest,
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    _=Depends(require_capability("maintenance_routing")),
) -> VendorResponse:
    """Create a new vendor."""
    user, org_id = user_data
    
    created_at = datetime.now(timezone.utc)
    
    vendor = Vendor(
        org_id=org_id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        specialties=json.dumps(payload.specialties),
        service_zip_codes=json.dumps(payload.service_zip_codes) if payload.service_zip_codes else None,
        is_active=True,
        created_at=created_at,
    )
    db.add(vendor)
    db.commit()
    db.refresh(vendor)

    return VendorResponse(
        id=vendor.id,
        name=vendor.name,
        email=vendor.email,
        phone=vendor.phone,
        specialties=json.loads(vendor.specialties),
        service_zip_codes=json.loads(vendor.service_zip_codes) if vendor.service_zip_codes else None,
        total_jobs_assigned=vendor.total_jobs_assigned,
        jobs_completed=vendor.jobs_completed,
        average_rating=vendor.average_rating,
        is_active=vendor.is_active,
        created_at=created_at,
    )


@app.get("/api/vendors")
def get_vendors(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    _=Depends(require_capability("maintenance_routing")),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get all vendors for the organization."""
    user, org_id = user_data
    
    vendors = (
        db.query(Vendor)
        .filter(Vendor.org_id == org_id)
        .order_by(Vendor.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    return [
        {
            "id": v.id,
            "name": v.name,
            "email": v.email,
            "phone": v.phone,
            "specialties": json.loads(v.specialties),
            "service_zip_codes": json.loads(v.service_zip_codes) if v.service_zip_codes else None,
            "total_jobs_assigned": v.total_jobs_assigned,
            "jobs_completed": v.jobs_completed,
            "average_rating": v.average_rating,
            "is_active": v.is_active,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in vendors
    ]


@app.put("/api/vendors/{vendor_id}", response_model=VendorResponse)
def update_vendor(
    vendor_id: int,
    payload: VendorRequest,
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    _=Depends(require_capability("maintenance_routing")),
) -> VendorResponse:
    """Update a vendor."""
    user, org_id = user_data
    
    vendor = db.query(Vendor).filter(
        Vendor.id == vendor_id,
        Vendor.org_id == org_id
    ).first()
    
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    vendor.name = payload.name
    vendor.email = payload.email
    vendor.phone = payload.phone
    vendor.specialties = json.dumps(payload.specialties)
    vendor.service_zip_codes = json.dumps(payload.service_zip_codes) if payload.service_zip_codes else None
    
    db.commit()
    db.refresh(vendor)

    return VendorResponse(
        id=vendor.id,
        name=vendor.name,
        email=vendor.email,
        phone=vendor.phone,
        specialties=json.loads(vendor.specialties),
        service_zip_codes=json.loads(vendor.service_zip_codes) if vendor.service_zip_codes else None,
        total_jobs_assigned=vendor.total_jobs_assigned,
        jobs_completed=vendor.jobs_completed,
        average_rating=vendor.average_rating,
        is_active=vendor.is_active,
        created_at=vendor.created_at,
    )


@app.delete("/api/vendors/{vendor_id}")
def delete_vendor(
    vendor_id: int,
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    _=Depends(require_capability("maintenance_routing")),
):
    """Soft delete a vendor (set is_active=false)."""
    user, org_id = user_data
    
    vendor = db.query(Vendor).filter(
        Vendor.id == vendor_id,
        Vendor.org_id == org_id
    ).first()
    
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    vendor.is_active = False
    db.commit()
    
    return {"message": "Vendor deactivated"}


# ============================================================================
# RENT COLLECTION ENDPOINTS
# ============================================================================


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
    
    # Check property limits based on plan
    plan = get_org_plan(db, org_id)
    current_count = db.query(PropertyModel).filter(PropertyModel.org_id == org_id).count()
    
    if plan == "core" and current_count >= 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Free plan is limited to 1 property. Upgrade to add more properties."
        )
    # growth and premium plans have unlimited properties
    
    created_at = datetime.now(timezone.utc)
    
    prop = PropertyModel(
        org_id=org_id,
        property_id=payload.property_id,
        address=payload.address,
        city=payload.city,
        state=payload.state,
        zip_code=payload.zip_code,
        property_type=payload.property_type,
        units=1,  # Default for now
        created_at=created_at,
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)

    return PropertyResponse(
        id=prop.id,
        property_id=prop.property_id,
        address=payload.address,
        city=payload.city,
        state=payload.state,
        zip_code=payload.zip_code,
        property_type=prop.property_type,
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

    # Update property
    prop.address = payload.address
    prop.city = payload.city
    prop.state = payload.state
    prop.zip_code = payload.zip_code
    prop.property_type = payload.property_type

    db.commit()
    db.refresh(prop)

    return PropertyResponse(
        id=prop.id,
        property_id=prop.property_id,
        address=prop.address,
        city=prop.city,
        state=prop.state,
        zip_code=prop.zip_code,
        property_type=prop.property_type,
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
        fieldnames=["id", "address", "city", "state", "zip_code", "property_type", "created_at"]
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
    
    # Check for SLA breaches and escalate if needed (only for Growth plan and above)
    from auth import get_org_plan
    plan = get_org_plan(db, org_id)
    if plan in ["growth", "premium"]:
        now = datetime.now(timezone.utc)
        breached_requests = db.query(MaintenanceRequestModel).filter(
            MaintenanceRequestModel.org_id == org_id,
            MaintenanceRequestModel.status.in_(["scheduled", "dispatched"]),
            MaintenanceRequestModel.sla_due_at < now,
            MaintenanceRequestModel.escalated == False,
            MaintenanceRequestModel.accepted_at.is_(None)
        ).all()
        
        for request in breached_requests:
            # Mark as escalated
            request.escalated = True
            
            # Find another vendor (skip the current one)
            current_vendor_id = request.vendor_id
            eligible_vendors = db.query(Vendor).filter(
                Vendor.org_id == org_id,
                Vendor.is_active == True,
                Vendor.id != current_vendor_id
            ).all()
            
            if eligible_vendors:
                # Pick the first available vendor (could implement more sophisticated logic)
                new_vendor = eligible_vendors[0]
                request.vendor_id = new_vendor.id
                request.vendor = new_vendor.name
                
                # Send new dispatch email
                send_vendor_dispatch_email(db, request, new_vendor)
                
                # Log the escalation
                log_entry = MaintenanceDispatchLog(
                    org_id=org_id,
                    maintenance_request_id=request.id,
                    vendor_id=new_vendor.id,
                    action="escalated",
                    details=f"SLA breached, reassigned from vendor {current_vendor_id} to {new_vendor.id}"
                )
                db.add(log_entry)
        
        db.commit()
    
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
            "quantity": 1,
        }],
        mode="subscription",
        success_url=os.getenv("FRONTEND_URL", "http://localhost:8000") + "/billing-success.html",
        cancel_url=os.getenv("FRONTEND_URL", "http://localhost:8000") + "/payment.html",
        metadata={"org_id": str(org_id), "plan": payload.plan},
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
        
        # Create or update subscription record
        db_sub = SubscriptionModel(
            org_id=org_id,
            stripe_customer_id=subscription.customer,
            stripe_subscription_id=subscription.id,
            plan=plan,
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
            db.commit()
    
    return {"status": "ok"}


@app.get("/api/enterprise/analytics")
def enterprise_analytics(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    _=Depends(require_capability("advanced_analytics")),
):
    """Enterprise-only analytics endpoint."""
    return {"message": "Enterprise analytics data"}


# Public home page route (no authentication required)
@app.get("/", response_class=HTMLResponse)
async def home_page():
    """Serve the public home page without authentication."""
    index_path = BASE_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Home page not found")


# Public static assets required by index.html
@app.get("/styles.css")
async def styles_css():
    """Serve styles.css for the public homepage."""
    file_path = BASE_DIR / "styles.css"
    if file_path.exists():
        return FileResponse(file_path, media_type="text/css")
    raise HTTPException(status_code=404, detail="Styles not found")


@app.get("/script.js")
async def script_js():
    """Serve script.js for the public homepage."""
    file_path = BASE_DIR / "script.js"
    if file_path.exists():
        return FileResponse(file_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Script not found")


# Public images required by index.html
@app.get("/pic1.jpeg")
async def pic1_jpeg():
    """Serve pic1.jpeg for the public homepage."""
    file_path = BASE_DIR / "pic1.jpeg"
    if file_path.exists():
        return FileResponse(file_path, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Image not found")


@app.get("/pic 2.jpeg")
async def pic2_jpeg():
    """Serve pic 2.jpeg for the public homepage."""
    file_path = BASE_DIR / "pic 2.jpeg"
    if file_path.exists():
        return FileResponse(file_path, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Image not found")


@app.get("/pic 3.jpeg")
async def pic3_jpeg():
    """Serve pic 3.jpeg for the public homepage."""
    file_path = BASE_DIR / "pic 3.jpeg"
    if file_path.exists():
        return FileResponse(file_path, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Image not found")


@app.get("/pic4.jpeg")
async def pic4_jpeg():
    """Serve pic4.jpeg for the public homepage."""
    file_path = BASE_DIR / "pic4.jpeg"
    if file_path.exists():
        return FileResponse(file_path, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Image not found")


@app.get("/pic5.jpeg")
async def pic5_jpeg():
    """Serve pic5.jpeg for the public homepage."""
    file_path = BASE_DIR / "pic5.jpeg"
    if file_path.exists():
        return FileResponse(file_path, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Image not found")


# Auth page (public for login/signup)
@app.get("/auth.html", response_class=HTMLResponse)
async def auth_page():
    """Serve auth page (public for login/signup)."""
    file_path = BASE_DIR / "auth.html"
    if file_path.exists():
        return FileResponse(file_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Page not found")


# Protected HTML pages (require authentication)
@app.get("/{page}.html", response_class=HTMLResponse)
async def protected_page(page: str, current_user: Tuple[User, int] = Depends(get_current_user)):
    """Serve protected HTML pages with authentication."""
    # List of protected pages (all HTML files except index.html and auth.html)
    protected_pages = {
        "payment", "terms", "accounting", "account", "properties",
        "communication", "billing-success", "leases", "maintenance",
        "lease-renewal", "tenant-screening", "privacy", "vendors"
    }

    if page in protected_pages:
        file_path = BASE_DIR / f"{page}.html"
        if file_path.exists():
            return FileResponse(file_path, media_type="text/html")

    raise HTTPException(status_code=404, detail="Page not found")