"""SoulMate Agent Console — 交互式入口（打开就能用）。

功能随项目模块自动启用：
  1 数据库概览 | 2 生成画像(真实LLM) | 3 画像列表
  4 寻找匹配   | 5 一轮诱导卡片       | 6 完整闭环(N轮)
  7 信念状态   | 0 退出
"""
from __future__ import annotations

import os
import sys
import time

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)
os.chdir(PROJECT)

reconfigure = getattr(sys.stdout, "reconfigure", None)
if callable(reconfigure):
    try:
        reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (OSError, ValueError) as exc:
        print(f"  （stdout 编码设置失败：{exc.__class__.__name__}）", file=sys.stderr)

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.db import _engine
from app.models import BehaviorEvent, Profile, User

HAS_PROFILE = HAS_MATCH = HAS_ELICIT = HAS_BELIEF = HAS_ORCH = False

try:
    from app.agents.profile_agent import update_user_profile_from_events

    HAS_PROFILE = True
except ImportError:
    HAS_PROFILE = False
try:
    from app.agents.match_agent import match_user

    HAS_MATCH = True
except ImportError:
    HAS_MATCH = False
try:
    from app.agents.elicit_agent import generate_guess_cards

    HAS_ELICIT = True
except ImportError:
    HAS_ELICIT = False
try:
    from app.core.belief import BetaPosterior, entropy

    HAS_BELIEF = True
except ImportError:
    HAS_BELIEF = False
try:
    from app.agents.orchestrator import Orchestrator

    HAS_ORCH = True
except ImportError:
    HAS_ORCH = False


def hr(title: str = "") -> None:
    print("\n" + "=" * 60)
    if title:
        print(title)
        print("=" * 60)


def ask(prompt: str, default: str = "") -> str:
    try:
        raw = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return default
    return raw or default


def pick_user() -> int | None:
    with Session(_engine) as s:
        uids = list(s.execute(sa.select(User.id).order_by(User.id)).scalars().all())
    if not uids:
        print("  没有用户。请先运行：python scripts/gen_synthetic.py --users 20")
        return None
    raw = ask(f"  选择 user_id（回车=第一个 {uids[0]}）：", str(uids[0]))
    return int(raw) if raw.isdigit() and int(raw) in uids else uids[0]


def overview() -> None:
    hr("数据库概览")
    with Session(_engine) as s:
        for t in ("users", "behavior_events", "elicitations", "responses", "profiles", "beliefs"):
            try:
                n = s.execute(sa.text(f"select count(*) from {t}")).scalar()
            except Exception as e:  # noqa: BLE001
                n = f"未建表 ({e.__class__.__name__})"
            print(f"  {t:<18} {n}")


def build_profile() -> None:
    if not HAS_PROFILE:
        print("  画像模块不可用。")
        return
    uid = pick_user()
    if uid is None:
        return
    with Session(_engine) as s:
        n = s.execute(
            sa.select(sa.func.count()).select_from(BehaviorEvent).where(BehaviorEvent.user_id == uid)
        ).scalar()
        print(f"  用户 {uid} 行为事件：{n}｜调用真实 LLM + embeddings …")
        try:
            changed = update_user_profile_from_events(user_id=uid, session=s, force=True)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ 失败：{e}")
            return
        p = s.get(Profile, uid)
        emb = p.embedding or b""
        print(f"  ✓ 更新={changed}｜摘要 {len(p.summary or '')} 字｜向量 {len(emb)//4} 维")
        print(f"\n  {p.summary or ''}\n")


def show_profiles(limit: int = 10) -> None:
    hr(f"用户画像（前 {limit} 条）")
    with Session(_engine) as s:
        rows = s.execute(sa.select(Profile).order_by(Profile.user_id).limit(limit)).scalars().all()
    if not rows:
        print("  （暂无画像，请先执行菜单 2）")
        return
    for p in rows:
        emb = p.embedding or b""
        print(f"\n  [user {p.user_id}] 向量={len(emb)//4}维 hash={(p.source_hash or '')[:12]}")
        print(f"  {p.summary or '(空)'}")


