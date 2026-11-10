# -*- coding: utf-8 -*-
"""分组词表一致性核验：前端 topics.ts 规则（Python 复刻）vs 后端 _canonical_topic。

前端规则改动词表时，同步更新这里（或反过来）；两边输出必须一致。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

# ---- 前端 topics.ts 规则的 Python 复刻 ----
TOPIC = {
    "swim": "游泳记录",
    "ball": "球类运动",
    "run": "跑步记录",
    "fitness": "健身记录",
    "health": "身体数据",
    "model": "模型与配置",
    "game": "游戏",
    "memory": "记忆写入",
    "chat": "闲聊",
    "diet": "饮食偏好",
    "pet": "宠物",
    "travel": "旅行",
    "trip": "出差",
    "work": "工作",
    "testData": "测试数据",
    "other": "其他",
}

RULES = [
    (r"mcp|test|check", "testData"),
    (r"游泳|泳池|自由泳|蛙泳|蝶泳|仰泳|swim", "swim"),
    (r"乒乓球|羽毛球|网球|篮球|足球|排球|台球|球类", "ball"),
    (r"5k|跑步|配速|半马|全马|\bpb\b|跑", "run"),
    (r"健身|骑行|瑜伽|增肌|力量训练", "fitness"),
    (r"体重|身高|体脂|睡眠|心率|health", "health"),
    (r"模型|model|大模型|大肥鱼|deepseek|minimax", "model"),
    (r"游戏|遗器|太空封印|崩铁|星穹|原神|绝区零|抽卡|角色|技能|副本|深渊|配队", "game"),
    (r"饮食|米饭|咖啡|早餐|午餐|晚餐|口味|吃|食物", "diet"),
    (r"宠物|猫|狗|鱼|豆豆|大肥鱼", "pet"),
    (r"旅行|旅游|云南|大理|丽江|景点", "travel"),
    (r"出差|成都|会议", "trip"),
    (r"工作|项目|开发|实现|anchorline|lorekeeper", "work"),
    (r"记住|记忆|存下|保存|归档", "memory"),
    (r"你好|hi|hello|在吗|闲聊", "chat"),
]

CANON = [
    (r"^饮食", "diet"),
    (r"^跑步|^5k", "run"),
    (r"^游泳", "swim"),
    (r"^乒乓|^球类", "ball"),
    (r"^健身", "fitness"),
    (r"^身体", "health"),
    (r"^模型|^配置", "model"),
    (r"^游戏|^遗器|^太空|^崩铁|^原神|^绝区零", "game"),
    (r"^宠物|^猫|^狗", "pet"),
    (r"^旅行", "travel"),
    (r"^出差", "trip"),
    (r"^工作|^项目", "work"),
    (r"^记忆", "memory"),
    (r"^闲聊", "chat"),
    (r"^其他|^其它", "other"),
]


def front_topic_of_text(text: str) -> str:
    s = text.lower()
    for pat, key in RULES:
        if pat == "mcp|test|check":
            if "mcp" in s or "test" in s or "check" in s:
                return TOPIC[key]
            continue
        if __import__("re").search(pat, s):
            return TOPIC[key]
    return TOPIC["other"]


def front_canonical(topic: str) -> str:
    t = (topic or "").strip()
    if not t:
        return TOPIC["other"]
    if __import__("re").search(r"大肥鱼|大模型|deepseek|minimax", t, __import__("re").I):
        return TOPIC["model"]
    for pat, key in CANON:
        if __import__("re").search(pat, t):
            return TOPIC[key]
    return front_topic_of_text(t)


def main() -> int:
    from anchorline.api.main import _canonical_topic

    samples = [
        "跑步",
        "跑步成绩",
        "跑步记录",
        "游泳",
        "乒乓球",
        "太空封印站两件套效果是什么？",
        "遗器效果",
        "大肥鱼喜欢吃米饭和token",
        "模型与配置",
        "宠物",
        "出差",
        "旅行",
        "工作",
        "饮食",
        "饮食偏好",
        "记住我的 5K 最好成绩",
        "你好",
    ]
    ok = True
    print(f"{'input':32s} {'front_canonical':12s} {'back_canonical':12s} match")
    for s in samples:
        f = front_canonical(s)
        b = _canonical_topic(s)
        match = f == b
        ok = ok and match
        print(f"{s:32s} {f:12s} {b:12s} {match}")
    print("consistent:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
