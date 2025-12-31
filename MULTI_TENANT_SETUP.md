# Multi-Tenant SaaS Setup Guide

## Overview
This document describes the multi-tenant architecture migration completed in Phase 3. The system now supports:
- Multi-organization data isolation
- User authentication with JWT tokens
- Automated org_id filtering on all requests
- Role-based access control (owner/admin/staff)

## Architecture

### Database Schema Changes
- **organizations**: Stores company info with unique name constraint
- **users**: User accounts linked to organizations, with email/password_hash and role
- **All domain tables**: Now include `org_id` foreign key with cascade delete

```
organizations (id, name, created_at)
    ↓
users (id, org_id, email, password_hash, role, created_at)
tenant_screenings (id, org_id, ...)
maintenance_requests (id, org_id, ...)
rent_collections (id, org_id, ...)
lease_renewals (id, org_id, ...)
notifications (id, org_id, ...)
properties (id, org_id, ...)
leases (id, org_id, ...)
```

## Authentication Flow

### 1. User Registration
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "owner@company.com",
    "password": "secure_password",
    "organization_name": "Acme Properties"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": 1,
  "org_id": 1,
  "email": "owner@company.com"
}
```

### 2. User Login
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "owner@company.com",
    "password": "secure_password"
  }'
```

**Response:** Same as registration

### 3. Use Token in Requests
All protected endpoints require the `Authorization` header:

