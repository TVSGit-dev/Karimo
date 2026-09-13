"""Connexion a la base."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from karimo.config import database_url


@lru_cache(maxsize=1)
def moteur() -> Engine:
    url = database_url()
    engine = create_engine(url, future=True)

    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _active_les_cles_etrangeres(connexion, _record):
            # SQLite ignore les cles etrangeres tant qu'on ne les active pas
            # explicitement, connexion par connexion.
            curseur = connexion.cursor()
            curseur.execute("PRAGMA foreign_keys=ON")
            curseur.close()

    return engine


@lru_cache(maxsize=1)
def fabrique_session() -> sessionmaker[Session]:
    return sessionmaker(bind=moteur(), expire_on_commit=False, future=True)


@contextmanager
def session_portee() -> Iterator[Session]:
    """Session transactionnelle : commit si tout va bien, rollback sinon."""
    session = fabrique_session()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def obtenir_session() -> Iterator[Session]:
    """Dependance FastAPI."""
    with session_portee() as session:
        yield session
