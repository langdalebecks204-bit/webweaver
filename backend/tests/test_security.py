import datetime

import jwt

from app.config import settings
from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify():
    h = hash_password("secret123")
    assert h != "secret123"
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)


def test_token_roundtrip():
    token = create_access_token(1, "admin", "admin")
    payload = decode_access_token(token)
    assert payload["sub"] == "1"
    assert payload["username"] == "admin"
    assert payload["role"] == "admin"


def test_token_expiry():
    expired = jwt.encode(
        {
            "sub": "1",
            "username": "u",
            "role": "viewer",
            "exp": datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=1),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    try:
        decode_access_token(expired)
        raise AssertionError("expected expired token error")
    except jwt.ExpiredSignatureError:
        pass
