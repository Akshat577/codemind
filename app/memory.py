"""Hindsight memory layer for CodeMind.

Everything the reviewer "knows" about a team lives in one Hindsight memory bank
per team. We write four kinds of memories, distinguished by tags:

  kind:rule      - a coding standard the team explicitly taught the agent
  kind:feedback  - a suggestion the team accepted or rejected (and why)
  kind:mistake   - an accepted issue, attributed to the author who made it
  kind:decision  - an architectural decision recorded by the team

Before each review we recall from the bank; after each human verdict we retain.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from hindsight_client import Hindsight

BANK_MISSION = (
    "You are the long-term memory of a code review assistant for a software team. "
    "Remember the team's coding standards, architectural decisions, which review "
    "suggestions they accepted or rejected and why, and the recurring mistakes each "
    "developer makes, so future reviews are consistent and personalised."
)

RETAIN_MISSION = (
    "Extract durable facts about coding conventions, review preferences, rejected "
    "suggestions and the reasons, recurring mistakes per developer, and architectural "
    "decisions. Ignore one-off details about a specific snippet unless they reveal a "
    "preference or a pattern."
)


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "default"


@dataclass
class Memory:
    id: str
    text: str
    type: str | None = None
    tags: list[str] = field(default_factory=list)
    context: str | None = None

    def as_dict(self) -> dict:
        return {"id": self.id, "text": self.text, "type": self.type,
                "tags": self.tags, "context": self.context}


class TeamMemory:
    """Thin wrapper around a Hindsight bank scoped to one team."""

    def __init__(self, client: Hindsight, team: str):
        self.client = client
        self.team = team
        self.bank_id = f"codemind-{slug(team)}"
        self._ensured = False

    # ---- setup -----------------------------------------------------------------

    def ensure_bank(self) -> None:
        if self._ensured:
            return
        try:
            self.client.create_bank(
                bank_id=self.bank_id,
                name=f"CodeMind - {self.team}",
                mission=BANK_MISSION,
                retain_mission=RETAIN_MISSION,
            )
        except Exception:
            # Bank already exists (or the server auto-creates banks on first retain).
            pass
        self._ensured = True

    # ---- recall ----------------------------------------------------------------

    def recall_for_review(self, code: str, language: str, author: str,
                          filename: str) -> list[Memory]:
        """Pull everything relevant to reviewing this snippet.

        Two queries: one for team-wide rules and past feedback on this kind of
        code, one scoped to the author's own history of mistakes.
        """
        self.ensure_bank()
        snippet = code[:1500]
        team_query = (
            f"Team coding standards, architectural decisions and past review feedback "
            f"(accepted or rejected suggestions) relevant to this {language} file "
            f"{filename}:\n{snippet}"
        )
        author_query = f"Recurring mistakes and review history of developer {author}"

        seen: dict[str, Memory] = {}
        for query, tags in ((team_query, None), (author_query, [f"author:{slug(author)}"])):
            try:
                resp = self.client.recall(bank_id=self.bank_id, query=query,
                                          max_tokens=2048, budget="mid", tags=tags)
            except Exception:
                continue
            for r in resp.results or []:
                if r.id not in seen:
                    seen[r.id] = Memory(id=r.id, text=r.text, type=r.type,
                                        tags=list(r.tags or []), context=r.context)
        return list(seen.values())

    # ---- retain ----------------------------------------------------------------

    def _retain(self, content: str, context: str, tags: list[str],
                metadata: dict[str, str] | None = None) -> None:
        self.ensure_bank()
        self.client.retain(
            bank_id=self.bank_id,
            content=content,
            context=context,
            tags=tags,
            metadata=metadata or {},
            timestamp=datetime.now(timezone.utc),
        )

    def add_rule(self, rule: str, author: str = "team", kind: str = "rule") -> None:
        kind = kind if kind in {"rule", "decision"} else "rule"
        label = "coding standard" if kind == "rule" else "architectural decision"
        self._retain(
            content=f"Team {label} (added by {author}): {rule}",
            context=f"team {label}",
            tags=[f"kind:{kind}", f"author:{slug(author)}"],
        )

    def record_verdict(self, *, suggestion: dict, accepted: bool, reason: str,
                       author: str, reviewer: str, filename: str,
                       language: str) -> None:
        verdict = "ACCEPTED" if accepted else "REJECTED"
        title = suggestion.get("title", "")
        category = suggestion.get("category", "general")
        lines = [
            f"Code review suggestion {verdict} by {reviewer} on {author}'s {language} "
            f"file {filename}.",
            f"Suggestion ({category}, {suggestion.get('severity', 'minor')}): {title}.",
            f"Details: {suggestion.get('explanation', '')}",
        ]
        if reason:
            lines.append(f"Reason given: {reason}")
        if accepted:
            lines.append(
                f"The team agrees with this kind of feedback; keep flagging '{category}' "
                f"issues like this. {author} made this mistake."
            )
        else:
            lines.append(
                f"The team does NOT want this kind of suggestion; do not repeat "
                f"'{title}' in future reviews unless the code is clearly dangerous."
            )
        tags = ["kind:feedback", f"verdict:{verdict.lower()}", f"author:{slug(author)}",
                f"lang:{slug(language)}", f"category:{slug(category)}"]
        self._retain("\n".join(lines), context="code review verdict", tags=tags,
                     metadata={"filename": filename, "reviewer": reviewer})

        if accepted:
            self._retain(
                content=(f"Developer {author} made a {category} mistake in {filename}: "
                         f"{title}."),
                context="recurring developer mistake",
                tags=["kind:mistake", f"author:{slug(author)}", f"category:{slug(category)}"],
            )

    # ---- reflect / browse ------------------------------------------------------

    def insights(self, question: str | None = None) -> str:
        self.ensure_bank()
        q = question or (
            "Summarise this team's code review profile: the coding standards they "
            "enforce, architectural decisions, the kinds of suggestions they reject, "
            "and each developer's recurring mistakes. Use short bullet points."
        )
        return self.client.reflect(bank_id=self.bank_id, query=q, budget="mid").text

    def list_all(self, limit: int = 50) -> list[dict]:
        self.ensure_bank()
        resp = self.client.list_memories(bank_id=self.bank_id, limit=limit)
        return [
            {"id": m.id, "text": m.text, "type": m.fact_type, "tags": m.tags or [],
             "date": str(m.mentioned_at or m.var_date or "")}
            for m in (resp.items or [])
        ]


def make_client() -> Hindsight:
    base_url = os.getenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
    return Hindsight(base_url=base_url, api_key=os.getenv("HINDSIGHT_API_KEY") or None)
