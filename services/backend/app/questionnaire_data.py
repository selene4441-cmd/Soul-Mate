from datetime import datetime, timezone

QUESTIONNAIRE_VERSION = "relationship-signals-v0.1"

DIMENSION_LABELS = {
    "relationship_goal": "关系目标",
    "region_preference": "地域条件",
    "age_preference": "年龄条件",
    "marital_status": "婚恋状态",
    "value_family": "家庭位置",
    "value_career": "事业与生活",
    "value_integrity": "诚实与承诺",
    "value_freedom": "自主空间",
    "nonneg_long_distance": "异地取舍",
    "nonneg_children": "生育计划",
    "nonneg_social_intensity": "社交强度",
    "nonneg_spending": "消费底线",
    "growth_direction": "成长方向",
    "growth_pace": "变化节奏",
    "growth_autonomy": "支持自主成长",
    "growth_repair": "共同修正关系",
    "life_weekend": "周末节奏",
    "life_work_intensity": "工作强度",
    "comm_directness": "表达直接度",
    "comm_reply_frequency": "联系频率",
    "comm_depth": "交流深度",
    "repair_style": "冲突后的行动",
    "emotional_support": "被支持的方式",
    "time_reply_expectation": "回复预期",
    "time_change_notice": "安排变化说明",
    "space_solitude": "独处需求",
    "space_privacy": "隐私边界",
    "safety_boundary_response": "越界时的处理",
}


def _option(value: str, label: str) -> dict[str, str]:
    return {"value": value, "label": label}


def _question(
    *,
    qid: str,
    section: str,
    dimension: str,
    prompt: str,
    help_text: str,
    kind: str,
    sensitivity: str,
    claim_type: str,
    stability: str,
    options: list[tuple[str, str]],
    required: bool = True,
    min_selections: int | None = None,
    max_selections: int | None = None,
) -> dict:
    return {
        "id": qid,
        "section": section,
        "dimension": dimension,
        "prompt": prompt,
        "help_text": help_text,
        "kind": kind,
        "sensitivity": sensitivity,
        "claim_type": claim_type,
        "stability": stability,
        "required": required,
        "options": [_option(value, label) for value, label in options],
        "min_selections": min_selections,
        "max_selections": max_selections,
    }


