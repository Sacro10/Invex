# Multi-Tenant SaaS Architecture Guide

## Overview

INDEX Property Management is a **fully multi-tenant SaaS application** with complete data isolation between organizations. Each organization has its own users, properties, and all domain data (screenings, maintenance, leases, etc.).

## Architecture

### Core Models

#### Organization
- Primary tenant entity
- Each organization is completely isolated
- One organization can have multiple users
- Cascade deletes ensure data cleanup

```python
class Organization(Base):
    id: int
    name: str (unique)
    created_at: datetime
```

#### User
- Belongs to one organization (`org_id`)
- Three roles: `owner`, `admin`, `staff`
- Email + password authentication
- JWT tokens include both `user_id` and `org_id`

```python
class User(Base):
    id: int
    org_id: int (FK → organizations.id)
    email: str
    password_hash: str
    role: str  # owner, admin, staff
    created_at: datetime
```

### Domain Models

All domain tables include `org_id` with foreign key to organizations:

- `tenant_screenings.org_id`
- `maintenance_requests.org_id`
- `rent_collections.org_id`
- `lease_renewals.org_id`
- `notifications.org_id`
- `properties.org_id`
- `leases.org_id`

All domain models use:
```python
org_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
organization = relationship("Organization", back_populates="...")
```

## Security & Data Isolation

### Authentication Flow

1. **Register**: `POST /api/auth/register`
   - Creates new organization + owner user
   - Returns JWT with `user_id` and `org_id`

2. **Login**: `POST /api/auth/login`
   - Validates credentials
   - Returns JWT with `user_id` and `org_id`

3. **Protected Endpoints**
   - All domain endpoints use `get_current_user` dependency
   - Extracts `(user, org_id)` from JWT
   - Automatically filters all queries by `org_id`

### Cross-Org Protection

**No cross-organization access is possible** because:

1. JWT tokens encode `org_id` at creation time
2. `get_current_user` validates user belongs to encoded `org_id`
3. All writes set `org_id` from authenticated user's `org_id`
4. All reads filter by `org_id` from authenticated user
5. Database foreign keys enforce referential integrity

Example protected endpoint:
```python
@app.post("/api/tenant-screening")
def tenant_screening(
    payload: ScreeningRequest,
    user_data=Depends(get_current_user),  # ← Extracts (user, org_id)
    db: Session = Depends(get_db),
):
    user, org_id = user_data
    
    # Create with org_id from authenticated user
    screening = TenantScreeningModel(
        org_id=org_id,  # ← Automatic isolation
        name=payload.name,
        # ... other fields
    )
    db.add(screening)
    db.commit()
```

## API Endpoints

### Public Endpoints (No Auth)
- `POST /api/auth/register` - Create organization + owner
- `POST /api/auth/login` - Get JWT token
- `GET /api/health` - Health check

### Protected Endpoints (Require JWT)

All endpoints below require `Authorization: Bearer <token>` header.

#### Tenant Screening
- `POST /api/tenant-screening` - Create screening
- `GET /api/tenant-screenings` - List screenings (paginated)
- `GET /api/export/tenant-screenings/csv` - Export CSV

#### Maintenance
- `POST /api/maintenance-request` - Create request
- `GET /api/maintenance-requests` - List requests (paginated)
- `PUT /api/maintenance-requests/{id}` - Update status
- `GET /api/export/maintenance-requests/csv` - Export CSV

#### Rent Collection
- `POST /api/rent-collection` - Create collection
- `GET /api/rent-collections` - List collections (paginated)
- `GET /api/export/rent-collections/csv` - Export CSV

#### Lease Renewal
- `POST /api/lease-renewal` - Get AI suggestion
- `GET /api/lease-renewals` - List renewals (paginated)
- `GET /api/export/lease-renewals/csv` - Export CSV

#### Notifications
- `POST /api/notifications` - Queue notification
- `GET /api/notifications` - List notifications (paginated)
- `GET /api/export/notifications/csv` - Export CSV

#### Properties
- `POST /api/properties` - Add property
- `GET /api/properties` - List properties (paginated)
- `GET /api/export/properties/csv` - Export CSV

#### Leases
- `POST /api/leases` - Create lease
- `GET /api/leases` - List leases (paginated)
- `GET /api/export/leases/csv` - Export CSV

#### Dashboard
- `GET /api/pulse` - Get dashboard metrics

## Database Migrations

Migrations are managed with Alembic.

