"""Agent API 测试：全部使用注入的假客户端，不产生真实 LLM 调用与费用。"""

from __future__ import annotations

import math
from array import array

import pytest

from app.main import app
from app.models import (
    BehaviorEvent,
    Belief,
    Elicitation,
    ElicitationKind,
    Profile,
    User,
)

CONFIRM_TEXT = "是，点赞对我来说就是背书"
DISCONFIRM_TEXT = "不是，我只是懒得点"
UNCERTAIN_TEXT = "一半吧，看情况"


# --------------------------------------------------------------------------- #
# 假客户端（对应 app.state.agent_*_client 注入点）
# --------------------------------------------------------------------------- #
class FakeProfileClient:
    chat_model = "fake-chat"

    def summarize_hidden_traits(self, *, text: str) -> tuple[str, dict]:
        return ("测试画像：偏向先广泛浏览再择优投入，互动克制。", {"total_tokens": 11})

    def embed(self, *, text: str) -> tuple[list[float], dict]:
        return ([0.1, 0.2, 0.3, 0.4], {"total_tokens": 5})


class FakeRerankClient:
    def rerank(self, *, user_summary: str, candidates: list[tuple[int, float, str]]):
        best = candidates[0][0]
        ranked = [
            {"user_id": best, "score": 0.9, "reasons": ["共同点：都喜欢在晚上自习"]},
            *[
                {"user_id": cid, "score": 0.1, "reasons": ["差异：作息不同"]}
                for cid, _, _ in candidates[1:]
            ],
        ]
        for item in ranked:
            if int(item.get("user_id")) == int(best):
                item.update(
                    {
                        "shared": ["共同点：都喜欢「晚上自习」"],
                        "differences": ["差异：节奏与作息仍可能不同"],
                        "rare_common": ["罕见共同点：都能在高压下保持自律"],
                        "worldviews": ["世界观差异：对“努力”的理解角度不同但可互补"],
                        "why_this_person": "因为你们在「晚上自习」这件小事上呈现出一致的长期自律方式。",
                    }
                )
            else:
                item.update(
                    {
                        "shared": ["共同点：都愿意投入时间在自我提升上"],
                        "differences": ["差异：作息不同"],
                        "rare_common": ["罕见共同点：能把兴趣转为持续行动"],
                        "worldviews": ["世界观差异：对“效率”的权衡方式不同"],
                        "why_this_person": "你们有些共鸣，但整体契合度较低。",
                    }
                )
        return ranked, {"total_tokens": 7}


class FakeElicitClient:
    def generate_cards(self, *, user_profile: str, belief_p: float):
        cards = []
        for i in range(3):
            cards.append(
                {
                    "question": f"测试猜测卡 {i + 1}：你是不是把点赞当作一种承诺？",
                    "options": [
                        {"text": CONFIRM_TEXT, "polarity": "confirm"},
                        {"text": DISCONFIRM_TEXT, "polarity": "disconfirm"},
                        {"text": UNCERTAIN_TEXT, "polarity": "uncertain"},
                    ],
                    "evidence_weight": 1,
                }
            )
        return cards, {"total_tokens": 13}


@pytest.fixture()
def agent_client(client):
    """在 TestClient 上注入假客户端，避免真实 LLM 调用。"""
    app.state.agent_profile_client = FakeProfileClient()
    app.state.agent_match_client = FakeRerankClient()
    app.state.agent_elicit_client = FakeElicitClient()
    yield client
    app.state.agent_profile_client = None
    app.state.agent_match_client = None
    app.state.agent_elicit_client = None


# --------------------------------------------------------------------------- #
# 数据准备
# --------------------------------------------------------------------------- #
def seed_user(session, *, consent: bool = True) -> User:
    user = User(consent=consent)
    session.add(user)
    session.commit()
    return user


def seed_profile(session, user_id: int, *, dims: int = 4, summary: str = "测试画像") -> Profile:
    profile = Profile(
        user_id=user_id,
        summary=summary,
        embedding=array("f", [0.1] * dims).tobytes(),
        source_hash="hash-" + str(user_id),
    )
    session.add(profile)
    session.commit()
    return profile


def seed_events(session, user_id: int, count: int = 3) -> None:
    from app.models import BehaviorEventType

    session.add_all(
        [
            BehaviorEvent(
                user_id=user_id,
                event_type=BehaviorEventType.BROWSE,
                target_id=f"t{i}",
                duration_ms=1200,
            )
            for i in range(count)
        ]
    )
    session.commit()


