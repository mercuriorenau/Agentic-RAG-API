from pydantic import BaseModel


class ModelOptionResponse(BaseModel):
    id: str
    label: str
    mode: str
    provider: str | None = None
    model_name: str | None = None


class ModelsResponse(BaseModel):
    models: list[ModelOptionResponse]
