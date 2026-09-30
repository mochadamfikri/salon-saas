"""Tests for Phase 2 Salon Operations Core schema, constraints, and relationships.

Audit remediation: tests verify contract compliance, not invented business rules.
"""

import uuid
from datetime import time
from decimal import Decimal

import pytest
from app.core.dependencies import get_db
from app.db import engine
from app.models import (
    Salon,
    SalonCustomer,
    SalonMembership,
    SalonService,
    StaffProfile,
    StaffWeeklyAvailability,
    User,
)
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
            price_amount=Decimal("150000"),
        )
        session.add(service)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.close()


def test_salon_service_duration_must_be_positive() -> None:
    """Verify CHECK(duration_minutes > 0) constraint."""
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

        # duration_minutes = 0 should be rejected
        service = SalonService(
            id=uuid.uuid4(),
            salon_id=salon.id,
            name="Invalid Service",
            duration_minutes=0,
            price_amount=Decimal("100000"),
        )
        session.add(service)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        # duration_minutes < 0 should be rejected
        service2 = SalonService(
            id=uuid.uuid4(),
            salon_id=salon.id,
            name="Invalid Service 2",
            duration_minutes=-10,
            price_amount=Decimal("100000"),
        )
        session.add(service2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.query(Salon).filter(Salon.id == salon.id).delete()
        session.query(User).filter(User.id == owner.id).delete()
        session.commit()
        session.close()


def test_salon_service_price_non_negative() -> None:
    """Verify CHECK(price_amount >= 0) constraint."""
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

        # Negative price should be rejected
        service = SalonService(
            id=uuid.uuid4(),
            salon_id=salon.id,
            name="Invalid Service",
            duration_minutes=30,
            price_amount=Decimal("-100"),
        )
        session.add(service)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        # Zero price should be accepted (free service)
        service_free = SalonService(
            id=uuid.uuid4(),
            salon_id=salon.id,
            name="Free Consultation",
            duration_minutes=15,
            price_amount=Decimal("0"),
        )
        session.add(service_free)
        session.commit()
        assert service_free.price_amount == Decimal("0")
    finally:
        session.query(SalonService).filter(SalonService.salon_id == salon.id).delete()
        session.query(Salon).filter(Salon.id == salon.id).delete()
        session.query(User).filter(User.id == owner.id).delete()
        session.commit()
        session.close()


def test_salon_service_currency_defaults_to_idr() -> None:
    """Verify currency column defaults to 'IDR'."""
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

        service = SalonService(
            id=uuid.uuid4(),
            salon_id=salon.id,
            name="Haircut",
            duration_minutes=30,
            price_amount=Decimal("150000"),
        )
        session.add(service)
        session.commit()

        session.refresh(service)
        assert service.currency == "IDR"
    finally:
        session.query(SalonService).filter(SalonService.id == service.id).delete()
        session.query(Salon).filter(Salon.id == salon.id).delete()
        session.query(User).filter(User.id == owner.id).delete()
        session.commit()
        session.close()


def test_salon_service_category_optional() -> None:
    """Verify category is optional."""
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

        service = SalonService(
            id=uuid.uuid4(),
            salon_id=salon.id,
            name="Mystery Service",
            duration_minutes=45,
            price_amount=Decimal("200000"),
            category=None,
        )
        session.add(service)
        session.commit()
        assert service.category is None
    finally:
        session.query(SalonService).filter(SalonService.id == service.id).delete()
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


def test_staff_profile_display_name_optional() -> None:
    """Verify display_name is optional."""
    generator = get_db()
    session = next(generator)
    unique_suffix = uuid.uuid4().hex[:8]

    try:
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
            display_name=None,
        )
        session.add(profile)
        session.commit()
        assert profile.display_name is None
    finally:
        session.query(StaffProfile).filter(StaffProfile.id == profile.id).delete()
        session.query(SalonMembership).filter(SalonMembership.id == membership.id).delete()
        session.query(Salon).filter(Salon.id == salon.id).delete()
        session.query(User).filter(User.id.in_([owner.id, staff_user.id])).delete()
        session.commit()
        session.close()