def seed_elicitation(session) -> Elicitation:
    elicitation = Elicitation(
        question="你是不是把点赞当作一种承诺？",
        options=[
            {"text": CONFIRM_TEXT, "polarity": "confirm"},
            {"text": DISCONFIRM_TEXT, "polarity": "disconfirm"},
            {"text": UNCERTAIN_TEXT, "polarity": "uncertain"},
        ],
        kind=ElicitationKind.SINGLE_CHOICE,
    )
    session.add(elicitation)
    session.commit()
    return elicitation


# --------------------------------------------------------------------------- #
# profile
# --------------------------------------------------------------------------- #
def test_get_profile_ok(agent_client, api_session) -> None:
    user = seed_user(api_session)
    seed_profile(api_session, user.id, dims=4, summary="他很克制")

    resp = agent_client.get(f"/users/{user.id}/profile")
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"] == "他很克制"
    assert body["embedding_dims"] == 4
    assert body["source_hash"] == f"hash-{user.id}"


def test_get_profile_unknown_user_404(agent_client) -> None:
    assert agent_client.get("/users/999/profile").status_code == 404


def test_get_profile_without_consent_403(agent_client, api_session) -> None:
    user = seed_user(api_session, consent=False)
    assert agent_client.get(f"/users/{user.id}/profile").status_code == 403


def test_refresh_profile_uses_injected_client(agent_client, api_session) -> None:
    user = seed_user(api_session)
    seed_events(api_session, user.id, count=4)

    resp = agent_client.post(f"/users/{user.id}/profile/refresh")
    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"] is True
    assert body["summary_chars"] > 0
    assert body["embedding_dims"] == 4
    assert "测试画像" in body["summary"]

    # 二次调用：事件未变 → 命中缓存，updated=False（默认不重复扣费）
    again = agent_client.post(f"/users/{user.id}/profile/refresh")
    assert again.status_code == 200
    assert again.json()["updated"] is False

    # force=true 时忽略缓存强制重算
    forced = agent_client.post(f"/users/{user.id}/profile/refresh?force=true")
    assert forced.status_code == 200
    assert forced.json()["updated"] is True


# --------------------------------------------------------------------------- #
# match
# --------------------------------------------------------------------------- #
def test_match_ok_and_entropy_fields_separated(agent_client, api_session) -> None:
    me = seed_user(api_session)
    other = seed_user(api_session)
    seed_profile(api_session, me.id, summary="我：晚上自习")
    seed_profile(api_session, other.id, summary="TA：也晚上自习")

    resp = agent_client.post(f"/users/{me.id}/match")
    assert resp.status_code == 200
    body = resp.json()
    assert body["matched_user_id"] in (me.id, other.id)
    assert "score" not in body
    assert body["reasons"], "理由不能为空"
    # 无作答历史 → 信念熵应为先验的 ln2
    assert body["belief_entropy"] == pytest.approx(math.log(2), abs=1e-9)

    narrative = body["narrative"]
    assert narrative["shared"]
    assert narrative["differences"]
    assert narrative["rare_common"]
    assert narrative["worldviews"]
    assert narrative["why_this_person"]
    assert "match_uncertainty" not in body
    assert "匹配不确定性" in body["explanation"]


def test_match_without_profile_409(agent_client, api_session) -> None:
    user = seed_user(api_session)
    assert agent_client.post(f"/users/{user.id}/match").status_code == 409


def test_match_without_consent_403(agent_client, api_session) -> None:
    user = seed_user(api_session, consent=False)
    assert agent_client.post(f"/users/{user.id}/match").status_code == 403


# --------------------------------------------------------------------------- #
# elicit
# --------------------------------------------------------------------------- #
def test_elicit_returns_cards_with_polarity(agent_client, api_session) -> None:
    user = seed_user(api_session)
    seed_profile(api_session, user.id)

    resp = agent_client.post(f"/users/{user.id}/elicit")
    assert resp.status_code == 200
    body = resp.json()
    assert body["belief_entropy_before"] == pytest.approx(math.log(2), abs=1e-9)
    assert len(body["cards"]) == 3
    first = body["cards"][0]
    polarities = {opt["text"]: opt["polarity"] for opt in first["options"]}
    assert polarities[CONFIRM_TEXT] == "confirm"
    assert polarities[DISCONFIRM_TEXT] == "disconfirm"
    assert polarities[UNCERTAIN_TEXT] == "uncertain"
    assert first["expected_information_gain"] > 0


def test_elicit_without_profile_409(agent_client, api_session) -> None:
    user = seed_user(api_session)
    resp = agent_client.post(f"/users/{user.id}/elicit")
    assert resp.status_code == 409


