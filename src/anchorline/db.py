# -*- coding: utf-8 -*-
"""数据库会话工厂。单 API 副本；MySQL 8 + InnoDB。"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from anchorline.config import Settings

_settings: Settings | None = None
_engine = None
_factory: sessionmaker[Session] | None = None


def settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings().mysql_dsn, pool_pre_ping=True, pool_recycle=1800)
    return _engine


def session_factory() -> sessionmaker[Session]:
    global _factory
    if _factory is None:
        _factory = sessionmaker(bind=engine(), expire_on_commit=False)
    return _factory


def get_db() -> Iterator[Session]:
    db = session_factory()()
    try:
        yield db
    finally:
        db.close()
