# INDEX Property Management SaaS

A **multi-tenant SaaS** property management platform with AI-powered tenant screening, automated maintenance routing, rent collection, and lease renewal optimization. Built with FastAPI (Python) backend and a responsive static frontend.

## 🏢 Multi-Tenant Architecture

INDEX is a **fully isolated multi-tenant system** where each organization has:
- Complete data isolation (no cross-org access)
- Independent users with role-based access (owner/admin/staff)
- JWT-based authentication with org_id enforcement
- Dedicated properties, leases, screenings, and all domain data

See [MULTI_TENANT_GUIDE.md](MULTI_TENANT_GUIDE.md) for complete architecture details.

## Features

- **🔐 Multi-Tenant**: Complete data isolation between organizations
- **👥 User Management**: Organization-scoped users with role-based access
- **🎯 Tenant Screening**: AI-driven risk scoring based on credit, income, and eviction history
- **🔧 Maintenance Routing**: Automatic vendor assignment and scheduling based on issue type
- **💰 Rent Collection**: Automated rent tracking with optional auto-pay integration
- **📋 Lease Renewal**: Market-aware pricing suggestions with confidence scoring
- **📧 Notifications**: Multi-channel tenant communication (email, SMS, portal)
- **🏠 Property Management**: Full CRUD for properties and lease portfolios
- **📊 Real-time Dashboard**: Pulse view of occupancy, rent collected, and pending requests
- **📤 Data Export**: CSV exports for screenings, maintenance, rent collections, and leases

## Quick Start

### Local Development

1. **Clone and navigate to the project:**
   ```bash
   git clone <repository>
   cd Business
   ```

2. **Install Python dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Run database migrations:**
   ```bash
   alembic upgrade head
   ```

4. **Create test organization and user (local dev only):**
   ```bash
   python -c "from seed import create_test_org_and_user; create_test_org_and_user()"
   ```
   This creates:
   - Organization: "Test Company"
   - User: `admin@test.local` / `password123` (role: owner)

5. **Run the FastAPI server:**
   ```bash
   uvicorn main:app --reload
   ```
   Server will be available at `http://localhost:8000`

6. **Get JWT token:**
   ```bash
   curl -X POST http://localhost:8000/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"admin@test.local","password":"password123"}'
   ```

7. **Use protected endpoints:**
   ```bash
   # Use the access_token from login response
   curl -X GET http://localhost:8000/api/properties \
     -H "Authorization: Bearer <your-token-here>"
   ```

8. **Access the API documentation:**
   - Swagger UI: `http://localhost:8000/api/docs`
   - ReDoc: `http://localhost:8000/api/redoc`
   - Health check: `http://localhost:8000/api/health`

9. **Test multi-tenant isolation (optional):**
   ```bash
   # Install requests if needed
   pip install requests
   
   # Run the test suite
   python test_multi_tenant.py
   ```

### Database

The application uses **SQLAlchemy 2.0 ORM** with **Alembic migrations** and supports:
- **PostgreSQL** in production (Railway provides DATABASE_URL automatically)
- **SQLite** locally (defaults to `backend/local.db`)

**Core Tables:**
- `organizations` - Tenant organizations
- `users` - Organization-scoped users with roles
- `tenant_screenings` - Tenant risk assessments (org-scoped)
- `maintenance_requests` - Maintenance work orders (org-scoped)
- `rent_collections` - Rent payment tracking (org-scoped)
- `lease_renewals` - Renewal recommendations (org-scoped)
- `notifications` - Communication queue (org-scoped)
- `properties` - Property portfolio (org-scoped)
- `leases` - Active lease agreements (org-scoped)

All domain tables include `org_id` foreign key with cascade delete.

Database management:
- Migrations via Alembic (see [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md))
- All endpoints use SQLAlchemy sessions (no raw SQL)
- Pagination support on all list endpoints (limit/offset query params)
- Automatic org_id filtering on all queries

## Deployment on Railway

