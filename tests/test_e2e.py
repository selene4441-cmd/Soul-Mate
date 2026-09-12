from __future__ import annotations

import hashlib
import os
import struct
import zlib
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agents.orchestrator import FeedbackProvider, Orchestrator
from app.agents.profile_agent import update_user_profile_from_events
from app.core.belief import BetaPosterior, entropy as bernoulli_entropy
from app.models import Profile, User


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type)
    crc = zlib.crc32(data, crc)
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc & 0xFFFFFFFF)


def _write_entropy_png(path: Path, entropies: list[float]) -> None:
    width, height = 640, 360
    margin = 40
    bg = (255, 255, 255)
    axis = (0, 0, 0)
    line = (30, 90, 200)

    pixels = bytearray([bg[0], bg[1], bg[2]] * width * height)

    def set_px(x: int, y: int, color: tuple[int, int, int]) -> None:
        if x < 0 or x >= width or y < 0 or y >= height:
            return
        idx = (y * width + x) * 3
        pixels[idx : idx + 3] = bytes(color)

    def draw_line(x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
        dx = abs(x1 - x0)
        sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0)
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        while True:
            set_px(x, y, color)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    # Axes
    for x in range(margin, width - margin):
        set_px(x, height - margin, axis)
    for y in range(margin, height - margin):
        set_px(margin, y, axis)

    if not entropies:
        entropies = [0.0]

    xs = list(range(len(entropies)))
    y_min = min(entropies)
    y_max = max(entropies)
    if y_max - y_min < 1e-12:
        y_max = y_min + 1e-12

    def map_x(i: int) -> int:
        if len(xs) == 1:
            return margin
        return margin + int(round((width - 2 * margin) * (i / (len(xs) - 1))))

    def map_y(v: float) -> int:
        frac = (v - y_min) / (y_max - y_min)
        y = (height - margin) - int(round((height - 2 * margin) * frac))
        return y

    points = [(map_x(i), map_y(v)) for i, v in enumerate(entropies)]
    for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
        draw_line(x0, y0, x1, y1, line)

    # PNG encoding
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)  # filter type 0
        start = y * stride
        raw.extend(pixels[start : start + stride])

    compressed = zlib.compress(bytes(raw), level=6)
    png = bytearray()
    png.extend(b"\x89PNG\r\n\x1a\n")
    png.extend(
        _png_chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
        )
    )
    png.extend(_png_chunk(b"IDAT", compressed))
    png.extend(_png_chunk(b"IEND", b""))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(png))


@dataclass
class FakeProfileClient:
    chat_model: str = "gpt-5.2"
    embedding_model: str = "fake-embed"
    last_usage: dict[str, Any] | None = None

    def summarize_hidden_traits(self, *, text: str) -> tuple[str, dict]:
        self.last_usage = {"total_tokens": 23}
        # Stable, short, paragraph-like, <=200 chars.
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
        summary = f"隐性特质画像：更偏稳定与清晰边界，先观察后投入；对细节敏感，重视一致性（{digest}）。"
        return summary[:200], self.last_usage

    def embed(self, *, text: str) -> tuple[list[float], dict]:
        self.last_usage = {"total_tokens": 7}
        h = hashlib.sha256(text.encode("utf-8")).digest()
        a = int.from_bytes(h[0:4], "big") / 2**32
        b = int.from_bytes(h[4:8], "big") / 2**32
        # 2-d vector, non-zero norm
        return [float(a + 0.1), float(b + 0.2)], self.last_usage


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
                    "reasons": [f"你「{user_summary[:10]}」与TA「{summary[:10]}」有呼应。"],
                }
            )
        return ranked, self.last_usage


@dataclass
class LocalFixedFeedback(FeedbackProvider):
    idx: int = 0
    choice: str = "同意"
    rt: int = 250

    def choose(self, *, cards):
        return (self.idx, self.choice, self.rt)


def test_e2e_closed_loop(client: TestClient, api_engine, scratch_dir: Path) -> None:
    # Arrange: 3 users, where u2 is closest to u1 in embedding space after profiling.
    with Session(api_engine) as session:
        u1 = User(consent=True)
        u2 = User(consent=True)
        u3 = User(consent=True)
        session.add_all([u1, u2, u3])
        session.commit()
        user_ids = [u1.id, u2.id, u3.id]

    # 打点：写行为事件（通过 API）。
    events = []
    for uid in user_ids:
        # u1/u2 share similar targets; u3 differs.
        target = "profile:shared" if uid in (user_ids[0], user_ids[1]) else "profile:other"
        for _ in range(20):
            events.append({"user_id": uid, "event_type": "browse", "target_id": target, "duration_ms": 300})
        for _ in range(10):
            events.append({"user_id": uid, "event_type": "dwell", "target_id": target, "duration_ms": 9000})

    resp = client.post("/events", json={"events": events})
    assert resp.status_code == 200
    assert resp.json()["inserted"] == len(events)

    # 画像：对每个用户跑 profile_agent（fake LLM/embedding）。
    prof_client = FakeProfileClient()
    with Session(api_engine) as session:
        for uid in user_ids:
            updated = update_user_profile_from_events(user_id=uid, session=session, client=prof_client, force=True)
            assert updated is True
            p = session.get(Profile, uid)
            assert p is not None
            assert p.embedding is not None
            assert p.source_hash

        # Ensure embeddings are consistent length.
        emb_lens = []
        for uid in user_ids:
            p = session.get(Profile, uid)
            arr = array("f")
            arr.frombytes(p.embedding or b"")
            emb_lens.append(len(arr))
        assert len(set(emb_lens)) == 1

    # 3 轮诱导 + 匹配（orchestrator）
    orch_logs = scratch_dir / "logs"
    orch = Orchestrator(
        logs_dir=str(orch_logs),
        belief_hypothesis="match:e2e",
        elicit_client=FakeElicitClient(),
        match_client=FakeMatchClient(),
    )

    posterior = BetaPosterior(alpha=1.0, beta=1.0)
    entropies = [bernoulli_entropy(posterior.mean)]
    matches: list[int] = []

    with Session(api_engine) as session:
        for r in range(1, 4):
            result, posterior = orch.run_round(
                round_index=r,
                session=session,
                user_id=user_ids[0],
                posterior=posterior,
                feedback=LocalFixedFeedback(idx=0, choice="同意", rt=250),
            )
            entropies.append(result.entropy_after)
            matches.append(int(result.match["user_id"]))

    # 断言熵下降曲线单调（非增）。
    for a, b in zip(entropies, entropies[1:], strict=False):
        assert b <= a + 1e-15

    # 匹配结果稳定：3 轮得到相同对象。
    assert len(set(matches)) == 1

    # 输出曲线图到 reports/entropy.png
    out_path = Path("reports") / "entropy.png"
    _write_entropy_png(out_path, entropies)
    assert out_path.exists()
    assert out_path.stat().st_size > 100

    # Also ensure orchestrator logs exist
    log_file = orch_logs / "orchestrator.jsonl"
    assert log_file.exists()
    assert log_file.read_text(encoding="utf-8").strip()
