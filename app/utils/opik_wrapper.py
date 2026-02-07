"""Small wrappers around Opik to keep instrumentation consistent.

We keep these helpers best-effort and guarded behind Settings so observability
never breaks runtime logic when Opik is disabled or misconfigured.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.config import settings


def store_prompt(
    *,
    name: str,
    prompt: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Store a prompt in Opik using `opik.Prompt`.

    Best-effort: never raises. No-op when Opik is disabled.
    """
    if not settings.OPIK_ENABLED:
        return
    if not prompt or not isinstance(prompt, str):
        return
    if not name or not isinstance(name, str):
        return

    try:
        import opik

        opik.Prompt(name=name, prompt=prompt, metadata=metadata or None)
    except Exception:
        # Avoid breaking core logic if Opik is unavailable.
        return

