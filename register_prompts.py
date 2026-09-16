#!/usr/bin/env python3
"""Register Arbiter's prompt templates in the MLflow Prompt Registry.

Can be run standalone or called from the app lifespan. Only creates a new
version when the template text has actually changed.
"""

import mlflow.genai

from app.prompts import (
    ANALYZE_SYSTEM_PROMPT,
    ANALYZE_USER_TEMPLATE,
    GENERATE_SYSTEM_PROMPT,
    GENERATE_USER_TEMPLATE,
    REVIEW_SYSTEM_PROMPT,
    REVIEW_USER_TEMPLATE,
)

PROMPTS = [
    {
        "name": "arbiter-analyze-system",
        "template": ANALYZE_SYSTEM_PROMPT,
        "tags": {"step": "analyze", "role": "system"},
    },
    {
        "name": "arbiter-analyze-user",
        "template": ANALYZE_USER_TEMPLATE,
        "tags": {"step": "analyze", "role": "user"},
    },
    {
        "name": "arbiter-generate-system",
        "template": GENERATE_SYSTEM_PROMPT,
        "tags": {"step": "generate", "role": "system"},
    },
    {
        "name": "arbiter-generate-user",
        "template": GENERATE_USER_TEMPLATE,
        "tags": {"step": "generate", "role": "user"},
    },
    {
        "name": "arbiter-review-system",
        "template": REVIEW_SYSTEM_PROMPT,
        "tags": {"step": "review", "role": "system"},
    },
    {
        "name": "arbiter-review-user",
        "template": REVIEW_USER_TEMPLATE,
        "tags": {"step": "review", "role": "user"},
    },
]


def register_prompts(commit_message: str | None = None):
    for prompt in PROMPTS:
        existing = mlflow.genai.load_prompt(
            prompt["name"], allow_missing=True
        )
        if existing and existing.template == prompt["template"]:
            continue
        mlflow.genai.register_prompt(
            commit_message=commit_message, **prompt
        )


if __name__ == "__main__":
    import sys
    from config import setup_mlflow

    setup_mlflow()
    msg = sys.argv[1] if len(sys.argv) > 1 else None
    register_prompts(commit_message=msg)

    registered = mlflow.genai.search_prompts()
    print(f"Prompt registry ({len(registered)} prompts):")
    for p in registered:
        print(f"  - {p.name}")
