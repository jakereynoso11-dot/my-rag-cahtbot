import json
from typing import Optional

from app.clients.powabase_client import PowabaseClient
from app.services.specialist_management import Specialist

__all__ = ["choose_specialist"]

_ROUTER_SYSTEM_PROMPT = (
    "You are a routing classifier for a team of specialist assistants. "
    "Given a user's message and a list of specialists (each with a name "
    "and area of focus), decide which single specialist, if any, is the "
    "best fit to answer it. Respond with ONLY the specialist's name exactly "
    "as given, or the word NONE if no specialist is clearly a better fit "
    "than a general assistant. Do not explain your choice."
)


def _build_routing_message(query: str, specialists: list[Specialist]) -> str:
    roster = "\n".join(f"- {s.name}: {s.specialty}" for s in specialists)
    return f"Specialists:\n{roster}\n\nUser message: {query}"


async def choose_specialist(
    query: str,
    specialists: list[Specialist],
    router_agent_id: str,
    powabase: PowabaseClient,
) -> Optional[Specialist]:
    """Ask a lightweight, session-less classification run which specialist
    (if any) should handle this message. Falls back to no specialist
    (the parent chatbot answers) on any ambiguity or failure — routing is a
    nice-to-have, never something that should block a chat response."""
    if not specialists:
        return None
    if len(specialists) == 1:
        return specialists[0]

    reply = ""
    try:
        async for line in powabase.stream_agent_run(
            router_agent_id,
            message=(
                f"{_ROUTER_SYSTEM_PROMPT}\n\n"
                f"{_build_routing_message(query, specialists)}"
            ),
            session_id=None,
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
