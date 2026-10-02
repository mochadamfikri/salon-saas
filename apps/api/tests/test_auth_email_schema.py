import pytest
from app.schemas.auth import LoginRequest, RegisterRequest, normalize_auth_email


def test_login_accepts_preview_local_addresses_in_development() -> None:
    payload = LoginRequest(
        email=" OWNER@Preview.Salon.Local ",
        password="SalonPreview#2026",
    )

    assert payload.email == "OWNER@preview.salon.local"


def test_register_accepts_preview_local_addresses_in_development() -> None:
    payload = RegisterRequest(
        email="owner@preview.salon.local",
        password="SalonPreview#2026",
    )

    assert payload.email == "owner@preview.salon.local"


def test_reserved_local_domain_is_rejected_outside_development() -> None:
    with pytest.raises(ValueError, match="special-use|valid email"):
        normalize_auth_email("owner@preview.salon.local", app_env="production")


def test_regular_email_is_normalized_in_production() -> None:
    assert normalize_auth_email(" OWNER@Example.COM ", app_env="production") == "OWNER@example.com"
