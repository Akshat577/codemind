"""Seed a team's Hindsight bank with a few standards and decisions for the demo.

Usage: python -m scripts.seed_memory [team]
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from app.memory import TeamMemory, make_client  # noqa: E402

RULES = [
    ("rule", "Money is always an integer number of paise. Never use floats for amounts."),
    ("rule", "Never use a bare `except:`. Catch specific exceptions and log with the `logger`, never `print`."),
    ("rule", "Every outbound HTTP call must set an explicit timeout."),
    ("decision", "All payment gateway calls go through `PaymentClient` in payments/client.py; do not call requests directly."),
    ("decision", "We intentionally do not use type hints in legacy scripts under scripts/; do not suggest adding them there."),
]

if __name__ == "__main__":
    team = sys.argv[1] if len(sys.argv) > 1 else "demo-team"
    mem = TeamMemory(make_client(), team)
    for kind, rule in RULES:
        mem.add_rule(rule, author="tech-lead", kind=kind)
        print(f"remembered [{kind}] {rule}")
    print(f"seeded bank {mem.bank_id}")
