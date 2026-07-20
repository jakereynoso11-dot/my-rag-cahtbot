from typing import Any, Dict, List, Optional

from langchain_core.documents import Document
from supabase.client import Client
from langchain_openai import OpenAIEmbeddings

from app.core.config import settings


class RetrievalService:
    def __init__(self, supabase: Client, embeddings: OpenAIEmbeddings):
        self.supabase = supabase
        self.embeddings = embeddings

    def similarity_search(
        self,
        query: str,
        k: int,
        filter: Optional[Dict[str, Any]] = None,
        match_threshold: Optional[float] = None,
    ) -> List[Document]:
        query_embedding = self.embeddings.embed_query(query)

        payload: Dict[str, Any] = {
            "query_embedding": query_embedding,
            "match_count": k,
            "filter": filter or {},
        }

        if match_threshold is not None:
            payload["match_threshold"] = match_threshold

        resp = self.supabase.rpc(settings.supabase_match_fn, payload).execute()
        rows = resp.data or []

        return [
            Document(
                page_content=r.get("content") or "",
                metadata={
                    **(r.get("metadata") or {}),
                    "_id": r.get("id"),
                    "_similarity": r.get("similarity"),
                },
            )
            for r in rows
        ]