from __future__ import annotations

from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from .models import Base

class Database:
    def __init__(self, url: str, *, echo: bool = False):
        self.url = url
        if url.startswith("sqlite:///"):
            from pathlib import Path
            Path(url.removeprefix("sqlite:///" )).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url, pool_pre_ping=True, echo=echo)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def transaction(self):
        session: Session = self.sessions()
        try:
            with session.begin():
                yield session
        finally:
            session.close()

    def health(self) -> dict:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return {"status": "ready", "backend": self.engine.url.get_backend_name()}
        except Exception as exc:
            return {"status": "not_ready", "error_code": "database_unavailable", "detail": type(exc).__name__}
