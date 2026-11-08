# -*- coding: utf-8 -*-
"""确定性摄入 workflow 单测。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from anchorline.graph.workflows import ingest_trajectory
from anchorline.models import Base, Trace


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _traj():
    return {
        "id": "abc12345",
        "states": [
            {"url": "/a", "action": "", "thought": "open", "accessibility_tree": "nav\nitem A\n[1] link 'Home'"},
            {"url": "/b", "action": "click('1')", "thought": "go", "accessibility_tree": "nav\nitem B\n[1] link 'Home'"},
            {"url": "/b", "action": "", "thought": "", "accessibility_tree": "nav"},
        ],
    }


def test_ingest_dedupes_across_states_and_writes_trace(db):
    out = ingest_trajectory(_traj(), db)
    db.commit()
    # "nav" 只在第一个 state 保留；"[1] link 'Home'" 同理
    assert out["l0_text"].count("nav") == 1
    assert out["l0_text"].count("[1] link 'Home'") == 1
    assert out["l0_lines"] == 4  # nav, item A, [1] link 'Home', item B
    assert out["l0_ratio"] > 1.0
    rows = db.query(Trace).all()
    assert len(rows) == 1
    assert rows[0].layers == "L0>L1"
    assert rows[0].session_id == "abc12345"


def test_ingest_empty_trajectory_is_safe(db):
    out = ingest_trajectory({"id": "empty", "states": []}, db)
    db.commit()
    assert out["l0_text"] == ""
    assert db.query(Trace).count() == 1
