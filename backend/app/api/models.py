from fastapi import APIRouter
from typing import List, Dict

from app.services.ai_service import get_model_options

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/")
def list_models() -> List[Dict[str, str]]:
    """Return available built-in model options."""
    models = get_model_options()
    return [
        {"id": model_id, "label": label, "provider": model_id.split("/")[0]}
        for model_id, label in models
    ]
