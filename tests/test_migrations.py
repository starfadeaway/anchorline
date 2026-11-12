# -*- coding: utf-8 -*-
"""迁移往返测试（需要真实 MySQL；CI 无 MySQL 时自动跳过）。

覆盖：upgrade head 建库 → 0016 三态往返（NULL → '' → NULL）→ downgrade base → 再 upgrade head。
这是项目第一条真正跑「回滚路径」的测试（此前 CI 只跑 upgrade head）。
"""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DB = "anchorline_migtest"


def _connect(database: str | None = None):
    import pymysql

    from anchorline.config import Settings

    s = Settings()
    return pymysql.connect(
        host=s.mysql_host,
        port=s.mysql_port,
        user=s.mysql_user,
        password=s.mysql_password,
        database=database,
        autocommit=True,
        connect_timeout=3,
    )


def _alembic(*args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["MYSQL_DATABASE"] = TEST_DB
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True)


@pytest.fixture(scope="module")
def mysql_available():
    try:
        conn = _connect()
    except Exception as exc:
        pytest.skip(f"MySQL 不可用：{exc}")
    conn.close()


@pytest.fixture(scope="module")
def temp_db(mysql_available):
    server = _connect()
    cur = server.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
    cur.execute(f"CREATE DATABASE {TEST_DB} CHARACTER SET utf8mb4")
    yield
    cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
    server.close()


def _tables(cur) -> set[str]:
    cur.execute("SHOW TABLES")
    return {r[0] for r in cur.fetchall()}


def _version(cur) -> str:
    cur.execute("SELECT version_num FROM alembic_version")
    return cur.fetchone()[0]


def _neg_keywords(cur, row_id: str):
    cur.execute("SELECT negative_keywords FROM custom_skills WHERE id=%s", (row_id,))
    return cur.fetchone()[0]


def test_upgrade_head_creates_schema(temp_db):
    r = _alembic("upgrade", "head")
    assert r.returncode == 0, r.stderr
    conn = _connect(TEST_DB)
    cur = conn.cursor()
    tables = _tables(cur)
    assert _version(cur) == "0016"
    assert {"facts", "sessions", "skill_toggles", "custom_skills", "traces"} <= tables
    conn.close()


def test_0016_three_state_roundtrip(temp_db):
    """NULL=用默认、''=显式清空：升级后回填 NULL，回滚后变回 ''，再升级又是 NULL。"""
    conn = _connect(TEST_DB)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO custom_skills (id, name, title, description, instructions, enabled, negative_keywords) "
        "VALUES ('t1','t1','t','','i',0,NULL)"
    )
    assert _neg_keywords(cur, "t1") is None

    r = _alembic("downgrade", "0015")
    assert r.returncode == 0, r.stderr
    assert _neg_keywords(cur, "t1") == ""
    cur.execute("SHOW COLUMNS FROM custom_skills")
    col = {row[0]: (row[1], row[2]) for row in cur.fetchall()}["negative_keywords"]
    assert col[1] == "NO"  # 回滚后 NOT NULL

    r = _alembic("upgrade", "head")
    assert r.returncode == 0, r.stderr
    cur.execute("SHOW COLUMNS FROM custom_skills")
    col = {row[0]: (row[1], row[2]) for row in cur.fetchall()}["negative_keywords"]
    assert col[1] == "YES"  # 再升级后可空
    assert _neg_keywords(cur, "t1") is None  # 空串被回填为 NULL
    conn.close()


def test_full_downgrade_to_base_then_upgrade(temp_db):
    """整链回滚到空库再重建：证明 0001→0016 的 downgrade 路径可用。"""
    r = _alembic("downgrade", "base")
    assert r.returncode == 0, r.stderr
    conn = _connect(TEST_DB)
    cur = conn.cursor()
    cur.execute("SHOW TABLES")
    left = {row[0] for row in cur.fetchall()}
    assert left <= {"alembic_version"}, f"downgrade base 后仍残留表：{left}"

    r = _alembic("upgrade", "head")
    assert r.returncode == 0, r.stderr
    assert _version(cur) == "0016"
    assert len(_tables(cur)) >= 8
    conn.close()
