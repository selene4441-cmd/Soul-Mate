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


class InvitationRequest(BaseModel):
    candidate_id: str
    message: str | None = Field(default=None, max_length=300)


class MatchResponse(ApiModel):
    id: str
    other_user: dict[str, str]
    status: str
    created_at: datetime


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    client_message_id: str = Field(min_length=1, max_length=64)


class MessageResponse(ApiModel):
    id: str
    conversation_id: str
    sender_id: str
    body: str
    client_message_id: str
    created_at: datetime
    read_at: datetime | None


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
    event_type: Literal["harassment", "boundary_violation", "fraud", "other"]
    severity: Literal["low", "medium", "high", "critical"]
    details: str | None = Field(default=None, max_length=1000)


class SafetyEventResponse(ApiModel):
    id: str
    reporter_id: str
    subject_id: str
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
