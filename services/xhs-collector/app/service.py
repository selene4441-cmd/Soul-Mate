from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import XhsNote, XhsUser, utcnow
from .normalize import ParsedIdentifier, parse_line
from .schemas import CollectResult
from .tikhub import TikhubClient, TikhubError


def _get_by_user_id(db: Session, user_id: str) -> XhsUser | None:
    return db.execute(select(XhsUser).where(XhsUser.user_id == user_id)).scalar_one_or_none()


def _get_by_source(db: Session, source: str) -> XhsUser | None:
    return db.execute(select(XhsUser).where(XhsUser.source == source)).scalars().first()


def _apply_fields(lead: XhsUser, parsed: ParsedIdentifier, fields: dict[str, Any]) -> None:
    lead.identifier_type = parsed.type
    lead.user_id = fields.get("user_id") or lead.user_id
    lead.red_id = fields.get("red_id") or lead.red_id
    lead.nickname = fields.get("nickname")
    lead.avatar = fields.get("avatar")
    lead.description = fields.get("description")
    lead.gender = fields.get("gender")
    lead.ip_location = fields.get("ip_location")
    lead.followers_count = fields.get("followers_count")
    lead.following_count = fields.get("following_count")
    lead.notes_count = fields.get("notes_count")
    lead.interaction_count = fields.get("interaction_count")
    lead.status = "fetched"
    lead.error = None
    lead.raw_json = fields.get("raw_json")


def _upsert_fetched(db: Session, parsed: ParsedIdentifier, fields: dict[str, Any]) -> tuple[XhsUser, bool]:
    user_id = fields.get("user_id")
    lead = _get_by_user_id(db, user_id) if user_id else None
    if lead is None and user_id is None:
        lead = _get_by_source(db, parsed.value)

    created = lead is None
    if lead is None:
        lead = XhsUser(source=parsed.value, identifier_type=parsed.type)
        db.add(lead)
    _apply_fields(lead, parsed, fields)
    db.commit()
    db.refresh(lead)
    return lead, created


def _upsert_failed(db: Session, parsed: ParsedIdentifier, message: str) -> tuple[XhsUser, bool]:
    lead = _get_by_source(db, parsed.value)
    created = lead is None
    if lead is None:
        lead = XhsUser(source=parsed.value, identifier_type=parsed.type)
        db.add(lead)
    if parsed.user_id:
        lead.user_id = lead.user_id or parsed.user_id
    lead.status = "failed"
    lead.error = message
    db.commit()
    db.refresh(lead)
    return lead, created


def _upsert_needs_review(db: Session, parsed: ParsedIdentifier) -> tuple[XhsUser, bool, bool]:
    lead = _get_by_source(db, parsed.value)
    if lead is not None:
        return lead, False, True

    message = (
        "小红书号无法直接被 Tikhub 解析，请提供该用户的主页分享链接或 24 位 hex user_id 后解析"
        if parsed.type == "red_id"
        else "无法识别该标识，请提供主页分享链接或 user_id"
    )
    lead = XhsUser(
        source=parsed.value,
        identifier_type=parsed.type,
        status="needs_review",
        error=message,
    )
    if parsed.type == "red_id":
        lead.red_id = parsed.value
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead, True, False


def collect_identifiers(
    db: Session,
    text: str,
    client: TikhubClient,
    interval: float = 0.3,
) -> list[CollectResult]:
    results: list[CollectResult] = []
    seen: set[str] = set()

    for line in text.splitlines():
        for parsed in parse_line(line):
            key = parsed.user_id or parsed.share_text or parsed.value
            if key in seen:
                continue
            seen.add(key)

            if parsed.type in {"user_id", "share_text"}:
                try:
                    fields = client.fetch_user(parsed)
                except TikhubError as exc:
                    lead, _ = _upsert_failed(db, parsed, str(exc))
                    results.append(
                        CollectResult(
                            raw=parsed.value,
                            identifier_type=parsed.type,
                            status="failed",
                            message=str(exc),
                            lead_id=lead.id,
                        )
                    )
                else:
                    lead, created = _upsert_fetched(db, parsed, fields)
                    results.append(
                        CollectResult(
                            raw=parsed.value,
                            identifier_type=parsed.type,
                            status="created" if created else "updated",
                            user_id=lead.user_id,
                            nickname=lead.nickname,
                            lead_id=lead.id,
                        )
                    )
                finally:
                    time.sleep(interval)
            else:
                lead, _, skipped = _upsert_needs_review(db, parsed)
                if skipped:
                    results.append(
                        CollectResult(
                            raw=parsed.value,
                            identifier_type=parsed.type,
                            status="skipped",
                            message="该标识已存在且待解析",
                            lead_id=lead.id,
                        )
                    )
                else:
                    results.append(
                        CollectResult(
                            raw=parsed.value,
                            identifier_type=parsed.type,
                            status="needs_review",
                            message=lead.error or "",
                            lead_id=lead.id,
                        )
                    )

    return results


