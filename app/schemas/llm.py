from pydantic import BaseModel, Field


class SetLLMConfigRequest(BaseModel):
    provider: str = Field(min_length=1)
    api_key: str = Field(min_length=1)
    model: str | None = None


class LLMConfigOut(BaseModel):
    configured: bool
    provider: str | None = None
    model: str | None = None


class ListModelsRequest(BaseModel):
    provider: str = Field(min_length=1)
    api_key: str = Field(min_length=1)


class ModelListOut(BaseModel):
    models: list[str]
