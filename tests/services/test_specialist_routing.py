from app.services.specialist_management import Specialist
from app.services.specialist_routing import choose_specialist

BILLING = Specialist(id="s1", name="Billing Agent", specialty="billing", agent_id="agent-billing")
TAX = Specialist(id="s2", name="Tax Agent", specialty="taxes", agent_id="agent-tax")


class FakePowabaseClient:
    def __init__(self, reply="NONE", raise_error=False):
        self.reply = reply
        self.raise_error = raise_error
        self.calls = []

    async def stream_agent_run(self, agent_id, message, session_id=None, temperature=None):
        self.calls.append((agent_id, message, session_id))
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
