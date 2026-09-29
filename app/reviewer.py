"""LLM reviewer: turns code + recalled team memory into structured suggestions."""

from __future__ import annotations

import json
import os
import re
import uuid

from groq import Groq

from .memory import Memory

SYSTEM_PROMPT = """You are CodeMind, a senior code reviewer embedded in one specific team.
You review a single file and return precise, actionable suggestions.

You are given TEAM MEMORY recalled from previous reviews. Treat it as authoritative:
- Team rules and architectural decisions override generic best practices.
- If the team previously REJECTED a kind of suggestion, do not make it again
  (unless the code is a genuine security or correctness bug). List what you
  deliberately skipped in "skipped_due_to_memory".
- If the author has a recurring mistake that appears again, say so explicitly
  (e.g. "Recurring for <author>: ...") and raise the severity by one level.
- When a suggestion is driven by memory, quote the memory briefly in "memory_basis".
  Otherwise set "memory_basis" to null.
Do not invent memories. Do not pad with trivial nits.

Respond with ONLY a JSON object of this shape:
{
  "summary": "one or two sentences",
  "suggestions": [
    {
      "title": "short imperative title",
      "severity": "critical" | "major" | "minor" | "nit",
      "category": "security" | "bug" | "performance" | "style" | "naming" | "architecture" | "testing" | "error-handling" | "other",
      "line": <int or null>,
      "explanation": "why this matters for this team",
      "suggested_fix": "concrete code or instruction",
      "memory_basis": "the memory that drove this, or null",
      "recurring": true | false
    }
  ],
  "skipped_due_to_memory": ["suggestion you would normally make but the team rejected before"]
}"""


def _format_memories(memories: list[Memory]) -> str:
    if not memories:
        return "(no team memory yet - this team has never been reviewed before)"
    return "\n".join(
        f"- [{', '.join(t for t in m.tags if t.startswith(('kind:', 'verdict:'))) or m.type}] {m.text}"
        for m in memories
    )


def _number_lines(code: str) -> str:
    return "\n".join(f"{i:>4} | {line}" for i, line in enumerate(code.splitlines(), 1))


def _parse_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


class Reviewer:
    def __init__(self, client: Groq | None = None, model: str | None = None):
        self.client = client or Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    def review(self, *, code: str, language: str, filename: str, author: str,
               memories: list[Memory]) -> dict:
        user_prompt = (
            f"TEAM MEMORY (recalled from Hindsight):\n{_format_memories(memories)}\n\n"
            f"AUTHOR: {author}\nFILE: {filename}\nLANGUAGE: {language}\n\n"
            f"CODE:\n{_number_lines(code)}"
        )
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": user_prompt}],
        )
        data = _parse_json(resp.choices[0].message.content or "{}")
        suggestions = []
        for s in data.get("suggestions") or []:
            if not isinstance(s, dict) or not s.get("title"):
                continue
            s["id"] = uuid.uuid4().hex[:10]
            s.setdefault("severity", "minor")
            s.setdefault("category", "other")
            s.setdefault("memory_basis", None)
            s.setdefault("recurring", False)
            suggestions.append(s)
        return {
            "summary": data.get("summary", ""),
            "suggestions": suggestions,
            "skipped_due_to_memory": data.get("skipped_due_to_memory") or [],
        }