def do_match() -> dict | None:
    if not HAS_MATCH:
        print("  匹配模块不可用（第 11 步未完成）。")
        return None
    uid = pick_user()
    if uid is None:
        return None
    hr(f"为用户 {uid} 寻找匹配")
    print("  召回向量相似用户 + LLM 重排中（真实请求）…")
    with Session(_engine) as s:
        try:
            result = match_user(user_id=uid, session=s)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ 失败：{e}")
            return None
    print(f"  最佳匹配：user {result.get('user_id')}｜分数 {result.get('score')}｜熵 {result.get('entropy')}")
    for r in result.get("reasons", []) or []:
        print(f"    · {r}")
    return result


class ConsoleFeedback:
    """把诱导卡片呈现在终端，读取用户作答（含反应时长与选项极性标注）。"""

    def __init__(self, session=None) -> None:
        self._session = session
        self.last_gain = 0.0

    def _polarity_of(self, elicitation_id: int) -> dict[str, str]:
        """读取该卡片的选项极性：文本 -> confirm/disconfirm/uncertain。"""
        if self._session is None:
            return {}
        try:
            from app.agents.elicit_agent import _normalize_options
            from app.models import Elicitation

            e = self._session.get(Elicitation, elicitation_id)
            if e is None:
                return {}
            return {o["text"]: o["polarity"] for o in _normalize_options(e.options)}
        except Exception:  # noqa: BLE001
            return {}

    def choose(self, *, cards):
        print("\n  ── 请回答以下猜测卡（这些信息不一定准确，你的选择本身就是信息）──")
        print("  提示：[confirm]=肯定证据（降熵）｜[disconfirm]=否定证据（降熵）｜[uncertain]=无证据（熵不变）")
        for i, c in enumerate(cards, 1):
            print(f"\n  [{i}] {c.question}")
            pol = self._polarity_of(c.elicitation_id)
            for j, o in enumerate(c.options, 1):
                tag = pol.get(o, "")
                suffix = f"  [{tag}]" if tag else ""
                print(f"        {j}) {o}{suffix}")
            print(f"        (期望信息增益 {c.expected_information_gain:.4f})")
        raw = ask(f"\n  选择卡片编号（1-{len(cards)}，回车=1）：", "1")
        idx = int(raw) - 1 if raw.isdigit() and 1 <= int(raw) <= len(cards) else 0
        card = cards[idx]
        t0 = time.monotonic()
        opt = ask(f"  你的选择（1-{len(card.options)}，或直接写自己的答案）：", "1")
        rt = int((time.monotonic() - t0) * 1000)
        if opt.isdigit() and 1 <= int(opt) <= len(card.options):
            choice = card.options[int(opt) - 1]
        else:
            choice = opt
        print(f"  → 记录：卡片#{card.elicitation_id}｜选择「{choice}」｜反应 {rt}ms")
        return idx, choice, rt


def one_round(posterior):
    if not (HAS_ELICIT and HAS_BELIEF):
        print("  诱导卡片或信念模块不可用。")
        return posterior
    uid = pick_user()
    if uid is None:
        return posterior
    hr(f"一轮诱导卡片 · user {uid}")
    with Session(_engine) as s:
        try:
            cards = generate_guess_cards(user_id=uid, posterior=posterior, session=s)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ 生成卡片失败：{e}")
            return posterior
    if not cards:
        print("  没有生成卡片（检查是否已生成 elicitations）。")
        return posterior
    h_before = entropy(posterior.mean)
    with Session(_engine) as s:
        fb = ConsoleFeedback(session=s)
        _, choice, rt = fb.choose(cards=cards)
        from app.agents.orchestrator import belief_update

        try:
            posterior = belief_update(
                session=s,
                user_id=uid,
                elicitation_id=cards[0].elicitation_id,
                posterior=posterior,
                choice=choice,
                reaction_time_ms=rt,
                hypothesis="match",
                evidence_weight=cards[0].evidence_weight,
            )
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ 信念更新失败：{e}")
            return posterior
    h_after = entropy(posterior.mean)
    print(f"\n  信念：均值 {posterior.mean:.3f}（α={posterior.alpha:.1f}, β={posterior.beta:.1f}）")
    print(f"  熵：{h_before:.4f} → {h_after:.4f}  （下降 {h_before - h_after:+.4f}）")
    return posterior