def test_staff_profile_phone_optional() -> None:
    """Verify phone is optional."""
    generator = get_db()
    session = next(generator)
    unique_suffix = uuid.uuid4().hex[:8]

    try:
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
            phone=None,
        )
        session.add(profile)
        session.commit()
        assert profile.phone is None
    finally:
        session.query(StaffProfile).filter(StaffProfile.id == profile.id).delete()
        session.query(SalonMembership).filter(SalonMembership.id == membership.id).delete()
        session.query(Salon).filter(Salon.id == salon.id).delete()
        session.query(User).filter(User.id.in_([owner.id, staff_user.id])).delete()
        session.commit()
        session.close()


def test_staff_weekly_availability_day_0_valid() -> None:
    """Verify day_of_week = 0 (Monday per ISO 8601) is valid."""
    generator = get_db()
    session = next(generator)
    unique_suffix = uuid.uuid4().hex[:8]

    try:
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
        )
        session.add(profile)
        session.commit()

        availability = StaffWeeklyAvailability(
            id=uuid.uuid4(),
            staff_profile_id=profile.id,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        session.add(availability)
        session.commit()
        assert availability.day_of_week == 0
    finally:
        session.query(StaffWeeklyAvailability).filter(
            StaffWeeklyAvailability.staff_profile_id == profile.id
        ).delete()
        session.query(StaffProfile).filter(StaffProfile.id == profile.id).delete()
        session.query(SalonMembership).filter(SalonMembership.id == membership.id).delete()
        session.query(Salon).filter(Salon.id == salon.id).delete()
        session.query(User).filter(User.id.in_([owner.id, staff_user.id])).delete()
        session.commit()
        session.close()


def test_staff_weekly_availability_day_6_valid() -> None:
    """Verify day_of_week = 6 (Sunday per ISO 8601) is valid."""
    generator = get_db()
    session = next(generator)
    unique_suffix = uuid.uuid4().hex[:8]

    try:
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
        )
        session.add(profile)
        session.commit()

        availability = StaffWeeklyAvailability(
            id=uuid.uuid4(),
            staff_profile_id=profile.id,
            day_of_week=6,
            start_time=time(10, 0),
            end_time=time(14, 0),
        )
        session.add(availability)
        session.commit()
        assert availability.day_of_week == 6
    finally:
        session.query(StaffWeeklyAvailability).filter(
            StaffWeeklyAvailability.staff_profile_id == profile.id
        ).delete()
        session.query(StaffProfile).filter(StaffProfile.id == profile.id).delete()
        session.query(SalonMembership).filter(SalonMembership.id == membership.id).delete()
        session.query(Salon).filter(Salon.id == salon.id).delete()
        session.query(User).filter(User.id.in_([owner.id, staff_user.id])).delete()
        session.commit()
        session.close()


def test_staff_weekly_availability_day_negative_invalid() -> None:
    """Verify day_of_week < 0 is rejected."""
    generator = get_db()
    session = next(generator)
    unique_suffix = uuid.uuid4().hex[:8]

    try:
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
        )
        session.add(profile)
        session.commit()

        availability = StaffWeeklyAvailability(
            id=uuid.uuid4(),
            staff_profile_id=profile.id,
            day_of_week=-1,
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


def test_staff_weekly_availability_day_7_invalid() -> None:
    """Verify day_of_week = 7 is rejected (valid range 0-6)."""
    generator = get_db()
    session = next(generator)
    unique_suffix = uuid.uuid4().hex[:8]

    try:
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
        )
        session.add(profile)
        session.commit()

        availability = StaffWeeklyAvailability(
            id=uuid.uuid4(),
            staff_profile_id=profile.id,
            day_of_week=7,
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


def test_staff_weekly_availability_start_after_end_rejected() -> None:
    """Verify start_time >= end_time is rejected."""
    generator = get_db()
    session = next(generator)
    unique_suffix = uuid.uuid4().hex[:8]

    try:
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
        )
        session.add(profile)
        session.commit()

        # start_time > end_time
        availability = StaffWeeklyAvailability(
            id=uuid.uuid4(),
            staff_profile_id=profile.id,
            day_of_week=1,
            start_time=time(17, 0),
            end_time=time(9, 0),
        )
        session.add(availability)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        # start_time == end_time
        availability2 = StaffWeeklyAvailability(
            id=uuid.uuid4(),
            staff_profile_id=profile.id,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(9, 0),
        )
        session.add(availability2)
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


