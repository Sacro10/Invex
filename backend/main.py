from __future__ import annotations

import csv
import io
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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
)
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="INDEX Property Management API",
    version="1.0.0",
    description="AI-powered property management system with tenant screening, maintenance routing, rent collection, and lease renewal optimization.",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        data={"sub": user.id, "org_id": user.org_id, "email": user.email}
    )
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        org_id=user.org_id,
        email=user.email
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
        data={"sub": user.id, "org_id": user.org_id, "email": user.email}
    )
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        org_id=user.org_id,
        email=user.email
    )


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
    created_at: str


class MaintenanceRequest(BaseModel):
    property_id: str
    issue: str
    priority: str = Field(..., pattern="^(low|medium|high)$")


class MaintenanceResponse(BaseModel):
    id: int
    vendor: str
    scheduled_for: str
    status: str
    created_at: str


class RentCollectionRequest(BaseModel):
    tenant_id: str
    amount: float = Field(..., gt=0)
    due_date: str
    auto_pay: bool = False


class RentCollectionResponse(BaseModel):
    id: int
    status: str
    created_at: str
    paid_at: Optional[str]


class LeaseRenewalRequest(BaseModel):
    current_rent: float = Field(..., gt=0)
    market_rent: float = Field(..., gt=0)
    occupancy_rate: float = Field(..., ge=0, le=1)


class LeaseRenewalResponse(BaseModel):
    id: int
    suggested_rent: float
    confidence: float
    created_at: str


class NotificationRequest(BaseModel):
    tenant_id: str
    channel: str = Field(..., pattern="^(email|sms|portal)$")
    message: str
    scheduled_for: str


class NotificationResponse(BaseModel):
    id: int
    status: str
    created_at: str


class LeaseRequest(BaseModel):
    tenant_id: str
    property_id: str
    start_date: str
    end_date: str
    rent_amount: float
    deposit: float


class LeaseResponse(BaseModel):
    id: int
    status: str
    created_at: str


class PulseResponse(BaseModel):
    occupancy: float
    rent_collected: float
    open_requests: int
    timeline: dict


class PropertyRequest(BaseModel):
    address: str
    city: str
    state: str
    zip_code: str
    property_type: str = Field(..., pattern="^(apartment|house|condo|townhouse)$")
    units: int = Field(..., gt=0)


class PropertyResponse(BaseModel):
    id: int
    address: str
    city: str
    state: str
    zip_code: str
    property_type: str
    units: int
    created_at: str


@app.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict:
    """
    Health check endpoint. Returns basic application status and database connectivity.
    
    Returns:
        dict: Status information including app status and database connectivity
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


@app.get("/api/tenant-screenings")
def get_tenant_screenings(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get paginated list of tenant screenings for user's organization."""
    user, org_id = user_data
    
    screenings = (
        db.query(TenantScreeningModel)
        .filter(TenantScreeningModel.org_id == org_id)
        .order_by(TenantScreeningModel.created_at.desc())
        .limit(limit)
        .offset(offset)
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


@app.get("/api/export/tenant-screenings/csv")
def export_tenant_screenings(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export all tenant screenings as CSV for user's organization."""
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
    user_data=Depends(get_current_user),
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
    user_data=Depends(get_current_user),
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
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get paginated list of maintenance requests for user's organization."""
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
    user_data=Depends(get_current_user),
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
    db: Session = Depends(get_db)
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
    db: Session = Depends(get_db)
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
    db: Session = Depends(get_db)
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
) -> PropertyResponse:
    """Add a new property."""
    user, org_id = user_data
    
    created_at = datetime.now(timezone.utc)
    
    prop = PropertyModel(
        org_id=org_id,
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

    return PropertyResponse(
        id=prop.id,
        address=payload.address,
        city=payload.city,
        state=payload.state,
        zip_code=payload.zip_code,
        property_type=payload.property_type,
        units=payload.units,
        created_at=created_at.isoformat(),
    )


@app.get("/api/properties")
def get_properties(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
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


@app.get("/api/export/properties/csv")
def export_properties(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db)
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
    db: Session = Depends(get_db)
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


@app.get("/api/pulse", response_model=PulseResponse)
def pulse(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db)
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


app.mount("/", StaticFiles(directory=BASE_DIR, html=True), name="static")