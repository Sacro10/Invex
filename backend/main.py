from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data.db"

app = FastAPI(title="Index Property Management API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.mount("/", StaticFiles(directory=".", html=True), name="static")

@app.get("/")
def root():
    return FileResponse(BASE_DIR / "index.html")

@app.get("/styles.css")
def styles():
    return FileResponse(BASE_DIR / "styles.css")

@app.get("/script.js")
def script():
    return FileResponse(BASE_DIR / "script.js")

@app.get("/feature-pages.js")
def feature_pages():
    return FileResponse(BASE_DIR / "feature-pages.js")

@app.get("/tenant-screening.html")
def tenant_screening_page():
    return FileResponse(BASE_DIR / "tenant-screening.html")

@app.get("/maintenance.html")
def maintenance_page():
    return FileResponse(BASE_DIR / "maintenance.html")

@app.get("/accounting.html")
def accounting_page():
    return FileResponse(BASE_DIR / "accounting.html")

@app.get("/lease-renewal.html")
def lease_renewal_page():
    return FileResponse(BASE_DIR / "lease-renewal.html")

@app.get("/communication.html")
def communication_page():
    return FileResponse(BASE_DIR / "communication.html")

@app.get("/privacy.html")
def privacy_page():
    return FileResponse(BASE_DIR / "privacy.html")

@app.get("/terms.html")
def terms_page():
    return FileResponse(BASE_DIR / "terms.html")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tenant_screenings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                income REAL NOT NULL,
                credit_score INTEGER NOT NULL,
                evictions INTEGER NOT NULL,
                risk_score REAL NOT NULL,
                risk_level TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS maintenance_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id TEXT NOT NULL,
                issue TEXT NOT NULL,
                priority TEXT NOT NULL,
                vendor TEXT NOT NULL,
                scheduled_for TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rent_collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                amount REAL NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                paid_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lease_renewals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                current_rent REAL NOT NULL,
                market_rent REAL NOT NULL,
                occupancy_rate REAL NOT NULL,
                suggested_rent REAL NOT NULL,
                confidence REAL NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                message TEXT NOT NULL,
                scheduled_for TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


@app.on_event("startup")
def on_startup() -> None:
    init_db()


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


class PulseResponse(BaseModel):
    occupancy: float
    rent_collected: float
    open_requests: int
    timeline: dict


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/tenant-screenings")
def get_tenant_screenings():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM tenant_screenings ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


@app.get("/api/export/tenant-screenings/csv")
def export_tenant_screenings():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM tenant_screenings ORDER BY created_at DESC").fetchall()
    if not rows:
        return Response("No data", media_type="text/plain")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(dict(rows[0]).keys()))
    writer.writeheader()
    writer.writerows([dict(row) for row in rows])
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=tenant_screenings.csv"})


@app.post("/api/tenant-screening", response_model=ScreeningResponse)
def tenant_screening(payload: ScreeningRequest) -> ScreeningResponse:
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

    created_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO tenant_screenings (name, income, credit_score, evictions, risk_score, risk_level, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.name,
                payload.income,
                payload.credit_score,
                payload.evictions,
                risk_score,
                level,
                created_at,
            ),
        )
        screening_id = cur.lastrowid

    return ScreeningResponse(
        id=screening_id,
        risk_score=risk_score,
        risk_level=level,
        created_at=created_at,
    )


@app.post("/api/maintenance-request", response_model=MaintenanceResponse)
def maintenance_request(payload: MaintenanceRequest) -> MaintenanceResponse:
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
    status = "scheduled"
    created_at = datetime.now(timezone.utc).isoformat()

    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO maintenance_requests (property_id, issue, priority, vendor, scheduled_for, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.property_id,
                payload.issue,
                payload.priority,
                vendor,
                scheduled_for,
                status,
                created_at,
            ),
        )
        request_id = cur.lastrowid

    return MaintenanceResponse(
        id=request_id,
        vendor=vendor,
        scheduled_for=scheduled_for,
        status=status,
        created_at=created_at,
    )


@app.get("/api/maintenance-requests")
def get_maintenance_requests():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM maintenance_requests ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


@app.get("/api/export/maintenance-requests/csv")
def export_maintenance_requests():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM maintenance_requests ORDER BY created_at DESC").fetchall()
    if not rows:
        return Response("No data", media_type="text/plain")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(dict(rows[0]).keys()))
    writer.writeheader()
    writer.writerows([dict(row) for row in rows])
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=maintenance_requests.csv"})


@app.post("/api/rent-collection", response_model=RentCollectionResponse)
def rent_collection(payload: RentCollectionRequest) -> RentCollectionResponse:
    created_at = datetime.now(timezone.utc).isoformat()
    status = "scheduled"
    paid_at = None

    if payload.auto_pay:
        status = "paid"
        paid_at = datetime.now(timezone.utc).isoformat()

    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO rent_collections (tenant_id, amount, due_date, status, created_at, paid_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload.tenant_id,
                payload.amount,
                payload.due_date,
                status,
                created_at,
                paid_at,
            ),
        )
        collection_id = cur.lastrowid

    return RentCollectionResponse(
        id=collection_id,
        status=status,
        created_at=created_at,
        paid_at=paid_at,
    )


