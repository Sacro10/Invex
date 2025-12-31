# SQLAlchemy 2.0 + Alembic Migration Guide

## Overview

The backend has been refactored from raw SQLite3 to use SQLAlchemy 2.0 ORM with Alembic for database migrations. This enables:

- Support for both PostgreSQL (production) and SQLite (local development)
- Database-agnostic migrations via Alembic
- Type-safe ORM models
- Automatic pagination on all list endpoints
- Railway-ready deployment with environment variable configuration

## Key Changes

### Database Configuration

**New:** `backend/database.py`
- Configures SQLAlchemy engine based on `DATABASE_URL` environment variable
- Defaults to SQLite locally (`sqlite:///./local.db`)
- Uses PostgreSQL in production when Railway provides `DATABASE_URL`
- Session management via `get_db()` dependency

```python
from database import get_db
db: Session = Depends(get_db)
```

### ORM Models

**New:** `backend/models.py`
- 7 SQLAlchemy models mirroring original tables:
  - `TenantScreening`
  - `MaintenanceRequest`
  - `RentCollection`
  - `LeaseRenewal`
  - `Notification`
  - `Property`
  - `Lease`

### Migrations

**New:** `backend/alembic/` directory
- Alembic configuration for versioned schema management
- Initial migration already applied: `versions/16bd06c8a1e1_initial_schema_create_all_tables.py`
- All tables are created with proper indices

**Commands:**
```bash
# Create new migration after model changes
alembic revision --autogenerate -m "Description of change"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

### API Endpoints - All Refactored

All endpoints now use SQLAlchemy sessions instead of raw SQL:

#### Tenant Screening
```python
@app.post("/api/tenant-screening")
def tenant_screening(payload: ScreeningRequest, db: Session = Depends(get_db))
    # Creates TenantScreening model instance

@app.get("/api/tenant-screenings")
def get_tenant_screenings(db: Session = Depends(get_db), limit: int = 50, offset: int = 0)
    # Paginated query with limit/offset
```

#### Pagination Support

All list endpoints now support pagination:
- `limit` query param (default 50, max 500)
- `offset` query param (default 0)

**Example:**
```bash
GET /api/tenant-screenings?limit=25&offset=50
GET /api/maintenance-requests?limit=100&offset=0
GET /api/leases?limit=10&offset=100
```

#### CSV Exports

All export endpoints automatically converted to use ORM:
- `/api/export/tenant-screenings/csv`
- `/api/export/maintenance-requests/csv`
- `/api/export/rent-collections/csv`
- `/api/export/lease-renewals/csv`
- `/api/export/notifications/csv`
- `/api/export/properties/csv`
- `/api/export/leases/csv`

### Updated Pydantic Response Models

Response models remain compatible with frontend (feature-pages.js):
- `ScreeningResponse`
- `MaintenanceResponse`
- `RentCollectionResponse`
- `LeaseRenewalResponse`
- `NotificationResponse`
- `PropertyResponse`
- `LeaseResponse`
- `PulseResponse`

All responses return `id`, timestamps, and required fields as before.

## Environment Setup

### Local Development

1. **Set DATABASE_URL (optional, defaults to SQLite):**
   ```bash
   export DATABASE_URL="sqlite:///./local.db"
   ```

2. **Install dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Initialize database:**
   ```bash
   cd backend
   alembic upgrade head
   ```

4. **Run server:**
   ```bash
   uvicorn main:app --reload
   ```

Database file will be created at `backend/local.db`

### Production (Railway)

Railway automatically provides `DATABASE_URL` for PostgreSQL. The app automatically:
- Detects PostgreSQL from the URL
- Uses connection pooling with `pool_pre_ping=True` for health checks
- No additional configuration needed

**Railway deployment:**
```
- Root directory: backend
- Start command: uvicorn main:app --host 0.0.0.0 --port $PORT
- Set DATABASE_URL env var (Railway does this automatically)
```

## Frontend Compatibility

✓ **No breaking changes** - All API responses maintain the same JSON structure
✓ **Pagination is additive** - Frontend works with or without limit/offset params
✓ **CSV exports** work identically
✓ **feature-pages.js** continues to work without modification

## Data Migration (if needed)

If migrating from old SQLite database:

```bash
# Backup old database
cp backend/data.db backend/data.db.backup

# The new schema matches the old schema exactly
# All data can be preserved with a simple migration tool if needed
```

## Troubleshooting

### "No module named 'sqlalchemy'"
```bash
pip install -r backend/requirements.txt
```

### "DATABASE_URL environment variable not set"
SQLite defaults to `./local.db` - this is expected in local development

### Alembic migration errors
```bash
# Sync models with database
alembic stamp head

# Then create new migration
alembic revision --autogenerate -m "Auto sync"
alembic upgrade head
```

### PostgreSQL connection issues on Railway
- Ensure `DATABASE_URL` is set in Railway environment
- Check connection string format: `postgresql://user:pass@host:5432/dbname`
- Use `psycopg2-binary` (already in requirements)

## Performance Improvements

- **Connection pooling** - Automatic for PostgreSQL
- **Lazy loading** - Load related data only when needed
- **Index support** - All primary keys indexed, easy to add more
- **Query optimization** - SQLAlchemy can generate efficient SQL

## Next Steps

### Add Related Models (optional)
```python
# Example: Add foreign keys
class Lease(Base):
    property_id = Column(Integer, ForeignKey("properties.id"))
    property = relationship("Property")
```

### Add Caching
```python
from functools import lru_cache
@lru_cache(maxsize=128)
def get_properties(...):
    ...
```

### Add Filtering
```python
def get_tenant_screenings(
    risk_level: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(TenantScreening)
    if risk_level:
        query = query.filter(TenantScreening.risk_level == risk_level)
    return query.all()
```

## Dependencies Added

- **SQLAlchemy==2.0.23** - ORM and database abstraction
- **alembic==1.12.1** - Database migrations
- **psycopg2-binary==2.9.9** - PostgreSQL driver
- **python-dotenv==1.0.0** - Environment variable loading

See `backend/requirements.txt` for full dependency list.
