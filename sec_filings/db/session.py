from __future__ import annotations

from sqlalchemy.orm import sessionmaker

_session_factory = None


def configure_engine(engine) -> None:
    global _session_factory
    _session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_session():
    if _session_factory is None:
        raise RuntimeError("Database has not been bootstrapped. Call bootstrap_database().")
    return _session_factory()


class _SessionProxy:
    """Optional hook if a framework wants to reset a thread-local session."""

    def remove(self) -> None:
        return None


SessionLocal = _SessionProxy()
