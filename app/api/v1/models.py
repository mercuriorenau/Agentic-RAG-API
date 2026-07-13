from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.models import ModelOptionResponse, ModelsResponse
from app.services.llm.model_selector import list_available_models

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=ModelsResponse)
async def get_available_models() -> ModelsResponse:
    settings = get_settings()
    options = list_available_models(settings)
    return ModelsResponse(
        models=[
            ModelOptionResponse(
                id=option.id,
                label=option.label,
                mode=option.mode,
                provider=option.provider,
                model_name=option.model_name,
            )
            for option in options
        ]
    )
