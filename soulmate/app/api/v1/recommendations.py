from __future__ import annotations

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.api.v1.errors import APIError
from app.api.v1.questionnaire_def import QUESTIONNAIRE
from app.api.v1.security import CurrentUser, SessionDep, as_utc, new_id, require_consent
from app.models import Claim, Consent, RecommendationItem, RecommendationSession, User

router = APIRouter(prefix="/recommendations", tags=["v1/recommendations"])


def _dt_z(dt) -> str:
    return as_utc(dt).isoformat().replace("+00:00", "Z")


class RecommendationItemOut(BaseModel):
    recommendation_id: str
    candidate_id: str
    display_name: str
    headline: str
    common_signals: list[str]
    differences: list[str]
    unknowns: list[str]
    how_to_continue: list[str]
    evidence_ids: list[str]


class RecommendationsOut(BaseModel):
    generated_at: str
    session_id: str
    items: list[RecommendationItemOut]


def _evidence_union(claims: list[Claim]) -> list[str]:
    return sorted({eid for c in claims for eid in (c.evidence_ids or [])})


def _label_maps() -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    """维度键 / 选项值 → 面向用户的中文说法（取问卷的 section 与选项 label）。

    内部键（如 ``life_weekend``）只用于数据层，不能出现在给用户看的文案里。
    """
    dimensions: dict[str, str] = {}
    options: dict[tuple[str, str], str] = {}
    for question in QUESTIONNAIRE.get("questions", []):
        dimension = str(question.get("dimension") or "")
        if not dimension:
            continue
        dimensions[dimension] = str(question.get("section") or dimension)
        for option in question.get("options") or []:
            value = str(option.get("value") or "")
            if value:
                options[(dimension, value)] = str(option.get("label") or value)
    return dimensions, options


DIMENSION_LABELS, OPTION_LABELS = _label_maps()


def _dimension_label(dimension: str) -> str:
    return DIMENSION_LABELS.get(dimension, dimension)


def _option_label(dimension: str, value: str) -> str:
    return OPTION_LABELS.get((dimension, value), value)


def _headline(*, common_signals: list[str], differences: list[str], unknowns: list[str]) -> str:
    parts: list[str] = []
    if common_signals:
        parts.append("有一些共同点")
    if differences:
        parts.append("也有一些差异")
    if unknowns:
        parts.append("还需要继续了解")
    return "，".join(parts) if parts else "可以从一个具体生活场景开始了解"


def _build_item(*, me_claims: list[Claim], cand: User, cand_claims: list[Claim]) -> RecommendationItem:
    me_by_dim = {c.dimension: c.value for c in me_claims}
    cand_by_dim = {c.dimension: c.value for c in cand_claims}

    common_dims = [d for d in me_by_dim.keys() & cand_by_dim.keys() if me_by_dim[d] == cand_by_dim[d]]
    diff_dims = [d for d in me_by_dim.keys() & cand_by_dim.keys() if me_by_dim[d] != cand_by_dim[d]]
    unknown_dims = [d for d in me_by_dim.keys() - cand_by_dim.keys()]

    common_signals = [
        f"你们在「{_dimension_label(d)}」上的选择比较接近：{_option_label(d, me_by_dim[d])}"
        for d in common_dims[:1]
    ]
    differences = [
        f"在「{_dimension_label(d)}」上，你选了「{_option_label(d, me_by_dim[d])}」，"
        f"对方选了「{_option_label(d, cand_by_dim[d])}」——期待可能不同，不一定是问题"
        for d in diff_dims[:1]
    ]
    unknowns = [f"还不知道对方在「{_dimension_label(d)}」上的选择" for d in unknown_dims[:1]]
    if not unknowns and common_dims:
        # 双方都答完了：如实说出「还没验证过」，保证「还不确定」区块永远有内容（产品红线）
        first_common = common_dims[0]
        unknowns = [
            f"「{_dimension_label(first_common)}」上你们的选择接近，"
            f"但那只是问卷里的选择，还没有在真实相处里验证过"
        ]
    how_to_continue = ["可以从一个具体生活场景开始聊"]

    evidence_ids = _evidence_union(cand_claims)
    return RecommendationItem(
        id=new_id(),
        session_id="",
        user_id=0,
        candidate_id=int(cand.id),
        headline=_headline(common_signals=common_signals, differences=differences, unknowns=unknowns),
        common_signals=common_signals,
        differences=differences,
        unknowns=unknowns,
        how_to_continue=how_to_continue,
        evidence_ids=evidence_ids,
    )


