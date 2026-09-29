# My Code Reviewer Kept Suggesting Things We'd Already Said No To

*Publish on Medium / Dev.to / Hashnode. Add the screenshots marked [IMAGE] before publishing.*

---

Picture the third time an AI reviewer tells your team to "consider adding type hints" to a legacy script you explicitly decided to leave alone. By then, nobody is reading its comments. That's the real failure mode of AI code review. The suggestions aren't wrong, exactly. The reviewer just has no idea what your team already decided. Every pull request is its first day on the job.

Human reviewers aren't like that. A good senior engineer remembers that you store money as integer paise, that the team argued about `PaymentClient` and settled it, and that a particular teammate has a habit of writing bare `except:` blocks. That memory is most of what makes their review worth having.

So I built **CodeMind**, a code reviewer that keeps that memory. It recalls what the team has taught it before every review, and it writes down every accept and reject decision afterwards. The memory layer is [Hindsight](https://github.com/vectorize-io/hindsight), an open-source agent memory system from Vectorize.

## The problem, concretely

Here's a small example from a payments service:

```python
def charge(user, amount):
    total = amount * 1.18  # add GST
    try:
        r = requests.post("https://pay.example.com/charge",
                          json={"user": user.id, "amount": total})
        return r.json()
    except:
        print("payment failed")
        return None
```

A stateless LLM reviewer gives you a reasonable but generic list: catch specific exceptions, add a timeout, maybe add type hints, maybe add a docstring. That list comes back identical tomorrow, and the day after, no matter how many of those items your team has already dismissed.

It also misses what actually matters to *this* team:

- Money must be integer paise. `amount * 1.18` is a float, so this is a correctness bug for us, not a style nit.
- Payment calls must go through `PaymentClient`, not `requests` directly.
- This is the second time this month the same developer wrote a bare `except:`.

None of that is in the code. It's in the team's history.

## The loop

CodeMind's flow is short:

```
Code submit → Recall team memory → LLM review → Suggestions → Accept / Reject → Retain
```

[IMAGE: architecture diagram of the loop]

The important part is the arrow at the end. Every human decision gets written back to memory along with its reason, and the next review reads it.

## One memory bank per team

Each team gets its own Hindsight bank. When it's created, I give Hindsight a *mission* describing what's worth remembering, which shapes how it extracts facts from what I retain:

```python
self.client.create_bank(
    bank_id=self.bank_id,                     # e.g. "codemind-payments"
    name=f"CodeMind - {self.team}",
    mission=BANK_MISSION,
    retain_mission=(
        "Extract durable facts about coding conventions, review preferences, "
        "rejected suggestions and the reasons, recurring mistakes per developer, "
        "and architectural decisions. Ignore one-off details about a specific "
        "snippet unless they reveal a preference or a pattern."
    ),
)
```

The retain mission matters. Without it, the bank could fill with trivia like "line 4 multiplies amount by 1.18". With it, the fact worth keeping is "the team treats float money as a bug".

## Writing memories: verdicts, not reviews

The obvious approach is to retain the whole review output. I deliberately didn't. The model's own suggestions aren't knowledge. The *team's reaction* to them is. So CodeMind retains only three things:

1. **Rules and decisions** the team teaches it directly.
2. **Verdicts**: every accept or reject, with the reason.
3. **Mistakes**: each accepted issue, attributed to the author.

```python
def record_verdict(self, *, suggestion, accepted, reason, author, reviewer,
                   filename, language):
    verdict = "ACCEPTED" if accepted else "REJECTED"
    lines = [
        f"Code review suggestion {verdict} by {reviewer} on {author}'s "
        f"{language} file {filename}.",
        f"Suggestion ({suggestion['category']}): {suggestion['title']}.",
    ]
    if reason:
        lines.append(f"Reason given: {reason}")
    ...
    self._retain("\n".join(lines), context="code review verdict",
                 tags=["kind:feedback", f"verdict:{verdict.lower()}",
                       f"author:{slug(author)}", f"category:{slug(category)}"])
```

Tags are what make this work. Hindsight lets you filter recall by tag, so "everything about Ravi" is just a tag filter rather than a hope that semantic search finds it.

## Reading memories: two recalls per review

Before the LLM sees any code, CodeMind runs two recalls:

```python
team_query = (f"Team coding standards, architectural decisions and past review "
              f"feedback relevant to this {language} file {filename}:\n{snippet}")
author_query = f"Recurring mistakes and review history of developer {author}"

for query, tags in ((team_query, None), (author_query, [f"author:{slug(author)}"])):
    resp = self.client.recall(bank_id=self.bank_id, query=query,
                              max_tokens=2048, budget="mid", tags=tags)
```

The first is semantic. The snippet itself is part of the query, so payment code pulls up payment rules. The second is scoped to the author by tag. With a single combined query, the author's personal history would compete with team-wide rules for the same token budget. Two queries keep both in view.

## Making the model actually use memory

Putting memories in the prompt isn't enough. The model has to be told what they *mean*. The system prompt spells out the rules:

- Team rules override generic best practice.
- A previously **rejected** suggestion must not be repeated (unless it's a real security or correctness bug), and must be listed in `skipped_due_to_memory`.
- A recurring mistake is called out by name and bumped one severity level.
- Any memory-driven suggestion must quote the memory in `memory_basis`.

That last rule is about trust. When CodeMind says "use integer paise", the UI shows the memory behind it right under the suggestion. You can see the reviewer isn't making things up. It's repeating what your tech lead said.

[IMAGE: suggestion card showing the 🧠 memory_basis line]

## Before and after

Same author, a second file with the same habits:

```python
def refund(order):
    amount = order.total * 0.9
    try:
        resp = requests.post("https://pay.example.com/refund", ...)
        return resp.json()
    except:
        print("refund failed")
```

**With memory off:** a generic list, including suggestions the team had already rejected.

**With memory on**, after one round of accept/reject on the earlier file:

- "Use integer paise for money" is **major** and marked *recurring for ravi*, with the team rule quoted.
- "Route through `PaymentClient`" cites the architecture decision.
- The suggestion rejected last time is gone. It appears under *Skipped because your team rejected it before* instead.

[IMAGE: side-by-side screenshots of memory off vs memory on]

I made that "skipped" list explicit on purpose. Silently dropping a suggestion feels like the tool is hiding something. Saying "I didn't suggest X because you told me not to" feels like working with a colleague.

## Asking the memory what it knows

Hindsight's `reflect` reasons over the whole bank instead of just retrieving from it. CodeMind uses it for a "team insights" button:

```python
self.client.reflect(
    bank_id=self.bank_id,
    query="Summarise this team's code review profile: standards they enforce, "
          "architectural decisions, suggestions they reject, and each "
          "developer's recurring mistakes.",
    budget="mid",
)
```

It doubles as an onboarding document. A new engineer can read what the team cares about, drawn from real review decisions rather than a style guide nobody updates.

## Lessons learned

- **Store reactions, not outputs.** The value is in what humans accepted and rejected. The LLM's own text is noise.
- **Always ask for a reason on reject.** "Rejected" alone is weak signal. "Rejected: legacy scripts are frozen" generalises to future files.
- **Use tags for anything you'll filter on.** Semantic recall is great for "what's relevant to this code". Tags are better for "what about this person".
- **Show the memory.** Citing `memory_basis` on every suggestion is what made the reviewer trustworthy rather than creepy.
- **Keep the loop tight.** Retaining synchronously on every click means the very next review already knows. That's what makes the behaviour change visible.

## Try it

The code is on GitHub: **https://github.com/Akshat577/codemind**. It's FastAPI, a single-page UI, Groq for the LLM and Hindsight for memory. It runs against Hindsight Cloud or a local Docker instance.

- Hindsight: https://github.com/vectorize-io/hindsight
- Hindsight docs: https://hindsight.vectorize.io/
- What is agent memory: https://vectorize.io/what-is-agent-memory

A reviewer that forgets everything between pull requests will always sound like a linter with better grammar. One that remembers starts to sound like your team.
