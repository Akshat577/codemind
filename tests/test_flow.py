"""End-to-end flow test with in-memory fakes for Hindsight and Groq.

Proves the loop: review -> reject -> memory -> next review sees the rejection.
"""

import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import main
from app.memory import TeamMemory
from app.reviewer import Reviewer


class FakeHindsight:
    def __init__(self):
        self.banks: dict[str, list] = {}

    def create_bank(self, bank_id, **kw):
        self.banks.setdefault(bank_id, [])

    def retain(self, bank_id, content, context=None, tags=None, metadata=None, timestamp=None):
        mems = self.banks.setdefault(bank_id, [])
        mems.append(SimpleNamespace(id=f"m{len(mems)}", text=content, type="world",
                                    tags=tags or [], context=context, fact_type="world",
                                    mentioned_at=timestamp, var_date=None))

    def recall(self, bank_id, query, tags=None, **kw):
        mems = self.banks.get(bank_id, [])
        if tags:
            mems = [m for m in mems if set(tags) & set(m.tags)]
        return SimpleNamespace(results=mems)

    def reflect(self, bank_id, query, **kw):
        return SimpleNamespace(text=f"{len(self.banks.get(bank_id, []))} memories")

    def list_memories(self, bank_id, limit=100):
        return SimpleNamespace(items=self.banks.get(bank_id, [])[:limit])


class FakeGroq:
    """Suggests type hints unless memory says the team rejected them."""

    def __init__(self):
        self.prompts = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, messages, **kw):
        prompt = messages[-1]["content"]
        self.prompts.append(prompt)
        rejected = "REJECTED" in prompt and "type hints" in prompt
        body = {
            "summary": "ok",
            "suggestions": [{"title": "Use integer paise for money", "severity": "major",
                             "category": "bug", "line": 4, "explanation": "floats",
                             "suggested_fix": "int", "memory_basis": None, "recurring": False}]
            + ([] if rejected else [{"title": "Add type hints", "severity": "nit",
                                     "category": "style", "line": 1, "explanation": "x",
                                     "suggested_fix": "x", "memory_basis": None,
                                     "recurring": False}]),
            "skipped_due_to_memory": ["Add type hints"] if rejected else [],
        }
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(body)))])


def setup():
    fake_h, fake_g = FakeHindsight(), FakeGroq()
    main._state.update(hindsight=fake_h, reviewer=Reviewer(client=fake_g, model="fake"),
                       teams={}, reviews={})
    return TestClient(main.app), fake_h, fake_g


def test_rejected_suggestion_is_not_repeated():
    client, fake_h, fake_g = setup()
    payload = {"team": "t", "author": "ravi", "filename": "a.py", "code": "def f(x):\n  return x*1.18"}

    r1 = client.post("/api/review", json=payload).json()
    titles = [s["title"] for s in r1["suggestions"]]
    assert "Add type hints" in titles and r1["memories_used"] == []

    hints = next(s for s in r1["suggestions"] if s["title"] == "Add type hints")
    money = next(s for s in r1["suggestions"] if s["title"] != "Add type hints")
    assert client.post("/api/verdict", json={"review_id": r1["review_id"], "suggestion_id": hints["id"],
                                             "accepted": False, "reason": "we don't use type hints"}).json()["ok"]
    client.post("/api/verdict", json={"review_id": r1["review_id"], "suggestion_id": money["id"],
                                      "accepted": True})

    bank = fake_h.banks["codemind-t"]
    assert any("REJECTED" in m.text and "verdict:rejected" in m.tags for m in bank)
    assert any("kind:mistake" in m.tags and "author:ravi" in m.tags for m in bank)

    r2 = client.post("/api/review", json=payload).json()
    assert [s["title"] for s in r2["suggestions"]] == ["Use integer paise for money"]
    assert r2["skipped_due_to_memory"] == ["Add type hints"]
    assert len(r2["memories_used"]) >= 2


def test_memory_toggle_off_skips_recall():
    client, fake_h, fake_g = setup()
    client.post("/api/rules", json={"team": "t", "rule": "No floats for money"})
    r = client.post("/api/review", json={"team": "t", "code": "x = 1", "use_memory": False}).json()
    assert r["memories_used"] == [] and "no team memory yet" in fake_g.prompts[-1]


def test_rules_insights_and_listing():
    client, fake_h, _ = setup()
    client.post("/api/rules", json={"team": "t", "rule": "Use PaymentClient", "kind": "decision"})
    mems = client.get("/api/memories?team=t").json()
    assert mems["bank_id"] == "codemind-t" and "kind:decision" in mems["memories"][0]["tags"]
    assert client.post("/api/insights", json={"team": "t"}).json()["insights"] == "1 memories"


def test_bank_id_slug():
    assert TeamMemory(FakeHindsight(), "Payments Team!").bank_id == "codemind-payments-team"
