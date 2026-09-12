from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CollectRequest(BaseModel):
    text: str = Field(default="", description="从微信群复制的账号文本，每行一个，或整段分享文案")


class CollectResult(BaseModel):
    raw: str
    identifier_type: str
    status: str
    message: str = ""
    user_id: str | None = None
    nickname: str | None = None
    lead_id: int | None = None


class CollectResponse(BaseModel):
    results: list[CollectResult]
    summary: dict[str, int]


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    identifier_type: str
    user_id: str | None
    red_id: str | None
    nickname: str | None
    avatar: str | None
    description: str | None
    gender: str | None
    ip_location: str | None
    followers_count: int | None
    following_count: int | None
    notes_count: int | None
    interaction_count: int | None
    status: str
    error: str | None
    created_at: datetime
    updated_at: datetime


class LeadList(BaseModel):
    items: list[LeadOut]
    total: int


class ResolveRequest(BaseModel):
    user_id: str | None = None
    share_text: str | None = None