def _candidate_pool(*, db: Session, me_id: int, limit: int) -> list[User]:
    candidate_ids = (
        db.execute(
            select(Consent.user_id)
            .where(
                Consent.scope == "matching:v1",
                Consent.revoked_at.is_(None),
                Consent.user_id != me_id,
            )
            .distinct()
        )
        .scalars()
        .all()
    )
    if not candidate_ids:
        return []

    coverage = dict(
        db.execute(
            select(Claim.user_id, func.count(func.distinct(Claim.dimension)))
            .where(Claim.user_id.in_(candidate_ids))
            .group_by(Claim.user_id)
        ).all()
    )

    candidates = db.execute(select(User).where(User.id.in_(candidate_ids))).scalars().all()
    candidates.sort(key=lambda u: (-int(coverage.get(u.id, 0)), int(u.id)))
    return candidates[:limit]


@router.post("", response_model=RecommendationsOut, dependencies=[Depends(require_consent("matching:v1"))])
def create_recommendations(user: CurrentUser, db: SessionDep) -> RecommendationsOut:
    me_claims = db.execute(select(Claim).where(Claim.user_id == user.id)).scalars().all()
    candidates = _candidate_pool(db=db, me_id=int(user.id), limit=10)

    session_row = RecommendationSession(id=new_id(), user_id=int(user.id))
    db.add(session_row)
    db.flush()

    items_out: list[RecommendationItemOut] = []
    for cand in candidates[:5]:
        cand_claims = db.execute(select(Claim).where(Claim.user_id == cand.id)).scalars().all()
        if not cand_claims:
            continue
        item = _build_item(me_claims=me_claims, cand=cand, cand_claims=cand_claims)
        item.session_id = session_row.id
        item.user_id = int(user.id)
        db.add(item)
        items_out.append(
            RecommendationItemOut(
                recommendation_id=item.id,
                candidate_id=str(cand.id),
                display_name=cand.display_name or "匿名",
                headline=item.headline,
                common_signals=list(item.common_signals or []),
                differences=list(item.differences or []),
                unknowns=list(item.unknowns or []),
                how_to_continue=list(item.how_to_continue or []),
                evidence_ids=list(item.evidence_ids or []),
            )
        )
        if len(items_out) >= 3:
            break

    db.commit()
    generated_at = db.get(RecommendationSession, session_row.id).generated_at  # type: ignore[union-attr]
    return RecommendationsOut(
        generated_at=_dt_z(generated_at),
        session_id=session_row.id,
        items=items_out,
    )


@router.get("/{candidate_id}", response_model=RecommendationsOut, dependencies=[Depends(require_consent("matching:v1"))])
def get_recommendation(
    user: CurrentUser,
    db: SessionDep,
    candidate_id: int = Path(..., ge=1),
) -> RecommendationsOut:
    row = (
        db.execute(
            select(RecommendationItem, RecommendationSession)
            .join(RecommendationSession, RecommendationItem.session_id == RecommendationSession.id)
            .where(
                and_(
                    RecommendationItem.user_id == user.id,
                    RecommendationItem.candidate_id == candidate_id,
                )
            )
            .order_by(RecommendationSession.generated_at.desc())
        )
        .first()
    )
    if row is None:
        raise APIError(code="NOT_FOUND", message="recommendation_not_found", status_code=404)
    item, sess = row
    cand = db.get(User, candidate_id)
    display_name = cand.display_name if cand else "匿名"
    return RecommendationsOut(
        generated_at=_dt_z(sess.generated_at),
        session_id=sess.id,
        items=[
            RecommendationItemOut(
                recommendation_id=item.id,
                candidate_id=str(candidate_id),
                display_name=display_name,
                headline=item.headline,
                common_signals=list(item.common_signals or []),
                differences=list(item.differences or []),
                unknowns=list(item.unknowns or []),
                how_to_continue=list(item.how_to_continue or []),
                evidence_ids=list(item.evidence_ids or []),
            )
        ],
    )

