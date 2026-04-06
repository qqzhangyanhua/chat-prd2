from pydantic import BaseModel, ConfigDict, Field


class AdminModelConfigCreateRequest(BaseModel):
    name: str
    base_url: str
    api_key: str
    model: str
    enabled: bool = True


class AdminModelConfigUpdateRequest(BaseModel):
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    enabled: bool | None = None


class ModelConfigAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
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
