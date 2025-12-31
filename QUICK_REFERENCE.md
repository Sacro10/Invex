# Quick Reference: Completing Multi-Tenant Endpoints

## Current Status
✅ **DONE**: Auth system, database migration, tenant screening endpoints  
⏳ **TODO**: 6 endpoint groups with org_id/auth

## Copy-Paste Template for Each Endpoint Group

### For POST endpoints (create):
```python
@app.post("/api/entity", response_model=EntityResponse)
def create_entity(
    payload: EntityRequest,
    user_data=Depends(get_current_user),  # ADD THIS
    db: Session = Depends(get_db),
) -> EntityResponse:
    """Create entity."""
    user, org_id = user_data  # ADD THIS
    
    # ... existing logic ...
    
    entity = EntityModel(
        org_id=org_id,  # ADD THIS LINE
        # ... existing fields ...
    )
    # ... rest of code ...
```

### For GET list endpoints:
```python
@app.get("/api/entities")
def get_entities(
    user_data=Depends(get_current_user),  # ADD THIS
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get entities for user's org."""
    user, org_id = user_data  # ADD THIS
    
    entities = (
        db.query(EntityModel)
        .filter(EntityModel.org_id == org_id)  # ADD THIS
        .order_by(EntityModel.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    # ... rest of code ...
```

### For CSV export endpoints:
```python
@app.get("/api/export/entities/csv")
def export_entities(
    user_data=Depends(get_current_user),  # ADD THIS
    db: Session = Depends(get_db)
):
    """Export entities as CSV."""
    user, org_id = user_data  # ADD THIS
    
    entities = (
        db.query(EntityModel)
        .filter(EntityModel.org_id == org_id)  # ADD THIS
        .order_by(EntityModel.created_at.desc())
        .all()
    )
    # ... rest of code ...
```

## Endpoints to Update (in order)

### 1. Maintenance Requests (4 endpoints)
**File**: backend/main.py, lines ~462-550  
**Pattern**: POST (create), GET list, PUT update, GET CSV

```python
# POST maintenance-request (line ~462)
@app.post("/api/maintenance-request", response_model=MaintenanceResponse)
def maintenance_request(
    payload: MaintenanceRequest,
    user_data=Depends(get_current_user),  # ADD
    db: Session = Depends(get_db),
):
    """Create a maintenance request with auto vendor routing."""
    user, org_id = user_data  # ADD
    # ... existing vendor routing logic ...
    request = MaintenanceRequestModel(  # CHANGE FROM MaintenanceRequest
        org_id=org_id,  # ADD
        property_id=payload.property_id,
        # ... rest unchanged ...
    )
```

### 2. Rent Collection (3 endpoints)
**File**: backend/main.py, lines ~520-600  
**Pattern**: POST (create), GET list, GET CSV

### 3. Lease Renewals (3 endpoints)
**File**: backend/main.py, lines ~610-680  
**Pattern**: POST (create), GET list, GET CSV

### 4. Notifications (3 endpoints)
**File**: backend/main.py, lines ~730-800  
**Pattern**: POST (create), GET list, GET CSV

### 5. Properties (3 endpoints)
**File**: backend/main.py, lines ~840-910  
**Pattern**: POST (create), GET list, GET CSV

### 6. Leases (2 endpoints)
**File**: backend/main.py, lines ~940-1000  
**Pattern**: POST (create), GET list, GET CSV

### 7. Pulse Dashboard (1 endpoint)
**File**: backend/main.py, lines ~1050+  
**Change**: 
```python
@app.get("/api/pulse", response_model=PulseResponse)
def pulse(
    user_data=Depends(get_current_user),  # ADD
    db: Session = Depends(get_db)
):
    user, org_id = user_data  # ADD
    
    # Filter all queries by org_id:
    occupancy = db.query(...).filter(Table.org_id == org_id).count() / ...
    rent_collected = db.query(...).filter(RentCollectionModel.org_id == org_id).count()
    open_requests = db.query(...).filter(MaintenanceRequestModel.org_id == org_id).count()
    # ... etc for all metrics ...
```

## Model Alias Reference
These aliases are already in imports (top of main.py):

```python
TenantScreening → TenantScreeningModel  ✅ (already updated in code)
MaintenanceRequest → MaintenanceRequestModel  (update in remaining endpoints)
RentCollection → RentCollectionModel
LeaseRenewal → LeaseRenewalModel
Notification → NotificationModel
Property → PropertyModel
Lease → LeaseModel
```

## Testing Each Endpoint

```bash
# Get fresh token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.local","password":"password123"}' \
  | jq -r '.access_token')

# Test POST
curl -X POST http://localhost:8000/api/maintenance-requests \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"property_id":"123","issue":"leak","priority":"high"}'

# Test GET
curl -X GET http://localhost:8000/api/maintenance-requests \
  -H "Authorization: Bearer $TOKEN"

# Test CSV
curl -X GET http://localhost:8000/api/export/maintenance-requests/csv \
  -H "Authorization: Bearer $TOKEN"
```

## Common Gotchas

1. **Forget `Depends(get_current_user)`** - Endpoint won't have auth
   - Error: Endpoint works without token
   - Fix: Always add to function signature

2. **Forget `user, org_id = user_data`** - Tuple unpacking fails
   - Error: AttributeError: 'tuple' object has no attribute ...
   - Fix: Always unpack on first line of function

3. **Forget `.filter(Table.org_id == org_id)`** - Data leaks to other orgs
   - Error: Endpoint returns data from other orgs
   - Fix: Always add filter after query()

4. **Forget `org_id=org_id,` in create** - Records have no org_id
   - Error: 400 or 500 when creating
   - Fix: Always set org_id from user_data

5. **Use old class names** - Import conflicts
   - Error: Pydantic vs ORM class confusion
   - Fix: Use aliased names (Table → TableModel)

## Verification After Updates

```python
# In terminal, test that all endpoints require auth:
for endpoint in tenant-screening tenant-screenings maintenance-request \
                maintenance-requests rent-collection rent-collections \
                lease-renewal lease-renewals notifications properties \
                leases pulse; do
  curl -s http://localhost:8000/api/$endpoint -o /dev/null -w "GET $endpoint: %{http_code}\n"
done

# All should return 401 Unauthorized (except auth endpoints)
```

## Commit Message Template

```
chore: add multi-tenant auth to remaining endpoints

- Add get_current_user dependency to [endpoint groups]
- Filter GET queries by user's org_id
- Auto-set org_id on POST/PUT operations
- Update [X] endpoints with authentication

Endpoints updated:
- POST/GET /api/maintenance-request(s)
- POST/GET /api/rent-collection(s)
- [etc...]

Testing:
- All endpoints require valid JWT token
- Invalid/missing tokens return 401
- Queries filtered by org_id
- CSV exports filtered by org_id
```

## Time Estimate
- Maintenance: 15 min (4 endpoints, 1 requires new logic for PUT)
- Rent Collection: 10 min (3 endpoints)
- Lease Renewals: 10 min (3 endpoints)
- Notifications: 10 min (3 endpoints)
- Properties: 10 min (3 endpoints)
- Leases: 10 min (2 endpoints)
- Pulse: 15 min (needs aggregation logic per org)
- Testing: 20 min (manual curl tests)

**Total: ~2 hours** to complete all remaining endpoints
