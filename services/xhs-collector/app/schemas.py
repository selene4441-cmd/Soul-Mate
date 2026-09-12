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
    profile_url: str | None = None
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
    profile_url: str | None = None
    last_refreshed_at: datetime | None
    refresh_error: str | None
    created_at: datetime
    updated_at: datetime


class LeadList(BaseModel):
    items: list[LeadOut]
    total: int


class ResolveRequest(BaseModel):
    user_id: str | None = None
    share_text: str | None = None


class AccountUrlRequest(BaseModel):
    account: str = Field(default="", description="小红书账号（主页链接/分享短链/24 位 user_id/小红书号）")


class AccountUrlResponse(BaseModel):
    account: str
    status: str
    profile_url: str | None = None
    user_id: str | None = None
    nickname: str | None = None
    red_id: str | None = None
    message: str = ""


class NoteOut(BaseModel):
    id: int
    lead_id: int
    note_id: str
    title: str | None
    desc: str | None
    note_type: str | None
    likes: int | None
    comments_count: int | None
    collected_count: int | None
    share_count: int | None
    ip_location: str | None
    images: list[str] = []
    tags: list[str] = []
    note_url: str | None
    published_at: datetime | None
    last_synced_at: datetime | None
    sync_error: str | None
    created_at: datetime


class NoteList(BaseModel):
    items: list[NoteOut]
    total: int
