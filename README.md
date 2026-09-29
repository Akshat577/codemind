# 🧠 CodeMind — code review that remembers your team

CodeMind is an AI code reviewer with long-term memory. It learns your team's coding standards, architectural decisions, recurring mistakes and, most importantly, **which suggestions you rejected and why**, so the next review is personal to your team instead of generic.

Memory is powered by [Hindsight](https://github.com/vectorize-io/hindsight), and the reviews come from an LLM on [Groq](https://console.groq.com).

```
Code submit ──▶ Recall team memory (Hindsight) ──▶ LLM review ──▶ Suggestions
                     ▲                                                │
                     │                                                ▼
                     └────────── Retain verdict + reason ◀──── Accept / Reject
```

## Why memory matters here

Generic AI reviewers make the same suggestions every time. If your team decided that legacy scripts don't get type hints, you still see "add type hints" on every PR. CodeMind closes the loop:

| Without memory | With CodeMind |
|---|---|
| Suggests things your team already rejected | Skips them and tells you it skipped them |
| Doesn't know your conventions (e.g. "money is integer paise") | Enforces rules you taught it and cites them |
| Treats every mistake as the first time | Flags *recurring* mistakes per developer and raises severity |
| Review quality depends on who reviews | Consistent, because team knowledge is in one memory bank |

## How Hindsight is used

One Hindsight **memory bank per team** (`codemind-<team>`), created with a mission that tells Hindsight what to extract. See [app/memory.py](app/memory.py).

| Hindsight op | When | What |
|---|---|---|
| `create_bank` | first use of a team | mission + retain mission focused on standards, rejections, recurring mistakes |
| `recall` | before every review | two queries: (1) team rules, decisions and past feedback relevant to this file, (2) the author's own history, filtered by `author:<name>` tag |
| `retain` | on every Accept/Reject | the suggestion, verdict, reason, author, file, tagged `kind:feedback`, `verdict:*`, `author:*`, `category:*` |
| `retain` | on Accept | a `kind:mistake` fact attributing the mistake to the author, so recurring patterns emerge |
| `retain` | "Teach a rule" | `kind:rule` / `kind:decision` team standards |
| `reflect` | "Team insights" | synthesises the team's review profile from everything retained |
| `list_memories` | memory panel | shows the bank's contents live |

The recalled memories are placed in the reviewer prompt ([app/reviewer.py](app/reviewer.py)) with explicit rules: team memory overrides generic best practices, previously rejected suggestions are skipped and listed in `skipped_due_to_memory`, recurring mistakes are called out, and every memory-driven suggestion quotes its `memory_basis` so you can see *why*.

## Quick start

```bash
git clone https://github.com/Akshat577/codemind.git
cd codemind
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # add GROQ_API_KEY and HINDSIGHT_API_KEY
python -m scripts.seed_memory demo-team   # optional: a few team rules for the demo
uvicorn app.main:app --reload
```

Open http://localhost:8000.

**Keys**
- Groq: free key at https://console.groq.com/keys
- Hindsight Cloud: sign up at https://ui.hindsight.vectorize.io/signup and create an API key.

**Self-hosted Hindsight instead of Cloud**

```bash
docker run -it --pull always --name hindsight -p 8888:8888 -p 9999:9999 \
  -e HINDSIGHT_API_LLM_API_KEY=$OPENAI_API_KEY \
  -v hindsight-data:/home/hindsight/.pg0 ghcr.io/vectorize-io/hindsight:latest
```
Then set `HINDSIGHT_BASE_URL=http://localhost:8888` in `.env`.

## 60-second demo

1. Load the **payments** demo snippet and click **Review** with memory **off**. You get generic suggestions.
2. Turn memory **on** and review again. Suggestions now cite the team rules (integer paise, no bare `except`, `PaymentClient`).
3. **Reject** a suggestion you disagree with, giving a reason, and **Accept** the float-money one.
4. Load the **refunds** snippet (same author, same mistakes) and review. The rejected suggestion is gone and listed under *Skipped because your team rejected it before*. The float-money issue is flagged as **recurring for ravi**.
5. Click **What has CodeMind learned about this team?** Hindsight `reflect` summarises the team's profile.

## API

| Method | Path | Body |
|---|---|---|
| POST | `/api/review` | `{team, author, filename, language, code, use_memory}` |
| POST | `/api/verdict` | `{review_id, suggestion_id, accepted, reason, reviewer}` |
| POST | `/api/rules` | `{team, rule, author, kind: "rule" \| "decision"}` |
| POST | `/api/insights` | `{team, question?}` |
| GET | `/api/memories?team=` | |

## Project layout

```
app/
  main.py        FastAPI routes
  memory.py      Hindsight integration (banks, recall, retain, reflect)
  reviewer.py    Groq LLM reviewer + prompt
  static/        single-page UI
scripts/seed_memory.py
tests/test_flow.py   end-to-end loop test with fake Hindsight + LLM
```

## Tests

```bash
pytest -q
```

The main test demonstrates the learning loop: review, reject "add type hints", review again, and the suggestion is gone and reported as skipped.

## Links

- Hindsight: https://github.com/vectorize-io/hindsight
- Hindsight docs: https://hindsight.vectorize.io/
- What is agent memory: https://vectorize.io/what-is-agent-memory
