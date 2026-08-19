from app.services.specialist_management import Specialist
from app.services.specialist_routing import choose_specialist

BILLING = Specialist(id="s1", name="Billing Agent", specialty="billing", agent_id="agent-billing")
TAX = Specialist(id="s2", name="Tax Agent", specialty="taxes", agent_id="agent-tax")


class FakePowabaseClient:
    def __init__(self, reply="NONE", raise_error=False):
        self.reply = reply
        self.raise_error = raise_error
        self.calls = []

    async def stream_agent_run(
        self,
        agent_id,
        message,
        session_id=None,
        temperature=None,
        runtime_knowledge_bases=None,
    ):
        self.calls.append((agent_id, message, session_id, runtime_knowledge_bases))
        if self.raise_error:
            raise RuntimeError("boom")
        yield f'data: {{"event": "complete", "status": "completed", "content": "{self.reply}"}}'


async def test_choose_specialist_returns_none_with_no_specialists():
    powabase = FakePowabaseClient()

    result = await choose_specialist("hi", [], "router-agent", powabase)

    assert result is None
    assert powabase.calls == []


async def test_choose_specialist_skips_classification_with_one_specialist():
    powabase = FakePowabaseClient()

    result = await choose_specialist("hi", [BILLING], "router-agent", powabase)

    assert result is BILLING
    assert powabase.calls == []


async def test_choose_specialist_matches_exact_name():
    powabase = FakePowabaseClient(reply="Tax Agent")

    result = await choose_specialist("how do I file", [BILLING, TAX], "router-agent", powabase)

    assert result is TAX
    assert powabase.calls[0][0] == "router-agent"
    assert powabase.calls[0][2] is None


async def test_choose_specialist_matches_name_wrapped_in_sentence():
    powabase = FakePowabaseClient(reply="I'd pick the Billing Agent for this one")

    result = await choose_specialist("invoice question", [BILLING, TAX], "router-agent", powabase)

    assert result is BILLING


async def test_choose_specialist_returns_none_when_router_says_none():
    powabase = FakePowabaseClient(reply="NONE")

    result = await choose_specialist("random question", [BILLING, TAX], "router-agent", powabase)

    assert result is None


async def test_choose_specialist_falls_back_to_none_on_error():
    powabase = FakePowabaseClient(raise_error=True)

    result = await choose_specialist("hi", [BILLING, TAX], "router-agent", powabase)

    assert result is None


async def test_choose_specialist_passes_runtime_knowledge_bases_for_specialists_with_docs():
    powabase = FakePowabaseClient(reply="Billing Agent")

    result = await choose_specialist(
        "what's my late fee",
        [BILLING, TAX],
        "router-agent",
        powabase,
        specialist_kb_ids={"s1": ["kb-billing-1", "kb-billing-2"]},
    )

    assert result is BILLING
    runtime_kbs = powabase.calls[0][3]
    assert runtime_kbs == [
        {"id": "kb-billing-1", "top_k": 3},
        {"id": "kb-billing-2", "top_k": 3},
    ]
    assert "has attached documents" in powabase.calls[0][1]


async def test_choose_specialist_omits_runtime_knowledge_bases_when_no_specialist_has_docs():
    powabase = FakePowabaseClient(reply="NONE")

    await choose_specialist(
        "random question", [BILLING, TAX], "router-agent", powabase, specialist_kb_ids={}
    )

    assert powabase.calls[0][3] is None


async def test_choose_specialist_caps_runtime_knowledge_bases_at_ten():
    powabase = FakePowabaseClient(reply="Billing Agent")
    many_kbs = [f"kb-{i}" for i in range(15)]

    await choose_specialist(
        "question",
        [BILLING, TAX],
        "router-agent",
        powabase,
        specialist_kb_ids={"s1": many_kbs},
    )

    assert len(powabase.calls[0][3]) == 10
