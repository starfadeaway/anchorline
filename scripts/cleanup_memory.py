# -*- coding: utf-8 -*-
"""记忆数据治理：清理错误/重复记录 + 属性命名归一（可重复执行，幂等）。

清理项：
- 实体 user.乒乓球经历（属性误当实体）
- 实体 大肥鱼（已被 大模型.大肥鱼 取代）
- user 乒乓球经历 里重复的“6 场”失效行（同值保留一条）
归一：
- 大模型.大肥鱼 的属性：分组/身份/饮食偏好 → 模型分组/模型身份/模型伙食
- user:demo: 饮食 偏好/饮食 禁忌 → 饮食偏好/饮食禁忌
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from sqlalchemy import delete, select, update  # noqa: E402

from anchorline.db import session_factory  # noqa: E402
from anchorline.models import Fact  # noqa: E402


def main() -> int:
    db = session_factory()()
    try:
        def remove(rows):
            ids = [f.id for f in rows]
            if not ids:
                return 0
            db.execute(update(Fact).where(Fact.supersedes_id.in_(ids)).values(supersedes_id=None))
            db.execute(delete(Fact).where(Fact.id.in_(ids)))
            return len(ids)

        # 1) 错误实体
        removed = remove(list(db.scalars(select(Fact).where(Fact.entity_id == "user.乒乓球经历")).all()))
        removed += remove(list(db.scalars(select(Fact).where(Fact.entity_id == "大肥鱼")).all()))

        # 2) user 乒乓球经历：重复的 6 场失效行，保留一条
        six = sorted(
            [f for f in db.scalars(select(Fact).where(Fact.entity_id == "user", Fact.attribute == "乒乓球经历")).all()
             if "6个对手" in f.value and f.valid_to is not None],
            key=lambda f: f.created_at,
        )
        removed += remove(six[1:])

        # 3) 属性归一
        db.execute(update(Fact).where(Fact.entity_id == "大模型.大肥鱼", Fact.attribute == "分组").values(attribute="模型分组"))
        db.execute(update(Fact).where(Fact.entity_id == "大模型.大肥鱼", Fact.attribute == "身份").values(attribute="模型身份"))
        db.execute(update(Fact).where(Fact.entity_id == "大模型.大肥鱼", Fact.attribute == "饮食偏好").values(attribute="模型伙食"))
        db.execute(update(Fact).where(Fact.attribute == "饮食 偏好").values(attribute="饮食偏好"))
        db.execute(update(Fact).where(Fact.attribute == "饮食 禁忌").values(attribute="饮食禁忌"))
        # 跑步类属性归一（处理 (entity, attribute, valid_from) 唯一约束冲突：重复则删一条）
        def normalize_attr(old: str, new: str) -> None:
            rows = list(db.scalars(select(Fact).where(Fact.attribute == old)).all())
            for f in rows:
                dup = db.scalar(
                    select(Fact).where(
                        Fact.entity_id == f.entity_id,
                        Fact.attribute == new,
                        Fact.valid_from == f.valid_from,
                        Fact.id != f.id,
                    )
                )
                if dup is not None:
                    db.execute(update(Fact).where(Fact.supersedes_id == f.id).values(supersedes_id=None))
                    db.delete(f)
                else:
                    f.attribute = new
            db.flush()

        for old_attr in ("5k_pb", "5K_personal_best", "5K 最好成绩（PB）", "5K best time"):
            normalize_attr(old_attr, "5K 最好成绩")
        normalize_attr("跑步 配速", "跑步配速")
        normalize_attr("工作 目标", "工作目标")
        normalize_attr("工作 项目", "工作项目")
        normalize_attr("跑步 目标配速", "目标配速")
        db.commit()
        print(f"removed {removed} rows; attributes normalized")

        rows = list(db.scalars(select(Fact).order_by(Fact.valid_from.desc())))
        print("remaining:", len(rows))
        for f in rows[:12]:
            print(f"  {f.entity_id} | {f.attribute} | {f.value[:28]} | {'当前' if not f.valid_to else '已失效'}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