### Initial Migration
```bash
# Creates all tables with multi-tenant structure
alembic upgrade 16bd06c8a1e1
```

### Multi-Tenant Migration
```bash
# Adds organizations, users, and org_id to all tables
alembic upgrade 150039bd0904
```

### Apply All Migrations
```bash
cd backend
alembic upgrade head
```

### Create New Migration
```bash
alembic revision -m "Description of changes"
```

## Development Setup

### 1. Initialize Database
```bash
cd backend
alembic upgrade head
```

### 2. Create Test Organization & User
```bash
python -c "from seed import create_test_org_and_user; create_test_org_and_user()"
```

This creates:
- Organization: "Test Company"
- User: `admin@test.local` / `password123` (role: owner)

### 3. Start Server
```bash
uvicorn main:app --reload
```

### 4. Get JWT Token
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.local","password":"password123"}'
```

Response:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user_id": 1,
  "org_id": 1,
  "email": "admin@test.local"
}
```

### 5. Use Protected Endpoints
```bash
curl -X GET http://localhost:8000/api/properties \
  -H "Authorization: Bearer eyJ..."
```

## Production Deployment

### Environment Variables
```bash
# Required
DATABASE_URL=postgresql://user:pass@host/db
SECRET_KEY=your-secret-key-min-32-chars

# Optional
CORS_ORIGINS=https://yourdomain.com
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Security Checklist
- ✅ Change `SECRET_KEY` in [auth.py](backend/auth.py)
- ✅ Use strong password hashing (bcrypt/argon2 instead of SHA256)
- ✅ Enable HTTPS only
- ✅ Set specific CORS origins
- ✅ Use PostgreSQL instead of SQLite
- ✅ Enable rate limiting on auth endpoints
- ✅ Add email verification for registration
- ✅ Implement password reset flow

### Database
The seed script only creates test data in development. In production:
- First user registers via `/api/auth/register`
- Creates new organization automatically
- Becomes owner of that organization

## Testing Multi-Tenancy

### Create Multiple Organizations
```bash
# Org 1
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "owner1@company1.com",
    "password": "pass123",
    "organization_name": "Company One"
  }'

# Org 2
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "owner2@company2.com",
    "password": "pass123",
    "organization_name": "Company Two"
  }'
```

### Verify Isolation
```bash
# Login as Org 1 owner
TOKEN1=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"owner1@company1.com","password":"pass123"}' \
  | jq -r '.access_token')

# Login as Org 2 owner
TOKEN2=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"owner2@company2.com","password":"pass123"}' \
  | jq -r '.access_token')

# Create property in Org 1
curl -X POST http://localhost:8000/api/properties \
  -H "Authorization: Bearer $TOKEN1" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "123 Main St",
    "city": "Portland",
    "state": "OR",
    "zip_code": "97201",
    "property_type": "apartment",
    "units": 10
  }'

# List properties in Org 1 (shows property)
curl -H "Authorization: Bearer $TOKEN1" \
  http://localhost:8000/api/properties

# List properties in Org 2 (empty - data isolated!)
curl -H "Authorization: Bearer $TOKEN2" \
  http://localhost:8000/api/properties
```

## Troubleshooting

### "User not found" on login
- Check email/password are correct
- Verify user exists: `sqlite3 backend/data.db "SELECT * FROM users;"`

### "Invalid token claims"
- Token missing `org_id` - regenerate by logging in again
- Check SECRET_KEY matches between token creation and validation

### Cross-org data visible
- Should never happen - file a bug!
- Check all queries include `.filter(Model.org_id == org_id)`
- Verify JWT includes correct `org_id`

### Migration errors
- Reset database: `rm backend/data.db` then `alembic upgrade head`
- Check alembic_version table: `sqlite3 backend/data.db "SELECT * FROM alembic_version;"`

## User Roles

### Owner
- First user in organization
- Full access to all features
- Can manage users (future feature)

### Admin
- Can manage properties and operations
- Cannot delete organization

### Staff
- Can view and create records
- Limited editing permissions

*Note: Role-based permissions are defined but not yet enforced in endpoints. All authenticated users currently have full access to their org's data.*

## Future Enhancements

- [ ] User invitation system
- [ ] Role-based endpoint permissions
- [ ] Organization settings/billing
- [ ] Audit logging
- [ ] Multi-factor authentication
- [ ] SSO/SAML support
- [ ] API rate limiting per organization
- [ ] Usage analytics per organization