# --------------------------------------------------------------------------- #
# respond / belief
# --------------------------------------------------------------------------- #
def test_respond_confirm_lowers_entropy_and_syncs_belief(agent_client, api_session) -> None:
    user = seed_user(api_session)
    seed_profile(api_session, user.id)
    elicitation = seed_elicitation(api_session)

    resp = agent_client.post(
        f"/users/{user.id}/respond",
        json={"elicitation_id": elicitation.id, "choice": CONFIRM_TEXT, "reaction_time_ms": 1500},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["entropy_after"] < body["entropy_before"]
    assert body["entropy_delta"] < 0
    assert body["alpha"] == pytest.approx(2.0)
    assert body["beta"] == pytest.approx(1.0)
    assert body["belief_mean"] == pytest.approx(2 / 3, abs=1e-9)

    # beliefs 缓存行已同步
    belief = (
        api_session.query(Belief).filter(Belief.user_id == user.id, Belief.hypothesis == "match").one()
    )
    assert belief.confidence == pytest.approx(2 / 3, abs=1e-9)

    state = agent_client.get(f"/users/{user.id}/belief").json()
    assert state["strength"] == pytest.approx(3.0)
    assert state["responses_counted"] == 1
    assert state["entropy"] == pytest.approx(body["entropy_after"], abs=1e-9)


def test_respond_disconfirm_lowers_entropy_symmetrically(agent_client, api_session) -> None:
    user = seed_user(api_session)
    seed_profile(api_session, user.id)
    elicitation = seed_elicitation(api_session)

    body = agent_client.post(
        f"/users/{user.id}/respond",
        json={"elicitation_id": elicitation.id, "choice": DISCONFIRM_TEXT, "reaction_time_ms": 800},
    ).json()
    assert body["alpha"] == pytest.approx(1.0)
    assert body["beta"] == pytest.approx(2.0)
    assert body["entropy_delta"] < 0


def test_respond_uncertain_keeps_entropy(agent_client, api_session) -> None:
    user = seed_user(api_session)
    seed_profile(api_session, user.id)
    elicitation = seed_elicitation(api_session)

    body = agent_client.post(
        f"/users/{user.id}/respond",
        json={"elicitation_id": elicitation.id, "choice": UNCERTAIN_TEXT, "reaction_time_ms": 300},
    ).json()
    assert body["entropy_delta"] == pytest.approx(0.0)
    assert body["alpha"] == pytest.approx(1.0)
    assert body["beta"] == pytest.approx(1.0)


def test_belief_replay_accumulates_across_requests(agent_client, api_session) -> None:
    """两次作答后 α 应累计为 3.0：证明后验可从历史无状态恢复。"""
    user = seed_user(api_session)
    seed_profile(api_session, user.id)
    first = seed_elicitation(api_session)
    second = seed_elicitation(api_session)

    for elicitation in (first, second):
        resp = agent_client.post(
            f"/users/{user.id}/respond",
            json={"elicitation_id": elicitation.id, "choice": CONFIRM_TEXT, "reaction_time_ms": 900},
        )
        assert resp.status_code == 200

    state = agent_client.get(f"/users/{user.id}/belief").json()
    assert state["alpha"] == pytest.approx(3.0)
    assert state["beta"] == pytest.approx(1.0)
    assert state["responses_counted"] == 2
    assert state["ci_low"] < state["mean"] < state["ci_high"]


def test_respond_unknown_elicitation_404(agent_client, api_session) -> None:
    user = seed_user(api_session)
    seed_profile(api_session, user.id)
    resp = agent_client.post(
        f"/users/{user.id}/respond",
        json={"elicitation_id": 999999, "choice": CONFIRM_TEXT, "reaction_time_ms": 100},
    )
    assert resp.status_code == 404


def test_respond_without_profile_409(agent_client, api_session) -> None:
    """没有画像时不应答卡：返回 409 而不是让上游抛错变成 400/500。"""
    user = seed_user(api_session)
    elicitation = seed_elicitation(api_session)
    resp = agent_client.post(
        f"/users/{user.id}/respond",
        json={"elicitation_id": elicitation.id, "choice": CONFIRM_TEXT, "reaction_time_ms": 100},
    )
    assert resp.status_code == 409


def test_respond_rejects_invalid_payload(agent_client, api_session) -> None:
    user = seed_user(api_session)
    elicitation = seed_elicitation(api_session)
    resp = agent_client.post(
        f"/users/{user.id}/respond",
        json={"elicitation_id": elicitation.id, "choice": "", "reaction_time_ms": -1},
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# 成本保护
# --------------------------------------------------------------------------- #
def test_llm_endpoint_is_rate_limited(agent_client, api_session) -> None:
    """会调 LLM 的接口额度为 6 次/分钟，第 7 次应被 429 拦下。"""
    user = seed_user(api_session)
    seed_profile(api_session, user.id)

    codes = [agent_client.post(f"/users/{user.id}/elicit").status_code for _ in range(7)]
    assert codes[:6] == [200] * 6
    assert codes[6] == 429
