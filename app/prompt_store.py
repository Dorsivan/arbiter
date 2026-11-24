"""Resolve Arbiter's prompts from the MLflow Prompt Registry (with code fallback).

Prompt names: ``arbiter-{analyze,generate,review}-{system,user}``.

Environment:
    ARBITER_PROMPT_SOURCE     "registry" (default) or "code"
    ARBITER_PROMPT_ALIAS      alias to load, default "production"
    ARBITER_PROMPT_CACHE_TTL  seconds to cache a resolved prompt, default 30

When the registry is unreachable or the prompt/alias is missing, the code
constants in ``app.prompts`` are used and a warning is logged, so the app keeps
working (``LoadedPrompt.source == "code"``).
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from dataclasses import dataclass

from app import prompts as code_prompts

logger = logging.getLogger(__name__)

STEPS = ("analyze", "generate", "review")
ROLES = ("system", "user")

_CODE_CONSTANTS = {
    ("analyze", "system"): "ANALYZE_SYSTEM_PROMPT",
    ("analyze", "user"): "ANALYZE_USER_TEMPLATE",
    ("generate", "system"): "GENERATE_SYSTEM_PROMPT",
    ("generate", "user"): "GENERATE_USER_TEMPLATE",
    ("review", "system"): "REVIEW_SYSTEM_PROMPT",
    ("review", "user"): "REVIEW_USER_TEMPLATE",
}

_VAR_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def prompt_name(step: str, role: str) -> str:
    return f"arbiter-{step}-{role}"


def render(template: str, **variables) -> str:
    """Replace ``{{ var }}`` / ``{{var}}`` placeholders (MLflow syntax)."""

    def _sub(match: re.Match) -> str:
        key = match.group(1)
        if key not in variables:
            raise KeyError(f"Missing prompt variable: {key}")
        return str(variables[key])

    return _VAR_RE.sub(_sub, template)


@dataclass(frozen=True)
class LoadedPrompt:
    name: str
    template: str
    version: int | None
    uri: str | None
    source: str  # "registry" | "code"

    def format(self, **variables) -> str:
        return render(self.template, **variables)


def _settings() -> tuple[str, str, float]:
    source = os.environ.get("ARBITER_PROMPT_SOURCE", "registry").strip().lower()
    alias = os.environ.get("ARBITER_PROMPT_ALIAS", "production").strip()
    ttl = float(os.environ.get("ARBITER_PROMPT_CACHE_TTL", "30"))
    return source, alias, ttl


_cache: dict[tuple[str, str, str], tuple[float, LoadedPrompt]] = {}
_lock = threading.Lock()


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def code_prompt(step: str, role: str) -> LoadedPrompt:
    const = _CODE_CONSTANTS[(step, role)]
    return LoadedPrompt(
        name=prompt_name(step, role),
        template=getattr(code_prompts, const),
        version=None,
        uri=None,
        source="code",
    )


def _load_from_registry(step: str, role: str, alias: str) -> LoadedPrompt | None:
    import mlflow.genai

    name = prompt_name(step, role)
    uri = f"prompts:/{name}@{alias}"
    try:
        pv = mlflow.genai.load_prompt(uri)
    except Exception as exc:  # missing prompt/alias, server unreachable, ...
        logger.warning("Prompt %s not loaded from registry (%s); using code fallback", uri, exc)
        return None
    if pv is None:
        return None
    return LoadedPrompt(
        name=name,
        template=pv.template,
        version=int(pv.version) if pv.version is not None else None,
        uri=uri,
        source="registry",
    )


def get_prompt(step: str, role: str) -> LoadedPrompt:
    if (step, role) not in _CODE_CONSTANTS:
        raise ValueError(f"Unknown prompt {step}/{role}")
    source, alias, ttl = _settings()
    if source == "code":
        return code_prompt(step, role)

    key = (step, role, alias)
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]

    loaded = _load_from_registry(step, role, alias) or code_prompt(step, role)
    with _lock:
        _cache[key] = (now, loaded)
    return loaded


def resolved_prompts() -> dict[str, dict]:
    """All 6 prompts as currently resolved (used by GET /prompts and trace tags)."""
    _, alias, _ = _settings()
    out = {}
    for step in STEPS:
        for role in ROLES:
            p = get_prompt(step, role)
            out[p.name] = {"version": p.version, "source": p.source, "uri": p.uri, "alias": alias}
    return out