@app.get("/api/rent-collections")
def get_rent_collections():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM rent_collections ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


@app.get("/api/export/rent-collections/csv")
def export_rent_collections():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM rent_collections ORDER BY created_at DESC").fetchall()
    if not rows:
        return Response("No data", media_type="text/plain")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(dict(rows[0]).keys()))
    writer.writeheader()
    writer.writerows([dict(row) for row in rows])
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=rent_collections.csv"})


@app.post("/api/lease-renewal", response_model=LeaseRenewalResponse)
def lease_renewal(payload: LeaseRenewalRequest) -> LeaseRenewalResponse:
    market_delta = payload.market_rent - payload.current_rent
    adjustment = market_delta * (0.5 + 0.4 * payload.occupancy_rate)
    suggested = max(payload.current_rent, payload.current_rent + adjustment)
    confidence = round(0.6 + 0.3 * payload.occupancy_rate, 2)
    suggested_rent = round(suggested, 2)

    created_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO lease_renewals (current_rent, market_rent, occupancy_rate, suggested_rent, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload.current_rent,
                payload.market_rent,
                payload.occupancy_rate,
                suggested_rent,
                confidence,
                created_at,
            ),
        )
        renewal_id = cur.lastrowid

    return LeaseRenewalResponse(
        id=renewal_id,
        suggested_rent=suggested_rent,
        confidence=confidence,
        created_at=created_at,
    )


@app.get("/api/lease-renewals")
def get_lease_renewals():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM lease_renewals ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


@app.get("/api/export/lease-renewals/csv")
def export_lease_renewals():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM lease_renewals ORDER BY created_at DESC").fetchall()
    if not rows:
        return Response("No data", media_type="text/plain")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(dict(rows[0]).keys()))
    writer.writeheader()
    writer.writerows([dict(row) for row in rows])
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=lease_renewals.csv"})


@app.post("/api/notifications", response_model=NotificationResponse)
def notification(payload: NotificationRequest) -> NotificationResponse:
    created_at = datetime.now(timezone.utc).isoformat()
    status = "queued"

    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO notifications (tenant_id, channel, message, scheduled_for, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload.tenant_id,
                payload.channel,
                payload.message,
                payload.scheduled_for,
                status,
                created_at,
            ),
        )
        notification_id = cur.lastrowid

    return NotificationResponse(
        id=notification_id,
        status=status,
        created_at=created_at,
    )


@app.get("/api/notifications")
def get_notifications():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM notifications ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


@app.get("/api/export/notifications/csv")
def export_notifications():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM notifications ORDER BY created_at DESC").fetchall()
    if not rows:
        return Response("No data", media_type="text/plain")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(dict(rows[0]).keys()))
    writer.writeheader()
    writer.writerows([dict(row) for row in rows])
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=notifications.csv"})


@app.get("/api/pulse", response_model=PulseResponse)
def pulse() -> PulseResponse:
    with get_conn() as conn:
        occ_row = conn.execute(
            "SELECT AVG(occupancy_rate) AS avg_occ FROM lease_renewals"
        ).fetchone()
        occupancy = occ_row["avg_occ"] if occ_row["avg_occ"] is not None else 0.964

        rent_row = conn.execute(
            "SELECT SUM(amount) AS total_paid FROM rent_collections WHERE status = 'paid'"
        ).fetchone()
        rent_collected = rent_row["total_paid"] if rent_row["total_paid"] is not None else 0.0

        open_req_row = conn.execute(
            "SELECT COUNT(*) AS open_count FROM maintenance_requests WHERE status != 'closed'"
        ).fetchone()
        open_requests = open_req_row["open_count"] if open_req_row else 0

        maint = conn.execute(
            "SELECT issue, vendor, scheduled_for, created_at FROM maintenance_requests ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        renewal = conn.execute(
            "SELECT suggested_rent, market_rent, created_at FROM lease_renewals ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        screening = conn.execute(
            "SELECT risk_score, risk_level, name, created_at FROM tenant_screenings ORDER BY created_at DESC LIMIT 1"
        ).fetchone()

    def maintenance_text() -> str:
        if not maint:
            return "Auto-routed to vendor in minutes"
        return f"{maint['vendor']} scheduled {maint['scheduled_for']}"

    def renewal_text() -> str:
        if not renewal:
            return "AI suggested a 4.2% market update"
        delta = renewal["suggested_rent"] - renewal["market_rent"]
        change = (delta / renewal["market_rent"] * 100) if renewal["market_rent"] else 0
        return f"Suggested ${renewal['suggested_rent']:.0f} ({change:+.1f}% vs market)"

    def screening_text() -> str:
        if not screening:
            return "Risk score 82, approved"
        return f"Risk score {screening['risk_score']:.0f}, {screening['risk_level']}"

    return PulseResponse(
        occupancy=round(occupancy * 100, 1),
        rent_collected=rent_collected,
        open_requests=open_requests,
        timeline={
            "maintenance": maintenance_text(),
            "renewal": renewal_text(),
            "screening": screening_text(),
        },
    )