```bash
curl -X GET http://localhost:8000/api/tenant-screenings \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## Automatic org_id Filtering

All endpoints now automatically:
1. Extract the user from the JWT token
2. Get the user's `org_id`
3. Filter all queries by that `org_id`
4. Set `org_id` on all created records

Example - Get screening for current user's org:
```python
@app.get("/api/tenant-screenings")
def get_tenant_screenings(
    user_data=Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50),
    offset: int = Query(0),
):
    user, org_id = user_data  # Extracted from JWT token
    
    screenings = (
        db.query(TenantScreening)
        .filter(TenantScreening.org_id == org_id)  # Auto-filter
        .order_by(TenantScreening.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return screenings
```

## Local Development Setup

### 1. Apply Database Migration
```bash
cd backend
alembic upgrade head
```

### 2. Create Test Data
```bash
python seed.py
```

Output:
```
✓ Organization already exists: Test Company (ID: 1)
✓ Created user: admin@test.local (ID: 1, Role: owner)
  Password: password123

✓ Seed data ready for testing
  Login URL: POST /api/auth/login
  Credentials: admin@test.local / password123
```

### 3. Start Server
```bash
uvicorn main:app --reload
```

### 4. Test Login
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.local","password":"password123"}'
```

## Protected Endpoints

All of these endpoints now require authentication:

### Tenant Screening
- `POST /api/tenant-screening` - Create screening (auto-sets org_id)
- `GET /api/tenant-screenings` - List screenings (auto-filtered by org_id)
- `GET /api/export/tenant-screenings/csv` - Export CSV (auto-filtered)

### Maintenance
- `POST /api/maintenance-request` - Create request
- `GET /api/maintenance-requests` - List requests (auto-filtered by org_id)
- `PUT /api/maintenance-requests/{request_id}` - Update request
- `GET /api/export/maintenance-requests/csv` - Export CSV (auto-filtered)

### Rent Collection
- `POST /api/rent-collection` - Create payment
- `GET /api/rent-collections` - List payments (auto-filtered by org_id)
- `GET /api/export/rent-collections/csv` - Export CSV (auto-filtered)

### Lease Renewal
- `POST /api/lease-renewal` - Create renewal
- `GET /api/lease-renewals` - List renewals (auto-filtered by org_id)
- `GET /api/export/lease-renewals/csv` - Export CSV (auto-filtered)

### Notifications
- `POST /api/notifications` - Create notification
- `GET /api/notifications` - List notifications (auto-filtered by org_id)
- `GET /api/export/notifications/csv` - Export CSV (auto-filtered)

### Properties
- `POST /api/properties` - Create property
- `GET /api/properties` - List properties (auto-filtered by org_id)
- `GET /api/export/properties/csv` - Export CSV (auto-filtered)

### Leases
- `POST /api/leases` - Create lease
- `GET /api/leases` - List leases (auto-filtered by org_id)
- `GET /api/export/leases/csv` - Export CSV (auto-filtered)

### Pulse (Dashboard)
- `GET /api/pulse` - Get dashboard metrics (auto-filtered by org_id)

## Production Configuration

### Environment Variables
```env
# Database (PostgreSQL recommended)
DATABASE_URL=postgresql://user:password@host/database

# JWT Secret (change this in production!)
SECRET_KEY=your-super-secret-key-change-this-in-production

# CORS origins
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

### Security Checklist
- [ ] Change `SECRET_KEY` in `backend/auth.py` (use 32+ character random string)
- [ ] Set `DATABASE_URL` to PostgreSQL production instance
- [ ] Update `CORS_ORIGINS` to your domain
- [ ] Use HTTPS for all connections
- [ ] Implement rate limiting on `/api/auth/login` endpoint
- [ ] Add email verification for user registration
- [ ] Implement password reset flow
- [ ] Add audit logging for sensitive operations

## Implementation Status

### ✅ Completed
- [x] Organization and User models with relationships
- [x] All domain models updated with org_id FK
- [x] Database migration (batch mode for SQLite compatibility)
- [x] Auth utilities (password hashing, JWT tokens, user dependency)
- [x] Auth endpoints (register, login)
- [x] Tenant screening endpoints with auth/org_id filtering
- [x] CSV export with org_id filtering

### ⏳ Remaining Work
- [ ] Maintenance request endpoints with org_id
- [ ] Rent collection endpoints with org_id
- [ ] Lease renewal endpoints with org_id
- [ ] Notification endpoints with org_id
- [ ] Property/lease endpoints with org_id
- [ ] Pulse endpoint org_id filtering
- [ ] Add password reset endpoint
- [ ] Add user invite/management endpoints
- [ ] Add role-based access control (RBAC)
- [ ] Add audit logging
- [ ] Add email notifications

## Upgrading Existing Endpoints

To add auth/org_id to remaining endpoints, follow this pattern:

```python
# Before
@app.get("/api/maintenance-requests")
def get_maintenance_requests(
    db: Session = Depends(get_db),
    limit: int = Query(50),
    offset: int = Query(0),
):
    requests = (
        db.query(MaintenanceRequest)
        .order_by(MaintenanceRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [...]

# After
@app.get("/api/maintenance-requests")
def get_maintenance_requests(
    user_data=Depends(get_current_user),  # Add this
    db: Session = Depends(get_db),
    limit: int = Query(50),
    offset: int = Query(0),
):
    user, org_id = user_data  # Extract user and org_id
    
    requests = (
        db.query(MaintenanceRequest)
        .filter(MaintenanceRequest.org_id == org_id)  # Add this
        .order_by(MaintenanceRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [...]
```

## Troubleshooting

### Token Expired
If you see "Invalid authentication credentials", the token may have expired. Get a new one:
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.local","password":"password123"}'
```

### 401 Unauthorized
Missing or invalid Authorization header. Ensure it's in the format:
```
Authorization: Bearer <token>
```

### 403 Forbidden (Future)
User doesn't have permission for this action. This will be implemented with role-based access control.

## File Structure
```
backend/
├── auth.py                 # JWT, password hashing, get_current_user
├── models.py               # ORM models with org_id
├── database.py             # SQLAlchemy setup
├── seed.py                 # Create test data
├── main.py                 # FastAPI app with endpoints
├── alembic/
│   └── versions/
│       ├── 16bd06c8a1e1...py  # Initial schema
│       └── 150039bd0904...py  # Multi-tenant migration (org_id + users/orgs tables)
└── requirements.txt        # Dependencies (added passlib, python-jose)
```

## References
- FastAPI Dependency Injection: https://fastapi.tiangolo.com/tutorial/dependencies/
- JWT with Python-Jose: https://python-jose.readthedocs.io/
- SQLAlchemy Relationships: https://docs.sqlalchemy.org/en/20/orm/relationships.html
- Alembic Batch Mode: https://alembic.sqlalchemy.org/en/latest/batch.html
