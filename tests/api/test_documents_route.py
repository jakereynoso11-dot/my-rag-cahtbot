from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_powabase_client
from app.api.routes.documents import router as documents_router

app = FastAPI()
app.include_router(documents_router)
client = TestClient(app)


class FakePowabaseClient:
    def __init__(self, items):
        self._items = items

    async def list_kb_sources(self, kb_id):
        return {"items": self._items, "total": len(self._items)}


def teardown_function():
    app.dependency_overrides.pop(get_powabase_client, None)


def test_list_documents_returns_items():
    items = [{"id": "idx-1", "index_status": "indexed"}]
    app.dependency_overrides[get_powabase_client] = lambda: FakePowabaseClient(items)

    response = client.get("/documents")

    assert response.status_code == 200
    assert response.json() == items


def test_list_documents_empty():
    app.dependency_overrides[get_powabase_client] = lambda: FakePowabaseClient([])

    response = client.get("/documents")

    assert response.status_code == 200
    assert response.json() == []
