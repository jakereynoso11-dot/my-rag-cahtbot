import json
from typing import Optional

from app.clients.powabase_client import PowabaseClient
from app.services.specialist_management import Specialist

__all__ = ["choose_specialist"]

# Powabase caps runtime_knowledge_bases at 10 entries per run/stream call.
_MAX_RUNTIME_KNOWLEDGE_BASES = 10

_ROUTER_SYSTEM_PROMPT = (
    "You are a routing classifier for a team of specialist assistants. "
    "Given a user's message and a list of specialists (each with a name "
    "and area of focus), decide which single specialist, if any, is the "
    "best fit to answer it. Some specialists have their own reference "
    "documents attached -- when a specialist has documents, use "
    "knowledge_search to check whether they actually contain content "
    "relevant to the user's message before deciding; a specialist whose "
    "documents cover the topic is a stronger match than one that merely "
    "has a plausible-sounding specialty description. Respond with ONLY the "
    "specialist's name exactly as given, or the word NONE if no specialist "
    "is clearly a better fit than a general assistant. Do not explain your "
    "choice."
)


def _build_routing_message(
    query: str, specialists: list[Specialist], specialist_kb_ids: dict[str, list[str]]
) -> str:
    lines = []
    for s in specialists:
        has_docs = " (has attached documents you can search)" if specialist_kb_ids.get(s.id) else ""
        lines.append(f"- {s.name}: {s.specialty}{has_docs}")
    roster = "\n".join(lines)
    return f"Specialists:\n{roster}\n\nUser message: {query}"


def _build_runtime_knowledge_bases(
    specialists: list[Specialist], specialist_kb_ids: dict[str, list[str]]
) -> list:
    seen = set()
    entries = []
    for specialist in specialists:
        for kb_id in specialist_kb_ids.get(specialist.id, []):
            if kb_id in seen:
                continue
            seen.add(kb_id)
            entries.append({"id": kb_id, "top_k": 3})
            if len(entries) >= _MAX_RUNTIME_KNOWLEDGE_BASES:
                return entries
    return entries


async def choose_specialist(
    query: str,
    specialists: list[Specialist],
    router_agent_id: str,
    powabase: PowabaseClient,
    specialist_kb_ids: Optional[dict[str, list[str]]] = None,
) -> Optional[Specialist]:
    """Ask a lightweight, session-less classification run which specialist
    (if any) should handle this message. When specialists have their own
    documents (specialist_kb_ids), those knowledge bases are made
    request-scoped-searchable for this one run via runtime_knowledge_bases,
    so the classifier can check actual document content instead of just
    matching against a hand-written specialty description. Falls back to no
    specialist (the parent chatbot answers) on any ambiguity or failure --
    routing is a nice-to-have, never something that should block a chat
    response."""
    if not specialists:
        return None
    if len(specialists) == 1:
        return specialists[0]

    specialist_kb_ids = specialist_kb_ids or {}
    runtime_knowledge_bases = _build_runtime_knowledge_bases(specialists, specialist_kb_ids)

    reply = ""
    try:
        async for line in powabase.stream_agent_run(
            router_agent_id,
            message=(
                f"{_ROUTER_SYSTEM_PROMPT}\n\n"
                f"{_build_routing_message(query, specialists, specialist_kb_ids)}"
            ),
            session_id=None,
            runtime_knowledge_bases=runtime_knowledge_bases or None,
        ):
            if not line.startswith("data: "):
                continue
            payload = json.loads(line[len("data: "):])
            if payload.get("event") == "complete" and payload.get("status") == "completed":
                reply = (payload.get("content") or "").strip()
    except Exception:
        return None

    reply_normalized = reply.strip().strip(".").lower()
    if reply_normalized in ("", "none"):
        return None

    for specialist in specialists:
        if specialist.name.strip().lower() == reply_normalized:
            return specialist
    # Loose fallback: model sometimes wraps the name in a short sentence.
    for specialist in specialists:
        if specialist.name.strip().lower() in reply.lower():
            return specialist
    return None
