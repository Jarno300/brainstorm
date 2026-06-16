from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.provider_setting import ProviderSetting
from app.api.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/settings", tags=["settings"])


class ProviderSettingsResponse(BaseModel):
    provider: str
    api_key: str  # masked on read
    base_url: str
    has_api_key: bool

    class Config:
        from_attributes = True


class ProviderSettingsUpdate(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None


def _mask_key(key: str) -> str:
    """Show only last 4 characters of an API key."""
    if not key:
        return ""
    if len(key) <= 4:
        return "****"
    return "****" + key[-4:]


@router.get("/{provider}", response_model=ProviderSettingsResponse)
def get_provider_settings(provider: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get stored settings for a provider. API key is masked in the response."""
    setting = db.query(ProviderSetting).filter(
        ProviderSetting.provider == provider.lower()
    ).first()

    if not setting:
        return ProviderSettingsResponse(
            provider=provider.lower(),
            api_key="",
            base_url="",
            has_api_key=False,
        )

    return ProviderSettingsResponse(
        provider=setting.provider,
        api_key=_mask_key(setting.api_key),
        base_url=setting.base_url,
        has_api_key=bool(setting.api_key),
    )


@router.put("/{provider}", response_model=ProviderSettingsResponse)
def upsert_provider_settings(
    provider: str,
    data: ProviderSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update provider settings. Only non-None fields are updated."""
    provider = provider.lower()
    setting = db.query(ProviderSetting).filter(
        ProviderSetting.provider == provider
    ).first()

    if not setting:
        setting = ProviderSetting(provider=provider)
        db.add(setting)

    if data.api_key is not None:
        setting.api_key = data.api_key
    if data.base_url is not None:
        setting.base_url = data.base_url

    db.commit()
    db.refresh(setting)

    return ProviderSettingsResponse(
        provider=setting.provider,
        api_key=_mask_key(setting.api_key),
        base_url=setting.base_url,
        has_api_key=bool(setting.api_key),
    )
