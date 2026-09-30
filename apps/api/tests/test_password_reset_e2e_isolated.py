"""Full E2E password reset test with isolated DB session (no fixture rollback).

This test uses real database sessions and commits outside the fixture transaction
to verify all 6 steps of the password reset flow:
1. Old password works (login 200)
2. Refresh token works
3. Reset password succeeds
4. Old refresh token → 401
5. Old password → 401
6. New password → 200
"""

import uuid
from datetime import UTC, datetime, timedelta

from app.core.security import hash_password
from app.core.tokens import generate_opaque_token, hash_token
from app.db import engine
from app.models import AuthSession, PasswordResetToken, User
from sqlalchemy.orm import Session


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_password_reset_e2e_isolated():
    """Full E2E password reset: old password works, reset, old fails, new works.

    Uses isolated DB session with real commits to verify the complete lifecycle
    without fixture transaction rollback interference.
    """
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Setup: create user with committed password
    db = Session(engine)
    user_email = _unique("e2e-reset") + "@example.com"
    user_id = None  # Initialize for cleanup scope

    try:
        user = User(
            email=user_email,
            password_hash=hash_password("OldPass123"),
            is_active=True,
        )
        db.add(user)
        db.commit()
        user_id = user.id

        # Step 1: Old password works (login 200)
        login_resp = client.post(
            "/auth/login",
            json={"email": user_email, "password": "OldPass123"},
        )
        assert login_resp.status_code == 200, f"Step 1 failed: {login_resp.text}"
        old_refresh = login_resp.json()["refresh_token"]

        # Step 2: Refresh token works
        refresh_resp = client.post("/auth/refresh", json={"refresh_token": old_refresh})
        assert refresh_resp.status_code == 200, f"Step 2 failed: {refresh_resp.text}"
        rotated_refresh = refresh_resp.json()["refresh_token"]

        # Step 3: Issue reset token and perform reset
        raw_token = generate_opaque_token()
        reset_token = PasswordResetToken(
            user_id=user_id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        db.add(reset_token)
        db.commit()

        confirm_resp = client.post(
            "/auth/password-reset/confirm",
            json={"token": raw_token, "new_password": "BrandNewPass123"},
        )
        assert confirm_resp.status_code == 200, f"Step 3 failed: {confirm_resp.text}"

        # Step 4: Old and rotated refresh tokens are dead (401)
        for dead_token in (old_refresh, rotated_refresh):
            dead_resp = client.post("/auth/refresh", json={"refresh_token": dead_token})
            assert (
                dead_resp.status_code == 401
            ), f"Step 4 failed: token {dead_token[:20]}... gave {dead_resp.status_code}"

        # Step 5: Old password fails (401)
        old_login = client.post(
            "/auth/login",
            json={"email": user_email, "password": "OldPass123"},
        )
        assert old_login.status_code == 401, "Step 5 failed: old password still works"

        # Step 6: New password works (login 200)
        new_login = client.post(
            "/auth/login",
            json={"email": user_email, "password": "BrandNewPass123"},
        )
        assert (
            new_login.status_code == 200
        ), f"Step 6 failed: new password login gave {new_login.status_code}"

    finally:
        # Cleanup: delete user and related data (skip if setup failed early)
        if user_id is not None:
            db_cleanup = Session(engine)
            try:
                db_cleanup.query(AuthSession).filter(AuthSession.user_id == user_id).delete(
                    synchronize_session=False
                )
                db_cleanup.query(PasswordResetToken).filter(
                    PasswordResetToken.user_id == user_id
                ).delete(synchronize_session=False)
                db_cleanup.query(User).filter(User.id == user_id).delete(synchronize_session=False)
                db_cleanup.commit()
            finally:
                db_cleanup.close()
        db.close()
