"""Seed database with test data for local development."""

from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Organization, User
from auth import hash_password


def create_test_org_and_user():
    """Create a test organization and user for local development.
    
    Only creates data if it doesn't already exist (idempotent).
    
    Usage:
        python -c "from seed import create_test_org_and_user; create_test_org_and_user()"
    """
    db = SessionLocal()
    try:
        # Check if test org already exists
        test_org = db.query(Organization).filter(
            Organization.name == "Test Company"
        ).first()
        
        if test_org is None:
            # Create test organization
            test_org = Organization(
                name="Test Company",
                created_at=datetime.utcnow()
            )
            db.add(test_org)
            db.commit()
            db.refresh(test_org)
            print(f"✓ Created organization: {test_org.name} (ID: {test_org.id})")
        else:
            print(f"✓ Organization already exists: {test_org.name} (ID: {test_org.id})")
        
        # Check if test user already exists
        test_user = db.query(User).filter(
            User.email == "admin@test.local",
            User.org_id == test_org.id
        ).first()
        
        if test_user is None:
            # Create test user
            test_user = User(
                org_id=test_org.id,
                email="admin@test.local",
                password_hash=hash_password("password123"),
                role="owner",
                created_at=datetime.utcnow()
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
            print(f"✓ Created user: {test_user.email} (ID: {test_user.id}, Role: {test_user.role})")
            print(f"  Password: password123")
        else:
            print(f"✓ User already exists: {test_user.email} (ID: {test_user.id})")
        
        print("\n✓ Seed data ready for testing")
        print(f"  Login URL: POST /api/auth/login")
        print(f"  Credentials: admin@test.local / password123")
        
    except Exception as e:
        print(f"✗ Error creating seed data: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_test_org_and_user()
