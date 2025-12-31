"""
SQLAlchemy ORM models for multi-tenant property management system.
"""

from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Plan(str, Enum):
    CORE = "core"
    GROWTH = "growth"
    PREMIUM = "premium"


class Organization(Base):
    """Organization (tenant) in multi-tenant SaaS."""
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    properties = relationship("Property", back_populates="organization", cascade="all, delete-orphan")
    screenings = relationship("TenantScreening", back_populates="organization", cascade="all, delete-orphan")
    maintenance = relationship("MaintenanceRequest", back_populates="organization", cascade="all, delete-orphan")
    vendors = relationship("Vendor", back_populates="organization", cascade="all, delete-orphan")
    rent = relationship("RentCollection", back_populates="organization", cascade="all, delete-orphan")
    renewals = relationship("LeaseRenewal", back_populates="organization", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="organization", cascade="all, delete-orphan")
    leases = relationship("Lease", back_populates="organization", cascade="all, delete-orphan")
    checklists = relationship("MoveInChecklist", back_populates="organization", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    """User account in organization."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="staff")  # owner, admin, staff
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="users")

    def __repr__(self):
        return f"<User {self.email} (role={self.role})>"


class TenantScreening(Base):
    __tablename__ = "tenant_screenings"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    income = Column(Float, nullable=False)
    credit_score = Column(Integer, nullable=False)
    evictions = Column(Integer, nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="screenings")


class MaintenanceRequest(Base):
    __tablename__ = "maintenance_requests"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(String, nullable=False)
    issue = Column(String, nullable=False)
    priority = Column(String, nullable=False)
    vendor = Column(String, nullable=False)
    scheduled_for = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="maintenance")


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    specialties = Column(String, nullable=False)  # JSON string for specialties list
    service_zip_codes = Column(String, nullable=True)  # JSON string for zip codes list
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="vendors")


class RentCollection(Base):
    __tablename__ = "rent_collections"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    due_date = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    paid_at = Column(DateTime, nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="rent")


class LeaseRenewal(Base):
    __tablename__ = "lease_renewals"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    current_rent = Column(Float, nullable=False)
    market_rent = Column(Float, nullable=False)
    occupancy_rate = Column(Float, nullable=False)
    suggested_rent = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="renewals")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, nullable=False)
    channel = Column(String, nullable=False)
    message = Column(String, nullable=False)
    scheduled_for = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="notifications")


class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(String, nullable=False, unique=True, index=True)
    address = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)
    zip_code = Column(String, nullable=False)
    property_type = Column(String, nullable=False)
    units = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="properties")


class Lease(Base):
    __tablename__ = "leases"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, nullable=False)
    property_id = Column(String, nullable=False)
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=False)
    rent_amount = Column(Float, nullable=False)
    deposit = Column(Float, nullable=False)
    status = Column(String, default="active", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="leases")


class MoveInChecklist(Base):
    """Move-in checklist for tenants."""
    __tablename__ = "move_in_checklists"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, nullable=False)
    property_id = Column(String, nullable=False)
    items = Column(String, nullable=False)  # JSON string of checklist items
    completed_items = Column(String, nullable=False, default="[]")  # JSON string of completed item IDs
    status = Column(String, nullable=False, default="pending")  # pending, in_progress, completed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="checklists")


class Subscription(Base):
    """Subscription billing information for organizations."""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    stripe_customer_id = Column(String, nullable=False)
    stripe_subscription_id = Column(String, nullable=False)
    plan = Column(String, nullable=False)  # core, growth, premium
    unit_quantity = Column(Integer, nullable=False)
    status = Column(String, nullable=False)  # active, canceled, past_due, etc.
    current_period_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="subscriptions")


class BillingUpdateRetry(Base):
    """Queue for failed Stripe billing updates to retry later."""
    __tablename__ = "billing_update_retries"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    stripe_subscription_id = Column(String, nullable=False)
    new_quantity = Column(Integer, nullable=False)
    error_message = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)
    last_attempt = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    next_retry_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    organization = relationship("Organization")