def full_loop(posterior):
    if not HAS_ORCH:
        print("  Orchestrator 不可用（第 13 步未完成）。")
        return posterior
    uid = pick_user()
    if uid is None:
        return posterior
    rounds = int(ask("  跑几轮？（回车=3）：", "3") or 3)
    hr(f"完整闭环 · user {uid} · {rounds} 轮")
    orch = Orchestrator()
    with Session(_engine) as s:
        fb = ConsoleFeedback(session=s)
        for i in range(rounds):
            print(f"\n──────── 第 {i + 1}/{rounds} 轮 ────────")
            try:
                result, posterior = orch.run_round(
                    round_index=i,
                    session=s,
                    user_id=uid,
                    posterior=posterior,
                    feedback=fb,
                )
            except Exception as e:  # noqa: BLE001
                print(f"  ✗ 第 {i + 1} 轮失败：{e}")
                break
            print(f"  熵：{result.entropy_before:.4f} → {result.entropy_after:.4f}")
            if result.match:
                print(f"  匹配：user {result.match.get('user_id')}｜分数 {result.match.get('score')}")
                for r in (result.match.get("reasons") or [])[:2]:
                    print(f"    · {r}")
            if result.explanation:
                print(f"  解释：{result.explanation}")
    return posterior


def belief_state(posterior) -> None:
    hr("信念状态")
    print(f"  当前会话后验：α={posterior.alpha:.2f}, β={posterior.beta:.2f}, 均值={posterior.mean:.3f}, 熵={entropy(posterior.mean):.4f}")
    with Session(_engine) as s:
        try:
            rows = s.execute(sa.text("select hypothesis, confidence from beliefs order by updated_at desc limit 8")).fetchall()
        except Exception as e:  # noqa: BLE001
            print(f"  （beliefs 表读取失败：{e}）")
            return
    if not rows:
        print("  （beliefs 表暂无记录，跑一轮闭环后会写入）")
    for h, c in rows:
        print(f"  · {h}: {c}")


def menu() -> None:
    posterior = BetaPosterior(alpha=1.0, beta=1.0) if HAS_BELIEF else None
    while True:
        hr("SoulMate Agent 控制台")
        print("  1. 数据库概览")
        print(f"  2. 生成/刷新用户画像（真实 LLM）{'' if HAS_PROFILE else '   [不可用]'}")
        print("  3. 查看用户画像列表")
        print(f"  4. 为用户寻找匹配{'' if HAS_MATCH else '   [不可用]'}")
        print(f"  5. 一轮诱导卡片（回答问题 → 信念更新）{'' if HAS_ELICIT and HAS_BELIEF else '   [不可用]'}")
        print(f"  6. 完整闭环：探测→反馈→更新→匹配→解释{'' if HAS_ORCH else '   [不可用]'}")
        print(f"  7. 信念状态{'' if HAS_BELIEF else '   [不可用]'}")
        print("  0. 退出")
        choice = ask("\n  请选择 > ", "0")

        if choice == "1":
            overview()
        elif choice == "2":
            build_profile()
        elif choice == "3":
            show_profiles()
        elif choice == "4":
            do_match()
        elif choice == "5":
            posterior = one_round(posterior)
        elif choice == "6":
            posterior = full_loop(posterior)
        elif choice == "7":
            if HAS_BELIEF:
                belief_state(posterior)
            else:
                print("  信念模块不可用。")
        elif choice in ("0", "q", "exit"):
            print("  再见。")
            return
        else:
            print("  无效选择。")


if __name__ == "__main__":
    try:
        menu()
    except (EOFError, KeyboardInterrupt):
        print("\n  已退出。")