QUESTIONS = [
    _question(
        qid="relationship_goal",
        section="关系目标",
        dimension="relationship_goal",
        prompt="你目前更希望建立哪种关系？",
        help_text="关系目标会随时间变化，可稍后修正。",
        kind="single",
        sensitivity="L1",
        claim_type="fact",
        stability="medium",
        options=[
            ("long_term", "长期稳定关系"),
            ("marriage", "以婚姻为方向"),
            ("dating", "先约会认识"),
        ],
    ),
    _question(
        qid="region_preference",
        section="基础条件",
        dimension="region_preference",
        prompt="关于见面与地域，目前更接近哪种安排？",
        help_text="用于过滤现实不可行的组合，不代表城市优劣。",
        kind="single",
        sensitivity="L1",
        claim_type="preference",
        stability="medium",
        options=[
            ("same_city", "希望在同一城市"),
            ("same_region", "同区域或临近城市"),
            ("remote_ok", "可以接受异地并愿意规划"),
        ],
    ),
    _question(
        qid="age_preference",
        section="基础条件",
        dimension="age_preference",
        prompt="你目前愿意了解哪类年龄范围？",
        help_text="双方范围需要互相满足。",
        kind="single",
        sensitivity="L1",
        claim_type="preference",
        stability="medium",
        options=[
            ("25_32", "25–32 岁"),
            ("30_38", "30–38 岁"),
            ("35_45", "35–45 岁"),
            ("open", "更看重相处感受"),
        ],
    ),
    _question(
        qid="marital_status",
        section="基础条件",
        dimension="marital_status",
        prompt="你目前的状态是？",
        help_text="仅用于匹配可用性与双方条件，不用于评价。",
        kind="single",
        sensitivity="L1",
        claim_type="fact",
        stability="high",
        options=[
            ("never_married", "未婚"),
            ("divorced", "离异"),
            ("prefer_not_to_say", "暂不说明"),
        ],
    ),
    _question(
        qid="value_family",
        section="关键取舍",
        dimension="value_family",
        prompt="在一个重要假期里，你更愿意怎样安排？",
        help_text="没有标准答案，选择更接近你当下的取舍。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="medium",
        options=[
            ("family_first", "优先陪伴家人"),
            ("balanced", "兼顾家人与自己的安排"),
            ("personal_plan", "优先保留自己的计划"),
        ],
    ),
    _question(
        qid="value_career",
        section="关键取舍",
        dimension="value_career",
        prompt="当工作机会与共同计划冲突时，你更接近哪种做法？",
        help_text="这用于理解长期生活取舍。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="medium",
        options=[
            ("career_priority", "先认真评估工作机会"),
            ("discuss_balance", "一起讨论并寻找平衡"),
            ("relationship_priority", "优先保护共同计划"),
        ],
    ),
    _question(
        qid="value_integrity",
        section="关键取舍",
        dimension="value_integrity",
        prompt="答应过但后来发现做不到时，你更可能怎么做？",
        help_text="这反映承诺与说明方式。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="high",
        options=[
            ("explain_early", "尽早说明并重新商量"),
            ("solve_first", "先尝试解决，有结果再说明"),
            ("adjust_quietly", "自行调整安排，之后再看"),
        ],
    ),
    _question(
        qid="value_freedom",
        section="关键取舍",
        dimension="value_freedom",
        prompt="在一段关系里，你希望彼此怎样保留个人安排？",
        help_text="自主与亲密可以同时存在。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="medium",
        options=[
            ("high_autonomy", "保留较多独处和个人安排"),
            ("shared_rhythm", "保持共同节奏，也各有空间"),
            ("close_rhythm", "更多共同安排会让我安心"),
        ],
    ),
    _question(
        qid="nonneg_long_distance",
        section="不可协商项",
        dimension="nonneg_long_distance",
        prompt="关于长期异地，你的当前底线是？",
        help_text="这是硬约束。双方底线冲突时不会进入推荐。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="medium",
        options=[
            ("must_resolve", "必须在可预期时间内解决"),
            ("can_plan", "愿意先异地并共同规划"),
            ("not_acceptable", "无法接受长期异地"),
        ],
    ),
    _question(
        qid="nonneg_children",
        section="不可协商项",
        dimension="nonneg_children",
        prompt="关于是否生育，你目前更接近哪种情况？",
        help_text="这是重要的未来规划，不判断任何选择。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="medium",
        options=[
            ("want", "希望未来有孩子"),
            ("open", "目前开放，需要和伴侣确认"),
            ("do_not_want", "不打算要孩子"),
            ("undecided", "暂时没有确定"),
        ],
    ),
    _question(
        qid="nonneg_social_intensity",
        section="不可协商项",
        dimension="nonneg_social_intensity",
        prompt="频繁的多人社交对你意味着什么？",
        help_text="用于避免明显的生活方式冲突。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="medium",
        options=[
            ("enjoy_frequent", "很享受，也愿意一起参加"),
            ("sometimes", "偶尔参加就好"),
            ("prefer_quiet", "更偏好安静和小范围相处"),
        ],
    ),
    _question(
        qid="nonneg_spending",
        section="不可协商项",
        dimension="nonneg_spending",
        prompt="面对一笔较大的共同支出，你更接近哪种方式？",
        help_text="这不是评价消费观，只用于确认底线。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="medium",
        options=[
            ("save_first", "先充分储蓄再决定"),
            ("plan_ratio", "按共同计划与比例安排"),
            ("enjoy_now", "愿意为当下体验投入"),
        ],
    ),
    _question(
        qid="growth_direction",
        section="成长同向",
        dimension="growth_direction",
        prompt="未来三年，你更希望把精力放在哪里？",
        help_text="成长方向不同并不必然不兼容，重要的是能否协商。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="medium",
        options=[
            ("career_learning", "职业与持续学习"),
            ("life_balance", "生活平衡与兴趣"),
            ("family_building", "家庭建设与稳定"),
            ("exploration", "探索新城市或新方向"),
        ],
    ),
    _question(
        qid="growth_pace",
        section="成长同向",
        dimension="growth_pace",
        prompt="你更喜欢怎样的变化节奏？",
        help_text="关注节奏差异，而不是催促彼此改变。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="medium",
        options=[
            ("fast_change", "较快尝试新变化"),
            ("steady_change", "稳步推进，定期复盘"),
            ("slow_change", "节奏较慢，先保持稳定"),
        ],
    ),
    _question(
        qid="growth_autonomy",
        section="成长同向",
        dimension="growth_autonomy",
        prompt="对方想尝试一个你不熟悉的新方向时，你更可能怎么回应？",
        help_text="支持自主成长不等于必须投入相同方向。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="high",
        options=[
            ("support_autonomy", "了解需要后支持其自主选择"),
            ("discuss_cost", "先讨论时间与投入，再一起决定"),
            ("keep_stable", "希望优先保持现有安排"),
        ],
    ),
    _question(
        qid="growth_repair",
        section="成长同向",
        dimension="growth_repair",
        prompt="如果双方长期卡在同一种分歧里，你更愿意怎么做？",
        help_text="关系中的变化需要共同修正，而不是要求一方改造另一方。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="high",
        options=[
            ("seek_method", "寻找新方法并调整相处规则"),
            ("take_break", "先各自冷静，再约定时间复盘"),
            ("avoid_topic", "尽量绕开，维持当下状态"),
        ],
    ),
    _question(
        qid="life_weekend",
        section="生活节奏",
        dimension="life_weekend",
        prompt="理想周末更接近哪一种？",
        help_text="用于判断现实生活节奏是否容易重合。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="low",
        options=[
            ("outdoor", "外出探索和运动"),
            ("social", "见朋友或参加活动"),
            ("home", "在家休息和做自己的事"),
        ],
    ),
    _question(
        qid="life_work_intensity",
        section="生活节奏",
        dimension="life_work_intensity",
        prompt="你目前的工作强度更接近哪种？",
        help_text="这是当前状态，可能随时间变化。",
        kind="single",
        sensitivity="L1",
        claim_type="state",
        stability="low",
        options=[
            ("intense", "经常加班或出差"),
            ("variable", "忙闲波动明显"),
            ("regular", "时间相对规律"),
        ],
    ),
    _question(
        qid="comm_directness",
        section="沟通方式",
        dimension="comm_directness",
        prompt="有需求但担心对方不高兴时，你更可能？",
        help_text="不同表达方式都可能有效，关键是能否相互理解。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="high",
        options=[
            ("direct", "直接说明需求和原因"),
            ("soften", "先照顾气氛，再逐步表达"),
            ("wait", "先观察，等合适时机再说"),
        ],
    ),
    _question(
        qid="comm_reply_frequency",
        section="沟通方式",
        dimension="comm_reply_frequency",
        prompt="工作日联系频率怎样更舒服？",
        help_text="用于减少“时间压迫”，不是硬性考核。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="medium",
        options=[
            ("frequent", "希望当天多次自然交流"),
            ("daily", "每天有一段完整对话"),
            ("needs_space", "各自忙完后集中交流"),
        ],
    ),
    _question(
        qid="comm_depth",
        section="沟通方式",
        dimension="comm_depth",
        prompt="你更喜欢怎样的日常交流？",
        help_text="用于了解交流偏好的差异。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="medium",
        options=[
            ("deep_topics", "深入讨论观点与感受"),
            ("daily_share", "分享日常和具体经历"),
            ("action_oriented", "更常通过一起做事建立理解"),
        ],
    ),
    _question(
        qid="repair_style",
        section="冲突修复",
        dimension="repair_style",
        prompt="争执后，你更希望先发生什么？",
        help_text="这里描述当下更有效的修复方式，不是固定人格。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="medium",
        options=[
            ("talk_now", "尽快把问题说清楚"),
            ("pause_then_talk", "短暂冷静后约定继续谈"),
            ("show_care", "先恢复安全感，再讨论问题"),
        ],
    ),
    _question(
        qid="emotional_support",
        section="情感需求",
        dimension="emotional_support",
        prompt="你低落时，更希望对方怎样支持？",
        help_text="需求可能相互不同，可通过沟通确认供给。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="medium",
        options=[
            ("listen", "先听我说，不急着给方案"),
            ("practical", "一起拆解并解决具体问题"),
            ("presence", "安静陪伴或给一些空间"),
        ],
    ),
    _question(
        qid="time_reply_expectation",
        section="时间边界",
        dimension="time_reply_expectation",
        prompt="忙起来无法及时回复时，你更希望怎样？",
        help_text="明确预期可以减少时间压力。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="high",
        options=[
            ("advance_note", "提前说明大致何时忙完"),
            ("reply_when_free", "忙完自然回复即可"),
            ("real_time", "尽量抽空回应，不让对方等待"),
        ],
    ),
    _question(
        qid="time_change_notice",
        section="时间边界",
        dimension="time_change_notice",
        prompt="约定需要改变时，你更看重什么？",
        help_text="守时也包括及时说明变化。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="high",
        options=[
            ("early_notice", "尽快说明并提供新方案"),
            ("reason_first", "先解释原因，再一起调整"),
            ("flexible", "只要能灵活重新安排就可以"),
        ],
    ),
    _question(
        qid="space_solitude",
        section="空间与自主",
        dimension="space_solitude",
        prompt="在亲密关系里，你需要多少独处时间？",
        help_text="独处需求不是拒绝亲密，而是边界信息。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="medium",
        options=[
            ("daily", "几乎每天都需要一点独处"),
            ("weekly", "每周需要一段完整独处"),
            ("rarely", "有共同活动时通常很少需要独处"),
        ],
    ),
    _question(
        qid="space_privacy",
        section="空间与自主",
        dimension="space_privacy",
        prompt="关于手机、社交关系和个人物品，你更接近哪种边界？",
        help_text="未经同意查看、控制或持续侵入不属于关心。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="high",
        options=[
            ("private_by_default", "默认保持隐私，主动分享即可"),
            ("open_shared", "伴侣可以自然知道大部分内容"),
            ("case_by_case", "根据不同情况提前确认"),
        ],
    ),
    _question(
        qid="safety_boundary_response",
        section="安全与信任",
        dimension="safety_boundary_response",
        prompt="如果对方反复越过你已说明的边界，你会怎样？",
        help_text="这不是测试，而是一条不可协商的安全边界。",
        kind="single",
        sensitivity="L2",
        claim_type="preference",
        stability="high",
        options=[
            ("stop_and_report", "停止交往并向平台反馈"),
            ("set_final_limit", "明确最后边界并观察是否改变"),
            ("seek_help", "先寻求可信的人或专业帮助"),
        ],
    ),
]


