from __future__ import annotations

from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
RecommendedScene = Literal["general", "reasoning", "fallback"]


def _validate_base_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Invalid base_url")
    return value


class AdminModelConfigCreateRequest(BaseModel):
    name: NonEmptyString
    recommended_scene: RecommendedScene | None = None
    recommended_usage: NonEmptyString | None = None
    base_url: NonEmptyString
    api_key: NonEmptyString
    model: NonEmptyString
    enabled: bool = True

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        return _validate_base_url(value)


class AdminModelConfigUpdateRequest(BaseModel):
    name: NonEmptyString | None = None
    recommended_scene: RecommendedScene | None = None
    recommended_usage: NonEmptyString | None = None
    base_url: NonEmptyString | None = None
    api_key: NonEmptyString | None = None
    model: NonEmptyString | None = None
    enabled: bool | None = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_base_url(value)


class ModelConfigAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    recommended_scene: RecommendedScene | None = None
    recommended_usage: str | None = None
    base_url: str
    api_key: str
    model: str
    enabled: bool
    created_at: object
    updated_at: object


class AdminModelConfigListResponse(BaseModel):
    items: list[ModelConfigAdminResponse] = Field(default_factory=list)


class ModelConfigEnabledResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    model: str


class EnabledModelConfigListResponse(BaseModel):
    items: list[ModelConfigEnabledResponse] = Field(default_factory=list)