def refresh_all(db: Session, client: TikhubClient, interval: float = 0.3) -> dict[str, int]:
    """Incrementally refresh fans/notes counts for every fetched lead with a user_id."""
    leads = db.execute(
        select(XhsUser)
        .where(XhsUser.status == "fetched", XhsUser.user_id.is_not(None))
        .order_by(XhsUser.last_refreshed_at.is_(None).desc(), XhsUser.last_refreshed_at.asc())
    ).scalars().all()

    total = len(leads)
    refreshed = 0
    failed = 0

    for lead in leads:
        parsed = ParsedIdentifier(type="user_id", value=lead.user_id or "", user_id=lead.user_id)
        try:
            fields = client.fetch_user(parsed)
        except TikhubError as exc:
            lead.refresh_error = str(exc)
            failed += 1
        else:
            _apply_fields(lead, parsed, fields)
            lead.last_refreshed_at = utcnow()
            lead.refresh_error = None
            refreshed += 1
        finally:
            time.sleep(interval)

    db.commit()
    return {"total": total, "refreshed": refreshed, "failed": failed}


def resolve_lead(db: Session, lead_id: int, parsed: ParsedIdentifier, client: TikhubClient) -> XhsUser:
    lead = db.get(XhsUser, lead_id)
    if lead is None:
        raise ValueError("记录不存在")

    fields = client.fetch_user(parsed)
    user_id = fields.get("user_id")
    if user_id:
        existing = _get_by_user_id(db, user_id)
        if existing is not None and existing.id != lead_id:
            raise ValueError(f"该用户已存在于记录 #{existing.id}，无需重复添加")

    _apply_fields(lead, parsed, fields)
    db.commit()
    db.refresh(lead)
    return lead


def _get_note_by_id(db: Session, note_id: str) -> XhsNote | None:
    return db.execute(select(XhsNote).where(XhsNote.note_id == note_id)).scalar_one_or_none()


def _apply_note_fields(note: XhsNote, data: dict[str, Any]) -> None:
    for field, value in data.items():
        if value is None:
            continue
        if isinstance(value, str) and value == "":
            continue

        if field == "images":
            note.images = json.dumps(value or [], ensure_ascii=False)
        elif field == "tags":
            note.tags = json.dumps(value or [], ensure_ascii=False)
        elif field == "published_at":
            note.published_at = datetime.fromtimestamp(value, tz=timezone.utc).replace(tzinfo=None)
        elif field == "raw_json":
            note.raw_json = value
        elif hasattr(note, field) and field not in {"id", "lead_id", "note_id"}:
            setattr(note, field, value)

    note.last_synced_at = utcnow()
    note.sync_error = None


def sync_notes(
    db: Session,
    lead: XhsUser,
    client: TikhubClient,
    interval: float = 0.3,
    max_notes: int = 100,
    force_details: bool = False,
) -> dict[str, int]:
    """Fetch a lead's posted notes and their full content, then upsert them."""
    if not lead.user_id:
        return {"found": 0, "created": 0, "updated": 0, "details": 0, "failed_details": 0}

    result = client.fetch_posted_notes(lead.user_id, max_notes=max_notes)
    notes_data = result["notes"]
    created = 0
    updated = 0
    details = 0
    failed_details = 0

    for item in notes_data:
        note_id = item.get("note_id")
        if not note_id:
            continue

        note = _get_note_by_id(db, note_id)
        is_new = note is None
        if is_new:
            note = XhsNote(lead_id=lead.id, note_id=note_id)
            db.add(note)
            created += 1
        else:
            updated += 1

        _apply_note_fields(note, item)
        db.flush()

        if is_new or force_details or not note.desc:
            try:
                detail = client.fetch_note_detail(note_id, item.get("note_type") or "")
                _apply_note_fields(note, detail)
                details += 1
            except TikhubError as exc:
                note.sync_error = str(exc)
                failed_details += 1
            finally:
                time.sleep(interval)

    db.commit()
    return {
        "found": len(notes_data),
        "created": created,
        "updated": updated,
        "details": details,
        "failed_details": failed_details,
    }