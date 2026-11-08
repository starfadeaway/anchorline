# -*- coding: utf-8 -*-
"""L2 事实存储单测（SQLite 替身，不依赖 MySQL）。"""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from anchorline.memory.store import FactStore
from anchorline.models import Base, Fact


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_write_supersedes_old_without_deleting(db):
    store = FactStore(db)
    t1 = datetime(2023, 1, 1, 10, 0)
    t2 = datetime(2023, 2, 1, 10, 0)
    f1 = store.write(entity_id="user:liu", attribute="5K best time", value="24:00", valid_from=t1)
    f2 = store.write(entity_id="user:liu", attribute="5K best time", value="25:50", valid_from=t2)
    db.commit()

    assert f1.valid_to == t2
    assert f2.supersedes_id == f1.id
    cur = store.current("user:liu", "5K best time")
    assert cur is not None and cur.value == "25:50"
    hist = store.history("user:liu", "5K best time")
    assert [h.value for h in hist] == ["24:00", "25:50"]
    assert db.query(Fact).count() == 2


def test_write_same_valid_from_is_idempotent(db):
    store = FactStore(db)
    t = datetime(2023, 1, 1, 10, 0)
    a = store.write(entity_id="e", attribute="a", value="v1", valid_from=t)
    b = store.write(entity_id="e", attribute="a", value="v2", valid_from=t)
    db.commit()
    assert a.id == b.id
    assert b.value == "v2"
    assert db.query(Fact).count() == 1


def test_out_of_order_earlier_write_does_not_clobber_current(db):
    store = FactStore(db)
    t_new = datetime(2023, 5, 30, 10, 0)
    t_old = datetime(2023, 1, 1, 10, 0)
    store.write(entity_id="user:liu", attribute="5K best time", value="25:50", valid_from=t_new)
    f_old = store.write(entity_id="user:liu", attribute="5K best time", value="24:00", valid_from=t_old)
    db.commit()

    cur = store.current("user:liu", "5K best time")
    assert cur is not None and cur.value == "25:50"
    assert f_old.valid_to == t_new
    assert f_old.supersedes_id is None
    hist = store.history("user:liu", "5K best time")
    assert [(h.value, h.valid_from) for h in hist] == [("24:00", t_old), ("25:50", t_new)]


def test_search_text_hits_attribute_and_value(db):
    store = FactStore(db)
    store.write(entity_id="user:liu", attribute="frequent flyer status", value="Gold", valid_from=datetime(2023, 1, 1))
    store.write(entity_id="user:liu", attribute="kitchen gadget", value="Air Fryer", valid_from=datetime(2023, 2, 1))
    db.commit()
    assert [f.attribute for f in store.search_text("flyer")] == ["frequent flyer status"]
    assert [f.value for f in store.search_text("Air Fryer")] == ["Air Fryer"]
