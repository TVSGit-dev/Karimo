"""Fixtures partagees : une base SQLite jetable par test."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from karimo.db import session as module_session
from karimo.db.models import Base


@pytest.fixture
def moteur_test(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def fabrique(moteur_test):
    return sessionmaker(bind=moteur_test, expire_on_commit=False, future=True)


@pytest.fixture
def session(fabrique):
    s = fabrique()
    try:
        yield s
        s.commit()
    finally:
        s.close()


@pytest.fixture
def client(fabrique, monkeypatch):
    """Client HTTP branche sur la base jetable, sans toucher a karimo.db."""
    monkeypatch.setattr(module_session, "fabrique_session", lambda: fabrique)

    from karimo.web.app import app

    with TestClient(app) as c:
        yield c
