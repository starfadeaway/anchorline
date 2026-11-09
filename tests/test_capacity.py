# -*- coding: utf-8 -*-
"""记忆容量保护：每实体当前值上限 + 自动归档（标记失效）。"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from anchorline.memory.store import FactStore
from anchorline.models import Base, Fact


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _current(db) -> list[Fact]:
    return [f for f in db.query(Fact).all() if f.valid_to is None]


def test_capacity_archives_oldest(db):
    store = FactStore(db, max_current_per_entity=2)
    t0 = datetime(2026, 1, 1)
    store.write(entity_id="user", attribute="a", value="v1", valid_from=t0)
    store.write(entity_id="user", attribute="b", value="v2", valid_from=t0 + timedelta(days=1))
    store.write(entity_id="user", attribute="c", value="v3", valid_from=t0 + timedelta(days=2))
    assert store.last_archived == 1
    assert {f.attribute for f in _current(db)} == {"b", "c"}


def test_capacity_archives_low_confidence_first(db):
    store = FactStore(db, max_current_per_entity=2)
    t0 = datetime(2026, 1, 1)
    store.write(entity_id="user", attribute="a", value="v1", valid_from=t0, confidence=0.3)
    store.write(entity_id="user", attribute="b", value="v2", valid_from=t0 + timedelta(days=1), confidence=1.0)
    store.write(entity_id="user", attribute="c", value="v3", valid_from=t0 + timedelta(days=2), confidence=1.0)
    assert "a" not in {f.attribute for f in _current(db)}
