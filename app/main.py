"""CodeMind API: code review that remembers your team, powered by Hindsight."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()

from .memory import TeamMemory, make_client  # noqa: E402
from .reviewer import Reviewer  # noqa: E402

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="CodeMind", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.exception_handler(Exception)
async def upstream_error(request: Request, exc: Exception):
    # Most failures here are Hindsight/Groq connectivity or missing API keys.
    return JSONResponse(status_code=502, content={
        "detail": f"{type(exc).__name__}: {str(exc)[:300]} (check HINDSIGHT_* and GROQ_* in .env)"})

_state: dict = {"hindsight": None, "reviewer": None, "teams": {}, "reviews": {}}


def hindsight():
    if _state["hindsight"] is None:
        _state["hindsight"] = make_client()
    return _state["hindsight"]


def reviewer() -> Reviewer:
    if _state["reviewer"] is None:
        _state["reviewer"] = Reviewer()
    return _state["reviewer"]


def team_memory(team: str) -> TeamMemory:
    if team not in _state["teams"]:
        _state["teams"][team] = TeamMemory(hindsight(), team)
    return _state["teams"][team]


# ---- schemas ---------------------------------------------------------------------

class ReviewRequest(BaseModel):
    team: str = "demo-team"
    author: str = "anonymous"
    filename: str = "snippet.py"
    language: str = "python"
    code: str = Field(min_length=1, max_length=40_000)
    use_memory: bool = True


class VerdictRequest(BaseModel):
    review_id: str
    suggestion_id: str
    accepted: bool
    reason: str = ""
    reviewer: str = "reviewer"


class RuleRequest(BaseModel):
    team: str = "demo-team"
    rule: str = Field(min_length=3, max_length=2000)
    author: str = "team"
    kind: str = "rule"


class InsightRequest(BaseModel):
    team: str = "demo-team"
    question: str | None = None


# ---- routes ----------------------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.post("/api/review")
def review(req: ReviewRequest):
    mem = team_memory(req.team)
    t0 = time.perf_counter()
    memories = mem.recall_for_review(req.code, req.language, req.author,
                                     req.filename) if req.use_memory else []
    recall_ms = int((time.perf_counter() - t0) * 1000)

    t1 = time.perf_counter()
    try:
        result = reviewer().review(code=req.code, language=req.language,
                                   filename=req.filename, author=req.author,
                                   memories=memories)
    except Exception as e:  # surface LLM/config errors to the UI
        raise HTTPException(502, f"LLM review failed: {e}") from e
    review_ms = int((time.perf_counter() - t1) * 1000)

    review_id = uuid.uuid4().hex[:12]
    _state["reviews"][review_id] = {"request": req.model_dump(), **result}
    return {
        "review_id": review_id,
        **result,
        "memories_used": [m.as_dict() for m in memories],
        "used_memory": req.use_memory,
        "timing_ms": {"recall": recall_ms, "review": review_ms},
    }


@app.post("/api/verdict")
def verdict(req: VerdictRequest):
    stored = _state["reviews"].get(req.review_id)
    if not stored:
        raise HTTPException(404, "Unknown review (server restarted?) - run the review again")
    suggestion = next((s for s in stored["suggestions"] if s["id"] == req.suggestion_id), None)
    if not suggestion:
        raise HTTPException(404, "Unknown suggestion")
    r = stored["request"]
    team_memory(r["team"]).record_verdict(
        suggestion=suggestion, accepted=req.accepted, reason=req.reason,
        author=r["author"], reviewer=req.reviewer, filename=r["filename"],
        language=r["language"],
    )
    suggestion["verdict"] = "accepted" if req.accepted else "rejected"
    return {"ok": True, "saved_to_bank": team_memory(r["team"]).bank_id}


@app.post("/api/rules")
def add_rule(req: RuleRequest):
    mem = team_memory(req.team)
    mem.add_rule(req.rule, author=req.author, kind=req.kind)
    return {"ok": True, "bank_id": mem.bank_id}


@app.post("/api/insights")
def insights(req: InsightRequest):
    return {"insights": team_memory(req.team).insights(req.question)}


@app.get("/api/memories")
def memories(team: str = "demo-team", limit: int = 50):
    mem = team_memory(team)
    return {"bank_id": mem.bank_id, "memories": mem.list_all(limit)}


@app.get("/api/health")
def health():
    return {"ok": True}
