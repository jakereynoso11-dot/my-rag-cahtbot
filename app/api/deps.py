from typing import Optional

import httpx
from fastapi import Depends, Header, HTTPException

from app.clients.postgrest_client import PostgrestClient
from app.clients.powabase_client import PowabaseClient
from app.core.config import settings


def get_powabase_client() -> PowabaseClient:
    return PowabaseClient(settings.powabase_base_url, settings.powabase_api_key)


def get_postgrest_client() -> PostgrestClient:
    return PostgrestClient(settings.powabase_base_url, settings.powabase_api_key)


def get_bearer_token(authorization: Optional[str] = Header(None)) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401, detail="Missing or malformed Authorization header"
        )
    return token


async def get_current_user(
    access_token: str = Depends(get_bearer_token),
    powabase: PowabaseClient = Depends(get_powabase_client),
) -> dict:
    try:
        return await powabase.get_user(access_token)
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
