from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class RegisterRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=10, max_length=128)
    birth_year: int = Field(ge=1900, le=2100)
    region: str = Field(min_length=1, max_length=80)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value:
            raise ValueError("请输入有效邮箱")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str


class SessionUser(ApiModel):
    id: str
    display_name: str
    email: str
    birth_year: int
    region: str
    role: str
    status: str


class SessionResponse(BaseModel):
    user: SessionUser
    csrf_token: str


class ConsentRequest(BaseModel):
    scope: Literal["matching:v1", "conversation:v1", "outcomes:v1"]
    purpose: str = Field(min_length=5, max_length=255)


class ConsentResponse(ApiModel):
    id: str
    scope: str
    version: str
    purpose: str
    granted_at: datetime
    revoked_at: datetime | None


class QuestionnaireOption(BaseModel):
    value: str
    label: str


class QuestionnaireQuestion(BaseModel):
    id: str
    section: str
    dimension: str
    prompt: str
    help_text: str
    kind: Literal["single", "multi"]
    sensitivity: Literal["L1", "L2"]
    claim_type: Literal["fact", "preference", "state"]
    stability: Literal["high", "medium", "low"]
    required: bool
    options: list[QuestionnaireOption]
    min_selections: int | None = None
    max_selections: int | None = None


class QuestionnaireResponse(BaseModel):
    version: str
    estimated_minutes: int
    questions: list[QuestionnaireQuestion]


class QuestionnaireSubmission(BaseModel):
    version: str
    answers: dict[str, str | list[str]]


class ClaimResponse(ApiModel):
    id: str
    dimension: str
    value: Any
    claim_type: str
    evidence_ids: list[str]
    observed_at: datetime
    expires_at: datetime
    sensitivity: str
    user_editable: bool
    user_confirmed: bool
    correction_state: str | None


class ClaimFeedbackRequest(BaseModel):
    feedback: Literal["more_like_this", "not_like_this", "unsure"]


class ClaimUpdateRequest(BaseModel):
    value: Any
    user_confirmed: bool = True


class CandidateLead(ApiModel):
    recommendation_id: str
    candidate_id: str
    display_name: str
    headline: str
    common_signals: list[str]
    differences: list[str]
    unknowns: list[str]
    how_to_continue: list[str]
    evidence_ids: list[str]


class RecommendationBundle(BaseModel):
    generated_at: datetime
    session_id: str
    items: list[CandidateLead]


class ActionRequest(BaseModel):
    action: Literal["more_like_this", "not_for_me", "saved", "seen"]


class CueOption(BaseModel):
    id: str
    cue_type: Literal["common", "difference", "unknown", "boundary", "custom"]
    text: str


class InvitationRequest(BaseModel):
    candidate_id: str
    message: str | None = Field(default=None, max_length=300)


class ConnectionRequestCreate(BaseModel):
    candidate_id: str
    recommendation_id: str | None = None
    recommendation_session_id: str | None = Field(default=None, max_length=64)
    cue_type: Literal["common", "difference", "unknown", "boundary", "custom"] = "unknown"
    topic_text: str | None = Field(default=None, min_length=1, max_length=300)
    personal_message: str | None = Field(default=None, max_length=300)


class ConnectionDecisionRequest(BaseModel):
    reason_private: str | None = Field(default=None, max_length=300)


class ConnectionRequestResponse(BaseModel):
    id: str
    direction: Literal["incoming", "outgoing"]
    other_user: dict[str, str]
    status: str
    cue_type: str
    topic_text: str
    personal_message: str | None
    context_snapshot: dict[str, Any]
    recommendation_id: str | None
    expires_at: datetime
    responded_at: datetime | None
    created_at: datetime


class MatchResponse(ApiModel):
    id: str
    other_user: dict[str, str]
    status: str
    created_at: datetime


class ConversationCueResponse(ApiModel):
    id: str
    cue_type: str
    text: str
    status: str
    created_by: str
    created_at: datetime


class ConversationResponse(BaseModel):
    id: str
    match_id: str
    other_user: dict[str, str]
    status: str
    context_snapshot: dict[str, Any]
    active_cue: ConversationCueResponse | None
    opened_at: datetime
    last_message_at: datetime | None
    unread_count: int
    created_at: datetime


class ConversationCloseRequest(BaseModel):
    reason: Literal["not_a_fit", "taking_a_break", "boundary", "other"] = "other"


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    client_message_id: str = Field(min_length=1, max_length=64)
    kind: Literal["text", "cue_response"] = "text"
    reply_to_id: str | None = None

    @field_validator("body")
    @classmethod
    def normalize_body(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("消息不能为空")
        return value


class MessageResponse(ApiModel):
    id: str
    conversation_id: str
    sender_id: str
    body: str
    client_message_id: str
    kind: str
    reply_to_id: str | None
    created_at: datetime
    read_at: datetime | None


class MessagePage(BaseModel):
    items: list[MessageResponse]
    next_cursor: str | None = None


class BlockCreate(BaseModel):
    blocked_user_id: str
    reason_private: str | None = Field(default=None, max_length=300)


class BlockResponse(ApiModel):
    id: str
    blocked_user: dict[str, str]
    created_at: datetime
    revoked_at: datetime | None


class NotificationResponse(ApiModel):
    id: str
    kind: str
    entity_type: str
    entity_id: str
    state: str
    scheduled_at: datetime
    delivered_at: datetime | None
    read_at: datetime | None
    created_at: datetime


class OutcomeCreate(BaseModel):
    candidate_id: str
    match_id: str | None = None
    window_days: Literal[7, 14, 30]
    satisfaction: Literal["positive", "neutral", "negative"]
    growth_alignment: Literal["positive", "neutral", "negative"] | None = None
    boundary_respect: Literal["positive", "neutral", "negative"] | None = None
    continued_contact: bool
    safety_event: bool = False


class OutcomeResponse(ApiModel):
    id: str
    candidate_id: str
    window_days: int
    satisfaction: str
    growth_alignment: str | None
    boundary_respect: str | None
    continued_contact: bool
    good_outcome: bool
    submitted_at: datetime


class SafetyReportCreate(BaseModel):
    subject_id: str
    conversation_id: str | None = None
    message_id: str | None = None
    event_type: Literal["harassment", "boundary_violation", "fraud", "other"]
    severity: Literal["low", "medium", "high", "critical"]
    details: str | None = Field(default=None, max_length=1000)


class SafetyEventResponse(ApiModel):
    id: str
    reporter_id: str
    subject_id: str
    conversation_id: str | None
    message_id: str | None
    event_type: str
    severity: str
    status: str
    created_at: datetime
    reviewed_at: datetime | None


class AdminSafetyUpdate(BaseModel):
    status: Literal["confirmed", "dismissed"]
    review_note: str | None = Field(default=None, max_length=300)


class MessageEnvelope(BaseModel):
    code: str
    message: str
    trace_id: str
    details: Any | None = None
