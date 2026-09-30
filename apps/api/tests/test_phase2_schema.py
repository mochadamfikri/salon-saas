"""Tests for Phase 2 Salon Operations Core schema, constraints, and relationships."""

import uuid
from datetime import time

import pytest
from app.core.dependencies import get_db
from app.db import engine
from app.models import Salon, SalonCustomer, SalonService, StaffProfile, User
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError


def test_phase2_tables_exist() -> None:
    """Verify all Phase 2 Salon Operations Core tables exist in the database."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    expected_phase2_tables = {
        "salon_services",
        "staff_profiles",
        "staff_service_assignments",
        "staff_weekly_availability",
        "salon_customers",
    }
    assert expected_phase2_tables.issubset(table_names)


def test_salon_service_requires_salon_id() -> None:
    """Verify salon_service FK constraint to salons table."""
    generator = get_db()
    session = next(generator)

    try:
        # Attempt to create service without valid salon FK
        service = SalonService(
            id=uuid.uuid4(),
            salon_id=uuid.uuid4(),  # Non-existent salon
            name="Haircut",
            duration_minutes=30,
            price_amount=150000,
        )
        session.add(service)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.close()


def test_salon_service_unique_name_per_salon() -> None:
    """Verify UNIQUE(salon_id, name) prevents duplicate service names within one salon."""
    generator = get_db()
    session = next(generator)
    unique_suffix = uuid.uuid4().hex[:8]

    try:
        owner = User(
            id=uuid.uuid4(),
            email=f"owner_{unique_suffix}@example.com",
            password_hash="hash",
        )
        session.add(owner)
        session.commit()

        salon = Salon(
            id=uuid.uuid4(),
            name="Test Salon",
            slug=f"test-salon-{unique_suffix}",
            created_by_user_id=owner.id,
        )
        session.add(salon)
        session.commit()

        service1 = SalonService(
            id=uuid.uuid4(),
            salon_id=salon.id,
            name="Haircut",
            duration_minutes=30,
            price_amount=100000,
        )
        session.add(service1)
        session.commit()

        # Attempt duplicate name in same salon
        service2 = SalonService(
            id=uuid.uuid4(),
            salon_id=salon.id,
            name="Haircut",
            duration_minutes=45,
            price_amount=150000,
        )
        session.add(service2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.query(SalonService).filter(SalonService.salon_id == salon.id).delete()
        session.query(Salon).filter(Salon.id == salon.id).delete()
        session.query(User).filter(User.id == owner.id).delete()
        session.commit()
        session.close()


def test_staff_profile_one_to_one_with_membership() -> None:
    """Verify staff_profile has one-to-one relationship with salon_membership."""
    generator = get_db()
    session = next(generator)
    unique_suffix = uuid.uuid4().hex[:8]

    try:
        from app.models import SalonMembership

        owner = User(
            id=uuid.uuid4(),
            email=f"owner_{unique_suffix}@example.com",
            password_hash="hash",
        )
        staff_user = User(
            id=uuid.uuid4(),
            email=f"staff_{unique_suffix}@example.com",
            password_hash="hash",
        )
        session.add_all([owner, staff_user])
        session.commit()

        salon = Salon(
            id=uuid.uuid4(),
            name="Test Salon",
            slug=f"test-salon-{unique_suffix}",
            created_by_user_id=owner.id,
        )
        session.add(salon)
        session.commit()

        membership = SalonMembership(
            id=uuid.uuid4(),
            salon_id=salon.id,
            user_id=staff_user.id,
            role="staff",
        )
        session.add(membership)
        session.commit()

        # Create first profile
        profile1 = StaffProfile(
            id=uuid.uuid4(),
            membership_id=membership.id,
            display_name="John Stylist",
        )
        session.add(profile1)
        session.commit()

        # Attempt duplicate profile for same membership
        profile2 = StaffProfile(
            id=uuid.uuid4(),
            membership_id=membership.id,
            display_name="John Duplicate",
        )
        session.add(profile2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.query(StaffProfile).filter(StaffProfile.membership_id == membership.id).delete()
        session.query(SalonMembership).filter(SalonMembership.id == membership.id).delete()
        session.query(Salon).filter(Salon.id == salon.id).delete()
        session.query(User).filter(User.id.in_([owner.id, staff_user.id])).delete()
        session.commit()
        session.close()


def test_staff_weekly_availability_check_constraint() -> None:
    """Verify day_of_week CHECK constraint (1-7)."""
    generator = get_db()
    session = next(generator)
    unique_suffix = uuid.uuid4().hex[:8]

    try:
        from app.models import SalonMembership, StaffWeeklyAvailability

        owner = User(
            id=uuid.uuid4(),
            email=f"owner_{unique_suffix}@example.com",
            password_hash="hash",
        )
        staff_user = User(
            id=uuid.uuid4(),
            email=f"staff_{unique_suffix}@example.com",
            password_hash="hash",
        )
        session.add_all([owner, staff_user])
        session.commit()

        salon = Salon(
            id=uuid.uuid4(),
            name="Test Salon",
            slug=f"test-salon-{unique_suffix}",
            created_by_user_id=owner.id,
        )
        session.add(salon)
        session.commit()

        membership = SalonMembership(
            id=uuid.uuid4(),
            salon_id=salon.id,
            user_id=staff_user.id,
            role="staff",
        )
        session.add(membership)
        session.commit()

        profile = StaffProfile(
            id=uuid.uuid4(),
            membership_id=membership.id,
            display_name="Staff Member",
        )
        session.add(profile)
        session.commit()

        # Invalid day_of_week = 8
        availability = StaffWeeklyAvailability(
            id=uuid.uuid4(),
            staff_profile_id=profile.id,
            day_of_week=8,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        session.add(availability)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.query(StaffProfile).filter(StaffProfile.id == profile.id).delete()
        session.query(SalonMembership).filter(SalonMembership.id == membership.id).delete()
        session.query(Salon).filter(Salon.id == salon.id).delete()
        session.query(User).filter(User.id.in_([owner.id, staff_user.id])).delete()
        session.commit()
        session.close()


def test_salon_customer_unique_email_per_salon() -> None:
    """Verify UNIQUE(salon_id, email) for salon customers."""
    generator = get_db()
    session = next(generator)
    unique_suffix = uuid.uuid4().hex[:8]

    try:
        owner = User(
            id=uuid.uuid4(),
            email=f"owner_{unique_suffix}@example.com",
            password_hash="hash",
        )
        session.add(owner)
        session.commit()

        salon = Salon(
            id=uuid.uuid4(),
            name="Test Salon",
            slug=f"test-salon-{unique_suffix}",
            created_by_user_id=owner.id,
        )
        session.add(salon)
        session.commit()

        customer1 = SalonCustomer(
            id=uuid.uuid4(),
            salon_id=salon.id,
            full_name="Jane Doe",
            email="jane@example.com",
            phone="+6281234567890",
        )
        session.add(customer1)
        session.commit()

        # Attempt duplicate email in same salon
        customer2 = SalonCustomer(
            id=uuid.uuid4(),
            salon_id=salon.id,
            full_name="Jane Smith",
            email="jane@example.com",
            phone="+6289876543210",
        )
        session.add(customer2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.query(SalonCustomer).filter(SalonCustomer.salon_id == salon.id).delete()
        session.query(Salon).filter(Salon.id == salon.id).delete()
        session.query(User).filter(User.id == owner.id).delete()
        session.commit()
        session.close()
