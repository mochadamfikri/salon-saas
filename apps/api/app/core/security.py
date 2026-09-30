"""Password hashing and verification using Argon2id."""

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

# Single global instance for process-wide password operations
_pwd_context = PasswordHash((Argon2Hasher(),))


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using Argon2id.

    Args:
        plain_password: The plaintext password to hash.

    Returns:
        The hashed password string suitable for storage.
    """
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored hash.

    Args:
        plain_password: The plaintext password to verify.
        password_hash: The stored hash to verify against.

    Returns:
        True if the password matches, False otherwise.
    """
    return _pwd_context.verify(plain_password, password_hash)
