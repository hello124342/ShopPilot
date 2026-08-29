from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from .infra.database import Database
from .infra.models import Session as UserSession, User

def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"

def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, digest = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        actual = _hash_password(password, bytes.fromhex(salt)).split("$", 2)[2]
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False

def _token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

class AuthService:
    COOKIE = "shopilot_session"
    CSRF_COOKIE = "shopilot_csrf"

    def __init__(self, database: Database, *, ttl_hours: int = 24):
        self.database = database
        self.ttl = timedelta(hours=ttl_hours)

    def ensure_admin(self, username: str, password: str, tenant_id: str = "default") -> User:
        with self.database.transaction() as session:
            user = session.scalar(select(User).where(User.username == username))
            if user is None:
                user = User(username=username, password_hash=_hash_password(password), tenant_id=tenant_id, must_change_password=True)
                session.add(user)
                session.flush()
            return user

    def login(self, username: str, password: str) -> tuple[User, str, str]:
        now = datetime.now(timezone.utc)
        session_id = secrets.token_urlsafe(48)
        csrf_token = secrets.token_urlsafe(32)
        with self.database.transaction() as db:
            user = db.scalar(select(User).where(User.username == username, User.active.is_(True)))
            if user is None or not _verify_password(password, user.password_hash):
                raise ValueError("invalid_credentials")
            db.add(UserSession(id=_token_hash(session_id), user_id=user.id, tenant_id=user.tenant_id, csrf_token_hash=_token_hash(csrf_token), expires_at=now + self.ttl))
        return user, session_id, csrf_token

    def authenticate(self, session_id: str | None) -> User | None:
        if not session_id:
            return None
        now = datetime.now(timezone.utc)
        with self.database.transaction() as db:
            row = db.get(UserSession, _token_hash(session_id))
            if row is None or row.expires_at < now:
                if row is not None:
                    db.delete(row)
                return None
            return db.get(User, row.user_id)

    def validate_csrf(self, session_id: str | None, csrf_token: str | None) -> bool:
        if not session_id or not csrf_token:
            return False
        with self.database.transaction() as db:
            row = db.get(UserSession, _token_hash(session_id))
            return bool(row and hmac.compare_digest(row.csrf_token_hash, _token_hash(csrf_token)))

    def logout(self, session_id: str | None) -> None:
        if not session_id:
            return
        with self.database.transaction() as db:
            db.execute(delete(UserSession).where(UserSession.id == _token_hash(session_id)))
