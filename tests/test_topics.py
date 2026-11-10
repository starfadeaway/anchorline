# -*- coding: utf-8 -*-
"""分组词表测试：后端 _canonical_topic / _topic_of_text 与前端 topics.ts 对齐。"""
from anchorline.api.main import _canonical_topic, _topic_of_text


def test_canonical_topic_mapping():
    cases = {
        "跑步": "跑步记录",
        "跑步成绩": "跑步记录",
        "游泳": "游泳记录",
        "乒乓球": "球类运动",
        "太空封印站两件套效果是什么？": "游戏",
        "遗器效果": "游戏",
        "大肥鱼喜欢吃米饭和token": "模型与配置",
        "饮食": "饮食偏好",
        "宠物": "宠物",
        "旅行": "旅行",
        "出差": "出差",
        "工作": "工作",
        "你好": "闲聊",
    }
    for inp, expected in cases.items():
        assert _canonical_topic(inp) == expected, (inp, _canonical_topic(inp))


def test_topic_of_text_fallback():
    assert _topic_of_text("记住我的 5K 最好成绩") == "跑步记录"
    assert _topic_of_text("大肥鱼喜欢吃米饭和token") == "模型与配置"
    assert _topic_of_text("莫名其妙的内容 xyz") == "其他"
