from __future__ import annotations

QUESTIONNAIRE_VERSION = "relationship-signals-v0.1"

QUESTIONNAIRE = {
    "version": QUESTIONNAIRE_VERSION,
    "estimated_minutes": 12,
    "questions": [
        {
            "id": "life_weekend",
            "section": "生活节奏",
            "dimension": "life_weekend",
            "prompt": "一个理想的周末，你更想怎么度过？",
            "help_text": "请选择当前更接近你的情况",
            "kind": "single",
            "required": True,
            "options": [
                {"value": "stay_home", "label": "留在家里慢慢恢复", "polarity": "confirm"},
                {"value": "go_out", "label": "出去走走见朋友", "polarity": "disconfirm"},
                {"value": "mixed", "label": "半天在家半天出去", "polarity": "uncertain"},
            ],
        },
        {
            "id": "comm_reply_frequency",
            "section": "沟通频率",
            "dimension": "comm_reply_frequency",
            "prompt": "你期待对方在日常的回复频率更接近哪种？",
            "help_text": "请选择当前更接近你的情况",
            "kind": "single",
            "required": True,
            "options": [
                {"value": "daily", "label": "每天都有回应即可", "polarity": "confirm"},
                {"value": "few_times_week", "label": "一周几次也可以", "polarity": "disconfirm"},
                {"value": "asynchronous", "label": "更在意能讲清楚", "polarity": "uncertain"},
            ],
        },
    ],
}

