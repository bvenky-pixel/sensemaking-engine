"""
Magic-link email delivery -- one small, swappable function rather than
a provider SDK threaded through the rest of src/api/.

No provider is wired up until `RESEND_API_KEY` is actually set (see
fly.toml/deploy.yml for how that gets there in production, via `fly
secrets set`, never committed). Until then -- every local dev run, and
every test -- `send_magic_link_email` just logs the link to stdout,
same "no paid/external calls unless explicitly configured" discipline
this codebase already applies to LLM calls in tests (see
src/llm/providers.py). This means a login can always be completed
locally by reading the server's own console output or, in tests, by
reading the pending token straight out of SQLite (src/api/db.py's
`magic_links` table) -- neither needs a real inbox.
"""

from __future__ import annotations

import os

import requests

RESEND_API_URL = "https://api.resend.com/emails"

# Resend's own shared sending domain -- works with no domain
# verification step, which matters for an MVP that hasn't set one up
# yet. Swap for a verified from-address on the app's own domain once
# one exists; nothing else about this function needs to change.
_DEFAULT_FROM = "Confidant <onboarding@resend.dev>"


def send_magic_link_email(email: str, link: str) -> None:
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        print(f"[dev] Magic link for {email}: {link}")
        return

    requests.post(
        RESEND_API_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "from": os.environ.get("CONFIDANT_EMAIL_FROM", _DEFAULT_FROM),
            "to": [email],
            "subject": "Your Confidant login link",
            "html": (
                f'<p>Tap the link below to log in to Confidant.</p>'
                f'<p><a href="{link}">{link}</a></p>'
                f'<p>This link expires in 15 minutes and only works once.'
                f" If you didn't request it, you can ignore this email.</p>"
            ),
        },
        timeout=10,
    )