### Prerequisites
- Railway account (https://railway.app)
- GitHub repository connected to Railway

### Deployment Steps

1. **Create a new Railway project and connect your GitHub repository**

2. **Configure environment variables in Railway:**
   - Go to Variables tab and add:
     - `DATABASE_URL`: Railway will auto-provision PostgreSQL; no manual setup needed
     - `SECRET_KEY`: Generate a secure random string (min 32 chars) for JWT signing
     - `CORS_ORIGINS`: Your deployment URL (e.g., `https://yourapp.railway.app`)
     - `PORT`: `8000` (or omit; Railway defaults to 8000)
     - `ACCESS_TOKEN_EXPIRE_MINUTES`: `30` (optional, defaults to 30)

3. **Set the root directory to `backend`** in Railway's deployment settings

4. **Set the start command:**
   ```
   alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

5. **Deploy:**
   - Push to main branch or manually trigger deployment in Railway dashboard
   - Railway will automatically build and deploy

### Production Notes
- **Database**: Railway auto-provides PostgreSQL via `DATABASE_URL`. The app detects it and uses it automatically.
- **Migrations**: Alembic runs via the app startup. To run manually:
  ```bash
  alembic upgrade head
  ```
- **Environment Variables**: Ensure `JWT_SECRET` is long and cryptographically random. Use environment-specific Stripe keys for test vs. production.
- **Data Persistence**: PostgreSQL on Railway persists across deployments. For SQLite, add a Volume in Railway settings (not recommended for production).

## API Reference

### Query Parameters
- **limit** (optional, default 50, max 500): Number of records per page
- **offset** (optional, default 0): Number of records to skip
- **Examples:**
  ```
  GET /api/tenant-screenings?limit=25&offset=50
  GET /api/leases?limit=100
  ```

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/docs` | Swagger UI documentation |
| POST | `/api/tenant-screening` | Screen tenant (returns risk score) |
| GET | `/api/tenant-screenings` | List all screenings |
| GET | `/api/export/tenant-screenings/csv` | Export screenings as CSV |
| POST | `/api/maintenance-request` | Create maintenance request |
| GET | `/api/maintenance-requests` | List maintenance requests |
| PUT | `/api/maintenance-requests/{id}` | Update maintenance status |
| GET | `/api/export/maintenance-requests/csv` | Export maintenance as CSV |
| POST | `/api/rent-collection` | Log rent payment |
| GET | `/api/rent-collections` | List rent collections |
| POST | `/api/lease-renewal` | Get lease renewal suggestion |
| GET | `/api/lease-renewals` | List renewal history |
| POST | `/api/notifications` | Queue notification |
| GET | `/api/notifications` | List notifications |
| POST | `/api/properties` | Add property |
| GET | `/api/properties` | List properties |
| POST | `/api/leases` | Create lease |
| GET | `/api/leases` | List leases |
| GET | `/api/pulse` | Dashboard metrics (occupancy, rent collected, open requests) |

## Pricing Plans

### Core Plan - $29/month
- Up to 50 units
- Tenant screening (unlimited)
- Basic maintenance routing
- Manual rent tracking
- Email notifications
- API access
- Monthly reports

### Growth Plan - $79/month
- Up to 500 units
- Advanced tenant analytics
- Auto-vendor assignment + scheduling
- Automated rent collection integration
- SMS + email notifications
- Custom workflows
- Weekly reports
- Priority support
- 90-day data retention

### Premium Plan - $249/month
- Unlimited units
- Full AI suite (screening, maintenance, pricing)
- Stripe payment processing
- All notification channels (email, SMS, portal)
- Custom integrations
- 24/7 support
- Daily reports
- 2-year data retention
- SLA guarantee (99.9% uptime)
- Dedicated account manager

## Project Structure

```
Business/
├── backend/
│   ├── main.py              # FastAPI application & API endpoints
│   ├── requirements.txt      # Python dependencies
│   ├── data.db              # SQLite database (created on startup, not in git)
│   ├── index.html           # Landing page
│   ├── tenant-screening.html # Tenant screening demo page
│   ├── maintenance.html      # Maintenance request page
│   ├── accounting.html       # Rent collection page
│   ├── lease-renewal.html   # Lease renewal page
│   ├── communication.html   # Notifications page
│   ├── properties.html      # Property management page
│   ├── leases.html          # Lease management page
│   ├── script.js            # Intersection observer & pulse API
│   ├── feature-pages.js     # Generic form submission handler
│   └── styles.css           # Responsive styling
├── .env.example             # Environment variable template
├── .gitignore               # Git exclusions
└── README.md                # This file
```

## Technology Stack

- **Backend**: FastAPI 0.115.6, Uvicorn 0.32.0, Pydantic 2.9.2
- **Database**: SQLite (easily upgradeable to PostgreSQL)
- **Frontend**: Vanilla HTML5, CSS3, JavaScript (no build process)
- **Deployment**: Railway (or any server supporting Python/Uvicorn)

## Railway Deployment

### Setup Steps

1. **Connect Repository**: Link your GitHub repository to Railway

2. **Project Settings**:
   - **Root Directory**: `backend`
   - **Build Command**: (leave empty - Railway auto-detects Python)
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

3. **Environment Variables**:
   ```bash
   DATABASE_URL=postgresql://...  # From Railway Postgres plugin
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   JWT_SECRET=your-secure-jwt-secret-here
   CORS_ORIGINS=https://yourdomain.com
   ENVIRONMENT=production
   ```

4. **Database Setup**:
   - Add Railway Postgres plugin to your project
   - Copy the `DATABASE_URL` from the plugin settings
   - Run migrations: `alembic upgrade head` (can be done via Railway shell or locally)

5. **Health Check**:
   - Railway will automatically detect the `/api/health` endpoint for health monitoring
   - The endpoint returns `{"status":"ok","version":"1.0.0","timestamp":"..."}`

### Important Notes

- **Static Files**: The marketing site (HTML/CSS/JS) is served from the root via FastAPI's `StaticFiles` mount
- **API Routes**: All `/api/*` routes remain available alongside static content
- **Port Configuration**: Railway automatically sets the `PORT` environment variable
- **Procfile**: A `Procfile` is included in the `backend/` directory for deterministic deployment

## Development Notes

- **No build process**: Edit HTML/CSS/JS directly; changes reflect immediately in browser
- **Hot reload**: Run FastAPI with `--reload` flag for automatic server restart on code changes
- **Static files**: Frontend is served by FastAPI's `StaticFiles` mount at root
- **CORS**: Currently allows all origins in development; restrict in production via `CORS_ORIGINS` env var
- **Validation**: All API requests use Pydantic models with built-in validation

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes and test locally
3. Commit: `git commit -am 'Add feature'`
4. Push: `git push origin feature/your-feature`
5. Submit a pull request

## License

Proprietary - INDEX Property Management SaaS
