"""Password hashing, JWT issuance/verification, and Fernet encryption for Meta tokens."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet

from app.core.config import get_settings

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except VerifyMismatchError:
        return False


def create_access_token(user_id: UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expiration_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def create_meta_oauth_state(account_id: UUID) -> str:
    """Signed, short-lived `state` param binding a Meta OAuth round-trip to an account_id."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {"account_id": str(account_id), "typ": "meta_oauth_state", "iat": now, "exp": now + timedelta(minutes=10)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_meta_oauth_state(state: str) -> UUID:
    settings = get_settings()
    payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("typ") != "meta_oauth_state":
        raise jwt.InvalidTokenError("Unexpected state token type")
    return UUID(payload["account_id"])


def _fernet() -> Fernet:
    return Fernet(get_settings().fernet_key.encode())


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
