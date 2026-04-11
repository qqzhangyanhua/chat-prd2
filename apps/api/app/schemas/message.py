from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MessageCreateRequest(BaseModel):
    content: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)


class MessageRegenerateRequest(BaseModel):
    model_config_id: str = Field(min_length=1)


class MessageAcceptedEventData(BaseModel):
    message_id: str
    session_id: str


class ReplyGroupCreatedEventData(BaseModel):
    reply_group_id: str
    user_message_id: str
    session_id: str
    is_regeneration: bool
    is_latest: bool


class AssistantVersionStartedEventData(BaseModel):
    session_id: str
    user_message_id: str
    reply_group_id: str
    assistant_version_id: str
    version_no: int
    assistant_message_id: str | None = None
    model_config_id: str
    is_regeneration: bool
    is_latest: bool


class AssistantDeltaEventData(BaseModel):
    session_id: str
    user_message_id: str
    reply_group_id: str
    assistant_version_id: str
    version_no: int
    assistant_message_id: str | None = None
    model_config_id: str
    delta: str
    is_regeneration: bool
    is_latest: bool


class AssistantDoneEventData(BaseModel):
    session_id: str
    user_message_id: str
    reply_group_id: str
    assistant_version_id: str
    version_id: str
    version_no: int
    assistant_message_id: str
    model_config_id: str
    prd_snapshot_version: int
    is_regeneration: bool
    is_latest: bool


class PrdUpdatedEventData(BaseModel):
    sections: dict
    meta: dict | None = None


class ConversationMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: str
    content: str
    message_type: str
    reply_group_id: str | None = None
    version_no: int | None = None
    is_latest: bool | None = None


class AssistantReplyVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reply_group_id: str
    session_id: str
    user_message_id: str
    version_no: int
    content: str
    action_snapshot: dict
    model_meta: dict
    state_version_id: str | None
    prd_snapshot_version: int | None
    created_at: object
    is_latest: bool = False


class AssistantReplyGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    user_message_id: str
    latest_version_id: str | None
    created_at: object
    updated_at: object
    versions: list[AssistantReplyVersionResponse] = Field(default_factory=list)


class AgentTurnDecisionSectionResponse(BaseModel):
    key: str
    title: str
    content: str
    meta: dict = Field(default_factory=dict)


class AgentTurnDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    user_message_id: str
    phase: str
    phase_goal: str | None
    understanding_summary: str
    assumptions_json: list[dict]
    risk_flags_json: list[str]
    next_move: str
    suggestions_json: list[dict]
    recommendation_json: dict | None
    needs_confirmation_json: list[str]
    confidence: str
    state_patch_json: dict
    prd_patch_json: dict
    created_at: object
    decision_summary: str = ""
    decision_sections: list[AgentTurnDecisionSectionResponse] = Field(default_factory=list)
