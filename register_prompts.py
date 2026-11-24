#!/usr/bin/env python3
"""Register Arbiter's prompt templates in the MLflow Prompt Registry.

Only creates a new version when the template text changed. Optionally points
an alias (e.g. ``staging``/``production``) at the resulting version.

    python register_prompts.py [--message "why"] [--alias staging]
"""

from __future__ import annotations

import argparse

import mlflow.genai

from app.prompt_store import ROLES, STEPS, code_prompt, prompt_name


def _prompts() -> list[dict]:
    out = []
    for step in STEPS:
        for role in ROLES:
            out.append(
                {
                    "name": prompt_name(step, role),
                    "template": code_prompt(step, role).template,
                    "tags": {"app": "arbiter", "step": step, "role": role},
                }
            )
    return out


PROMPTS = _prompts()


def register_prompts(commit_message: str | None = None, alias: str | None = None) -> dict[str, int]:
    """Register/refresh all 6 prompts. Returns {name: version}."""
    versions: dict[str, int] = {}
    for prompt in PROMPTS:
        existing = mlflow.genai.load_prompt(f"prompts:/{prompt['name']}@latest", allow_missing=True)
        if existing is not None and existing.template == prompt["template"]:
            version = int(existing.version)
        else:
            pv = mlflow.genai.register_prompt(
                name=prompt["name"],
                template=prompt["template"],
                commit_message=commit_message,
                tags=prompt["tags"],
            )
            version = int(pv.version)
        if alias:
            mlflow.genai.set_prompt_alias(prompt["name"], alias=alias, version=version)
        versions[prompt["name"]] = version
    return versions


def main() -> None:
    from config import setup_mlflow

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message", "-m", default=None, help="commit message for new versions")
    parser.add_argument("--alias", "-a", default=None, help="alias to point at the versions")
    args = parser.parse_args()

    setup_mlflow()
    versions = register_prompts(commit_message=args.message, alias=args.alias)
    for name, version in versions.items():
        suffix = f" (alias {args.alias})" if args.alias else ""
        print(f"  {name}: v{version}{suffix}")


if __name__ == "__main__":
    main()
