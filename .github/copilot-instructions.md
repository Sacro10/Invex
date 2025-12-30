# INDEX Property Management - AI Coding Guidelines

## Architecture Overview
This is a property management SaaS demo with a static frontend (HTML/CSS/JS) and FastAPI backend (Python/SQLite). The system automates tenant screening, maintenance routing, rent collection, lease renewals, and communications.

## Key Directories & Files
- `index.html` - Landing page with dashboard pulse
- `*-screening.html`, `maintenance.html`, etc. - Feature demo pages with forms
- `script.js` - Intersection observer reveals and pulse API updates
- `feature-pages.js` - Generic form submission handler for API endpoints
- `styles.css` - Custom CSS with color variables (`--ink`, `--mint`, etc.) and fonts (Space Grotesk, Spectral)
- `backend/main.py` - FastAPI app with SQLite database and AI-like scoring logic
- `backend/requirements.txt` - FastAPI (0.115.6), Uvicorn (0.32.0), Pydantic (2.9.2)

## API Patterns
- Endpoints: `/api/tenant-screening`, `/api/maintenance-request`, `/api/rent-collection`, `/api/lease-renewal`, `/api/notification`, `/api/pulse`
- Request/response models use Pydantic with validation (e.g., credit_score 300-850)
- AI scoring: Risk score = 55% credit factor + 35% income factor - eviction penalty
- Vendor auto-routing based on keywords in issue description
- Pulse aggregates occupancy, rent collected, open requests, and recent timeline items

## Frontend Patterns
- Forms use `data-endpoint` attribute for API target
- Inputs with `data-type` ("number", "int", "boolean") for parsing
- Results displayed as formatted JSON in `<pre class="result">`
- API_BASE configurable via `window.API_BASE` (default: "http://localhost:8000")
- Logo SVG inlined in each page header
- Navigation links between feature pages

## Development Workflow
- Run backend: `cd backend && uvicorn main:app --reload` (serves API on :8000)
- Serve frontend: Open `index.html` in browser or use `python -m http.server` from root
- Database: SQLite `backend/data.db` auto-created on startup
- No build process; edit HTML/JS/CSS directly

## Deployment
- Backend serves static frontend files via FastAPI StaticFiles mount
- Deploy to Railway: Set root directory to "backend", connect GitHub repo
- API_BASE defaults to relative URLs for same-origin deployment
- Database persists in container (use paid tier for production)

## Conventions
- Color scheme: Dark ink (#0f1c22), mint accents (#9fd4c7), sandy backgrounds
- Fonts: Spectral for headings, Space Grotesk for UI
- Risk levels: low (>=75), medium (>=55), high (<55)
- Maintenance priorities: high (1 day), medium (2 days), low (4 days)
- Dates in ISO format (YYYY-MM-DD)</content>
<parameter name="filePath">/Users/sacro/ai_image_recognition/Business/.github/copilot-instructions.md