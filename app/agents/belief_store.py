"""信念状态的无状态存取：从 responses 历史重建 Beta 后验。

设计动机（Agent 审视结论 #1）：
``beliefs`` 表只持久化了 ``confidence``（后验均值），丢失了证据强度 α/β，
导致后验无法跨请求、跨进程恢复。但重建所需的原始数据其实都在库里：

    α = 1 + Σ(confirm 证据)，  β = 1 + Σ(disconfirm 证据)

即对某个用户全部 ``responses``，按所答 ``elicitation.options`` 的极性回放即可。
于是本模块让信念可无状态恢复，``beliefs`` 行退化为可校验的缓存。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.evidence import resolve_choice_evidence
from app.core.belief import BetaPosterior
from app.models import Belief, Elicitation, Response

DEFAULT_HYPOTHESIS = "match"
#: 先验 Beta(1, 1)：对"二人是否匹配"这一假设不偏不倚，初始熵为 ln2。
PRIOR = BetaPosterior(alpha=1.0, beta=1.0)


def load_posterior(
    session: Session,
    *,
    user_id: int,
    hypothesis: str = DEFAULT_HYPOTHESIS,
) -> BetaPosterior:
    """按作答历史回放，重建该用户在某假设上的 Beta 后验。

    注意：``Elicitation`` 当前未持久化 ``evidence_weight``，回放统一按 1.0 计。
    如需支持差异化权重，应给 elicitations 增加该列并在此读取。
    """
    rows = session.execute(
        select(Response, Elicitation)
        .join(Elicitation, Response.elicitation_id == Elicitation.id)
        .where(Response.user_id == user_id)
        .order_by(Response.id.asc())
    ).all()

    alpha = PRIOR.alpha
    beta = PRIOR.beta
    for response, elicitation in rows:
        evidence = resolve_choice_evidence(elicitation.options, response.choice, weight=1.0)
        alpha += evidence.positive
        beta += evidence.negative
    return BetaPosterior(alpha=alpha, beta=beta)


def sync_belief_row(
    session: Session,
    *,
    user_id: int,
    hypothesis: str,
    posterior: BetaPosterior,
) -> Belief:
    """把重建出的后验均值写回 ``beliefs`` 缓存行（不存在则创建）。"""
    belief = session.execute(
        select(Belief).where(Belief.user_id == user_id, Belief.hypothesis == hypothesis)
    ).scalar_one_or_none()
    if belief is None:
        belief = Belief(user_id=user_id, hypothesis=hypothesis, confidence=float(posterior.mean))
        session.add(belief)
    else:
        belief.confidence = float(posterior.mean)
    session.commit()
    return belief
