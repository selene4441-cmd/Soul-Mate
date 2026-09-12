from __future__ import annotations

import csv
import json
import io
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .dependencies import get_db
from .models import XhsNote, XhsUser
from .normalize import ParsedIdentifier
from .schemas import (
    NoteList,
    NoteOut,
    CollectRequest,
    CollectResponse,
    LeadList,
    LeadOut,
    ResolveRequest,
)
from .service import collect_identifiers, refresh_all, resolve_lead, sync_notes
from .tikhub import TikhubError

router = APIRouter()


@router.post("/api/v1/collect", response_model=CollectResponse)
def collect(req: CollectRequest, request: Request, db: Session = Depends(get_db)) -> CollectResponse:
    client = request.app.state.tikhub
    interval = request.app.state.settings.request_interval_seconds
    results = collect_identifiers(db, req.text, client, interval=interval)
    summary = dict(Counter(result.status for result in results))
    return CollectResponse(results=results, summary=summary)


@router.get("/api/v1/leads", response_model=LeadList)
def list_leads(
    request: Request,
    status: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> LeadList:
    stmt = select(XhsUser)
    if status:
        stmt = stmt.where(XhsUser.status == status)
    if q:

        stmt = stmt.where(
            or_(
                XhsUser.nickname.contains(q),
                XhsUser.user_id.contains(q),
                XhsUser.red_id.contains(q),
                XhsUser.source.contains(q),
            )
        )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.order_by(XhsUser.id.desc()).limit(limit).offset(offset)).scalars().all()
    return LeadList(items=[LeadOut.model_validate(row) for row in rows], total=total)


@router.get("/api/v1/leads/export.csv")
def export_csv(db: Session = Depends(get_db)) -> Response:
    rows = db.execute(select(XhsUser).order_by(XhsUser.id.asc())).scalars().all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id", "source", "identifier_type", "user_id", "red_id", "nickname",
            "gender", "ip_location", "followers_count", "following_count",
            "notes_count", "interaction_count", "status", "error", "created_at",
        ]
    )
    for lead in rows:
        writer.writerow(
            [
                lead.id, lead.source, lead.identifier_type, lead.user_id, lead.red_id,
                lead.nickname, lead.gender, lead.ip_location, lead.followers_count,
                lead.following_count, lead.notes_count, lead.interaction_count,
                lead.status, lead.error, lead.created_at.isoformat() if lead.created_at else "",
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=xhs_leads.csv"},
    )


@router.get("/api/v1/leads/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: int, db: Session = Depends(get_db)) -> XhsUser:
    lead = db.get(XhsUser, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return lead


def _identifier_from_resolve(req: ResolveRequest) -> ParsedIdentifier | None:
    if req.user_id:
        value = req.user_id.strip()
        return ParsedIdentifier(type="user_id", value=value, user_id=value)
    if req.share_text:
        value = req.share_text.strip()
        return ParsedIdentifier(type="share_text", value=value, share_text=value)
    return None


@router.post("/api/v1/leads/{lead_id}/resolve", response_model=LeadOut)
def resolve(lead_id: int, req: ResolveRequest, request: Request, db: Session = Depends(get_db)) -> XhsUser:
    parsed = _identifier_from_resolve(req)
    if parsed is None:
        raise HTTPException(status_code=400, detail="请提供 user_id 或 share_text")

    client = request.app.state.tikhub
    try:
        return resolve_lead(db, lead_id, parsed, client)
    except TikhubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.post("/api/v1/refresh")
def refresh_now(request: Request, db: Session = Depends(get_db)) -> dict[str, int]:
    client = request.app.state.tikhub
    interval = request.app.state.settings.request_interval_seconds
    return refresh_all(db, client, interval=interval)

def _note_to_out(note: XhsNote) -> NoteOut:
    return NoteOut(
        id=note.id,
        lead_id=note.lead_id,
        note_id=note.note_id,
        title=note.title,
        desc=note.desc,
        note_type=note.note_type,
        likes=note.likes,
        comments_count=note.comments_count,
        collected_count=note.collected_count,
        share_count=note.share_count,
        ip_location=note.ip_location,
        images=json.loads(note.images) if note.images else [],
        tags=json.loads(note.tags) if note.tags else [],
        note_url=note.note_url,
        published_at=note.published_at,
        last_synced_at=note.last_synced_at,
        sync_error=note.sync_error,
        created_at=note.created_at,
    )


@router.get("/api/v1/leads/{lead_id}/notes", response_model=NoteList)
def list_notes(lead_id: int, db: Session = Depends(get_db)) -> NoteList:
    lead = db.get(XhsUser, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    notes = db.execute(
        select(XhsNote).where(XhsNote.lead_id == lead_id).order_by(XhsNote.id.desc())
    ).scalars().all()
    return NoteList(items=[_note_to_out(note) for note in notes], total=len(notes))


@router.post("/api/v1/leads/{lead_id}/notes/sync")
def sync_notes_endpoint(lead_id: int, request: Request, db: Session = Depends(get_db)) -> dict[str, int]:
    lead = db.get(XhsUser, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    client = request.app.state.tikhub
    interval = request.app.state.settings.request_interval_seconds
    try:
        return sync_notes(db, lead, client, interval=interval)
    except TikhubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc