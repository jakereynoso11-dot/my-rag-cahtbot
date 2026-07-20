from typing import List

from openai import OpenAI
from langchain_core.documents import Document


class ChatService:
    def __init__(self, openai_client: OpenAI):
        self.client = openai_client

    def _build_messages(self, user_query: str, docs: List[Document]) -> List[dict]:
        context = "\n\n---\n\n".join(d.page_content for d in docs if d.page_content)

        system_content = (
            "You are a helpful assistant. Use the provided context to answer. "
            "If the context is insufficient, say so."
        )

        user_content = (
            f"User question:\n{user_query}\n\n"
            f"Context (retrieved):\n{context}"
        )

        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

    def answer(
        self,
        query: str,
        retrieved_docs: List[Document],
        model: str,
        max_output_tokens: int,
        temperature: float,
    ) -> str:
        messages = self._build_messages(query, retrieved_docs)

        resp = self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_output_tokens,
            temperature=temperature,
        )

        return resp.choices[0].message.content