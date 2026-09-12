from __future__ import annotations

import json
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.agents.orchestrator import FeedbackProvider, Orchestrator
from app.core.belief import BetaPosterior
from app.models import Profile, User


def _emb(values: list[float]) -> bytes:
    return array("f", values).tobytes()


@dataclass
class FixedFeedback(FeedbackProvider):
    idx: int = 0
    choice: str = "同意"
    rt: int = 321

    def choose(self, *, cards):
        return (self.idx, self.choice, self.rt)


@dataclass
class FakeElicitClient:
    chat_model: str = "gpt-5.2"
    last_usage: dict[str, Any] | None = None

    def generate_cards(self, *, user_profile: str, belief_p: float):
        self.last_usage = {"total_tokens": 11}
        cards = [
            {"question": "我猜：你更在意被认真对待。", "options": ["同意", "不同意"], "evidence_weight": 2},
            {"question": "我猜：你讨厌被催促。", "options": ["同意", "不同意", "不确定"], "evidence_weight": 1},
            {"question": "我猜：你更看重稳定。", "options": ["同意", "不同意"], "evidence_weight": 3},
        ]
        return cards, self.last_usage


@dataclass
class FakeMatchClient:
    chat_model: str = "gpt-5.2"
    last_usage: dict[str, Any] | None = None
    calls: int = 0

    def rerank(self, *, user_summary: str, candidates: list[tuple[int, float, str]]):
        self.calls += 1
        self.last_usage = {"total_tokens": 17}
        ranked: list[dict[str, Any]] = []
        for uid, sim, summary in sorted(candidates, key=lambda x: (-x[1], x[0])):
            ranked.append(
                {
                    "user_id": uid,
                    "score": max(0.0, min(1.0, (float(sim) + 1.0) / 2.0)),
                    "reasons": [f"你「{user_summary[:6]}」与TA「{summary[:6]}」一致。"],
                }
            )
        for item in ranked:
            item.update(
                {
                    "shared": ["共同点：都更偏向稳定与长期投入"],
                    "differences": ["差异：沟通方式与节奏不同"],
                    "rare_common": ["罕见共同点：在压力下也能保持自洽"],
                    "worldviews": ["世界观差异：对“关系”的期待层次不同"],
                    "why_this_person": "因为你们追求稳定的底层需求一致，且差异不会互相消耗。",
                }
            )
        return ranked, self.last_usage


def test_orchestrator_round_logs_entropy_and_tokens(
    session: Session, scratch_dir: Path
) -> None:
    u1 = User(consent=True)
    u2 = User(consent=True)
    session.add_all([u1, u2])
    session.flush()
    session.add_all(
        [
            Profile(
                user_id=u1.id,
                summary="A画像：偏稳定，慢热。",
                embedding=_emb([1.0, 0.0]),
                source_hash="ha",
            ),
            Profile(
                user_id=u2.id,
                summary="B画像：也偏稳定，愿意沟通。",
                embedding=_emb([0.9, 0.1]),
                source_hash="hb",
            ),
        ]
    )
    session.commit()

    logs_dir = scratch_dir / "logs"
    orch = Orchestrator(
        logs_dir=str(logs_dir),
        belief_hypothesis="match:test",
        elicit_client=FakeElicitClient(),
        match_client=FakeMatchClient(),
    )
    posterior = BetaPosterior(alpha=1.0, beta=1.0)
    result, posterior2 = orch.run_round(
        round_index=1,
        session=session,
        user_id=u1.id,
        posterior=posterior,
        feedback=FixedFeedback(),
    )

    assert posterior2.mean > posterior.mean
    assert result.entropy_after < result.entropy_before
    assert result.token_cost == 11 + 17
    assert "匹配对象" in result.explanation

    log_path = logs_dir / "orchestrator.jsonl"
    assert log_path.exists()
    line = log_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["round_index"] == 1
    assert payload["user_id"] == u1.id
    assert payload["delta_entropy"] < 0
    assert payload["token_cost"] == 28

