# Multi-Tenant Quick Reference

## Authentication

### Register New Organization
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "owner@company.com",
    "password": "securepassword",
    "organization_name": "My Property Company"
  }'
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user_id": 1,
  "org_id": 1,
  "email": "owner@company.com"
}
```

### Login
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "owner@company.com",
    "password": "securepassword"
  }'
```

## Using Protected Endpoints

All domain endpoints require JWT token in Authorization header:

```bash
TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."

# List properties
curl -X GET http://localhost:8000/api/properties \
  -H "Authorization: Bearer $TOKEN"

# Create property
curl -X POST http://localhost:8000/api/properties \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "123 Main St",
    "city": "Portland",
    "state": "OR",
    "zip_code": "97201",
    "property_type": "apartment",
    "units": 10
  }'
```

## Common Operations

### Tenant Screening
```bash
curl -X POST http://localhost:8000/api/tenant-screening \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "income": 75000,
    "credit_score": 720,
    "evictions": 0
  }'
```

### Maintenance Request
```bash
curl -X POST http://localhost:8000/api/maintenance-request \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "property_id": "PROP-001",
    "issue": "Leaking sink in unit 2B",
    "priority": "high"
  }'
```

### Rent Collection
```bash
curl -X POST http://localhost:8000/api/rent-collection \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "TENANT-001",
    "amount": 1500.00,
    "due_date": "2025-02-01",
    "auto_pay": false
  }'
```

### Create Lease
```bash
curl -X POST http://localhost:8000/api/leases \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "TENANT-001",
    "property_id": "PROP-001",
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
    "rent_amount": 1500.00,
    "deposit": 1500.00
  }'
```

## Pagination

All list endpoints support pagination:

```bash
# First 50 items (default)
curl -X GET http://localhost:8000/api/properties \
  -H "Authorization: Bearer $TOKEN"

# Next 50 items
curl -X GET "http://localhost:8000/api/properties?offset=50&limit=50" \
  -H "Authorization: Bearer $TOKEN"

# Custom page size
curl -X GET "http://localhost:8000/api/properties?limit=100" \
  -H "Authorization: Bearer $TOKEN"
```

## Export Data

Export endpoints return CSV files:

```bash
# Export all tenant screenings
curl -X GET http://localhost:8000/api/export/tenant-screenings/csv \
  -H "Authorization: Bearer $TOKEN" \
  -o screenings.csv

# Export all maintenance requests
curl -X GET http://localhost:8000/api/export/maintenance-requests/csv \
  -H "Authorization: Bearer $TOKEN" \
  -o maintenance.csv

# Export all properties
curl -X GET http://localhost:8000/api/export/properties/csv \
  -H "Authorization: Bearer $TOKEN" \
  -o properties.csv
```

## Dashboard Metrics

```bash
curl -X GET http://localhost:8000/api/pulse \
  -H "Authorization: Bearer $TOKEN"
```

Response:
```json
{
  "occupancy": 96.4,
  "rent_collected": 125000.00,
  "open_requests": 3,
  "timeline": {
    "maintenance": "AquaFlow Plumbing scheduled 2025-01-15",
    "renewal": "Suggested $1580 (+4.2% vs market)",
    "screening": "Risk score 82, low"
  }
}
```

## Testing Multi-Tenant Isolation

### Create Two Organizations
```bash
# Organization 1
ORG1=$(curl -s -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "owner1@company1.com",
    "password": "pass123",
    "organization_name": "Company One"
  }')

TOKEN1=$(echo $ORG1 | jq -r '.access_token')

# Organization 2
ORG2=$(curl -s -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "owner2@company2.com",
    "password": "pass123",
    "organization_name": "Company Two"
  }')

TOKEN2=$(echo $ORG2 | jq -r '.access_token')
```

### Verify Data Isolation
```bash
# Create property in Org 1
curl -X POST http://localhost:8000/api/properties \
  -H "Authorization: Bearer $TOKEN1" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "100 First Ave",
    "city": "Portland",
    "state": "OR",
    "zip_code": "97201",
    "property_type": "apartment",
    "units": 20
  }'

# List properties in Org 1 (shows the property)
curl -X GET http://localhost:8000/api/properties \
  -H "Authorization: Bearer $TOKEN1"

# List properties in Org 2 (empty - data isolated!)
curl -X GET http://localhost:8000/api/properties \
  -H "Authorization: Bearer $TOKEN2"
```

## Database Operations

### Run Migrations
```bash
cd backend
alembic upgrade head
```

### Create Test Data (Local Dev Only)
```bash
python -c "from seed import create_test_org_and_user; create_test_org_and_user()"
```

### Check Database
```bash
# SQLite (local)
sqlite3 backend/local.db "SELECT * FROM organizations;"
sqlite3 backend/local.db "SELECT id, email, org_id, role FROM users;"

# PostgreSQL (production)
psql $DATABASE_URL -c "SELECT * FROM organizations;"
psql $DATABASE_URL -c "SELECT id, email, org_id, role FROM users;"
```

### Reset Database (Local Dev Only)
```bash
cd backend
rm local.db
alembic upgrade head
python -c "from seed import create_test_org_and_user; create_test_org_and_user()"
```

## Environment Variables

### Development (.env)
```bash
# Optional - defaults work for local dev
DATABASE_URL=sqlite:///./local.db
SECRET_KEY=dev-secret-key-change-in-production
CORS_ORIGINS=*
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Production (Railway)
```bash
# Required
DATABASE_URL=postgresql://user:pass@host/db  # Auto-provided by Railway
SECRET_KEY=random-secure-32-char-minimum-string

# Optional
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

## Troubleshooting

### 401 Unauthorized
- Check Authorization header: `Authorization: Bearer <token>`
- Token may be expired - login again
- Verify token includes org_id claim

### Empty Results
- Verify you're logged in as correct organization
- Check token org_id matches your organization
- Confirm data exists for your organization

### Cross-Org Access
- Should never happen - file a bug!
- All queries are filtered by org_id from JWT
- Database foreign keys enforce isolation

### Migration Errors
```bash
# Check current migration version
alembic current

# Rollback one migration
alembic downgrade -1

# Upgrade to latest
alembic upgrade head

# Reset (local dev only)
rm backend/local.db
alembic upgrade head
```

## Security Best Practices

### Production Checklist
- [ ] Change SECRET_KEY to secure random string (32+ chars)
- [ ] Use HTTPS only (Railway provides this)
- [ ] Set specific CORS_ORIGINS (not *)
- [ ] Enable rate limiting on auth endpoints
- [ ] Use strong password hashing (bcrypt already included)
- [ ] Add email verification for registration
- [ ] Implement password reset flow
- [ ] Add API key management for integrations
- [ ] Enable audit logging
- [ ] Set up monitoring and alerts

### Token Security
- Tokens expire after 30 minutes (configurable)
- Tokens include user_id and org_id
- Tokens are validated on every request
- No cross-org token reuse possible

### Password Security
- Passwords hashed with passlib/bcrypt
- Never logged or returned in responses
- Minimum length enforced (8+ chars recommended)
- Consider password complexity requirements