def get_questionnaire() -> dict:
    return {
        "version": QUESTIONNAIRE_VERSION,
        "estimated_minutes": 12,
        "questions": QUESTIONS,
    }


def option_map(question: dict) -> dict[str, str]:
    return {item["value"]: item["label"] for item in question["options"]}


def validate_answers(answers: dict[str, str | list[str]]) -> None:
    known = {question["id"]: question for question in QUESTIONS}
    unknown = set(answers) - set(known)
    if unknown:
        raise ValueError(f"存在未知问题: {', '.join(sorted(unknown))}")
    missing = [
        qid for qid, question in known.items() if question["required"] and qid not in answers
    ]
    if missing:
        raise ValueError(f"还有必答问题未完成: {', '.join(missing)}")
    for qid, value in answers.items():
        question = known[qid]
        allowed = set(option_map(question))
        values = value if isinstance(value, list) else [value]
        if not values or any(item not in allowed for item in values):
            raise ValueError(f"问题 {qid} 的答案不在允许范围内")
        if question["kind"] == "single" and not isinstance(value, str):
            raise ValueError(f"问题 {qid} 只能选择一个答案")
        if question["kind"] == "multi":
            minimum = question.get("min_selections") or 1
            maximum = question.get("max_selections") or len(allowed)
            if not minimum <= len(values) <= maximum:
                raise ValueError(f"问题 {qid} 的选择数量不符合要求")


def claim_expiry(stability: str) -> datetime:
    days = {"high": 365, "medium": 180, "low": 45}[stability]
    return datetime.now(timezone.utc).replace(microsecond=0) + __import__("datetime").timedelta(
        days=days
    )
