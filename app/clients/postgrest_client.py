from typing import Any, Optional

import httpx


class PostgrestClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self, access_token: str) -> dict:
        return {
            "apikey": self.api_key,
            "Authorization": f"Bearer {access_token}",
        }

    async def rpc(self, function_name: str, payload: dict, *, access_token: str) -> Any:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/rest/v1/rpc/{function_name}",
                headers=self._headers(access_token),
                json=payload,
            )
        resp.raise_for_status()
        return resp.json()

    async def select_one(
        self, table: str, filters: dict, columns: str, *, access_token: str
    ) -> Optional[dict]:
        params = {"select": columns, "limit": "1"}
        for key, value in filters.items():
            params[key] = f"eq.{value}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/rest/v1/{table}",
                headers=self._headers(access_token),
                params=params,
            )
        resp.raise_for_status()
        rows = resp.json()
        return rows[0] if rows else None

    async def update(
        self, table: str, filters: dict, values: dict, *, access_token: str
    ) -> list:
        params = {}
        for key, value in filters.items():
            params[key] = f"eq.{value}"

        headers = self._headers(access_token)
        headers["Prefer"] = "return=representation"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.patch(
                f"{self.base_url}/rest/v1/{table}",
                headers=headers,
                params=params,
                json=values,
            )
        resp.raise_for_status()
        return resp.json()