def test_staff_weekly_availability_is_available_stored() -> None:
    """Verify is_available boolean is stored."""
    generator = get_db()
    session = next(generator)
    unique_suffix = uuid.uuid4().hex[:8]

    try:
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
        )
        session.add(profile)
        session.commit()

        availability = StaffWeeklyAvailability(
            id=uuid.uuid4(),
            staff_profile_id=profile.id,
            day_of_week=2,
            start_time=time(10, 0),
            end_time=time(18, 0),
            is_available=False,
        )
        session.add(availability)
        session.commit()

        session.refresh(availability)
        assert availability.is_available is False
    finally:
        session.query(StaffWeeklyAvailability).filter(
            StaffWeeklyAvailability.id == availability.id
        ).delete()
        session.query(StaffProfile).filter(StaffProfile.id == profile.id).delete()
        session.query(SalonMembership).filter(SalonMembership.id == membership.id).delete()
        session.query(Salon).filter(Salon.id == salon.id).delete()
        session.query(User).filter(User.id.in_([owner.id, staff_user.id])).delete()
        session.commit()
        session.close()


def test_salon_customer_name_only_valid() -> None:
    """Verify customer with only full_name (no email/phone) is valid."""
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

        customer = SalonCustomer(
            id=uuid.uuid4(),
            salon_id=salon.id,
            full_name="Walk-in Customer",
            email=None,
            phone=None,
        )
        session.add(customer)
        session.commit()
        assert customer.full_name == "Walk-in Customer"
        assert customer.email is None
        assert customer.phone is None
    finally:
        session.query(SalonCustomer).filter(SalonCustomer.id == customer.id).delete()
        session.query(Salon).filter(Salon.id == salon.id).delete()
        session.query(User).filter(User.id == owner.id).delete()
        session.commit()
        session.close()


def test_salon_customer_email_only_valid() -> None:
    """Verify customer with email but no phone is valid."""
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

        customer = SalonCustomer(
            id=uuid.uuid4(),
            salon_id=salon.id,
            full_name="Email Customer",
            email="customer@example.com",
            phone=None,
        )
        session.add(customer)
        session.commit()
        assert customer.email == "customer@example.com"
        assert customer.phone is None
    finally:
        session.query(SalonCustomer).filter(SalonCustomer.id == customer.id).delete()
        session.query(Salon).filter(Salon.id == salon.id).delete()
        session.query(User).filter(User.id == owner.id).delete()
        session.commit()
        session.close()


def test_salon_customer_phone_only_valid() -> None:
    """Verify customer with phone but no email is valid."""
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

        customer = SalonCustomer(
            id=uuid.uuid4(),
            salon_id=salon.id,
            full_name="Phone Customer",
            email=None,
            phone="+6281234567890",
        )
        session.add(customer)
        session.commit()
        assert customer.phone == "+6281234567890"
        assert customer.email is None
    finally:
        session.query(SalonCustomer).filter(SalonCustomer.id == customer.id).delete()
        session.query(Salon).filter(Salon.id == salon.id).delete()
        session.query(User).filter(User.id == owner.id).delete()
        session.commit()
        session.close()


def test_salon_customer_no_email_uniqueness_constraint() -> None:
    """Verify email is NOT unique per salon (owner never mandated this)."""
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

        # Create first customer with email
        customer1 = SalonCustomer(
            id=uuid.uuid4(),
            salon_id=salon.id,
            full_name="Jane Doe",
            email="duplicate@example.com",
        )
        session.add(customer1)
        session.commit()

        # Create second customer with same email - should succeed
        customer2 = SalonCustomer(
            id=uuid.uuid4(),
            salon_id=salon.id,
            full_name="Jane Smith",
            email="duplicate@example.com",
        )
        session.add(customer2)
        session.commit()  # Should NOT raise IntegrityError

        # Verify both exist
        count = (
            session.query(SalonCustomer)
            .filter(
                SalonCustomer.salon_id == salon.id, SalonCustomer.email == "duplicate@example.com"
            )
            .count()
        )
        assert count == 2
    finally:
        session.query(SalonCustomer).filter(SalonCustomer.salon_id == salon.id).delete()
        session.query(Salon).filter(Salon.id == salon.id).delete()
        session.query(User).filter(User.id == owner.id).delete()
        session.commit()
        session.close()


def test_phase1_regression_tables_intact() -> None:
    """Verify Phase 1 tables remain intact after Phase 2 migration."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    expected_phase1_tables = {
        "users",
        "salons",
        "salon_memberships",
        "auth_sessions",
        "salon_invitations",
        "password_reset_tokens",
    }
    assert expected_phase1_tables.issubset(table_names)
