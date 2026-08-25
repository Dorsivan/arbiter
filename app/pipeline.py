import json
import os
import re

import anthropic
import mlflow
from openai import OpenAI

from app.models import GenerateRequest, GenerateResponse, ResourcePlan, ReviewResult
from app.prompts import (
    ANALYZE_SYSTEM_PROMPT,
    ANALYZE_USER_TEMPLATE,
    GENERATE_SYSTEM_PROMPT,
    GENERATE_USER_TEMPLATE,
    REVIEW_SYSTEM_PROMPT,
    REVIEW_USER_TEMPLATE,
)

LLM_BACKEND = os.environ.get("LLM_BACKEND", "openai")
MODEL_NAME = os.environ.get("MODEL_NAME", "")

_openai_client: OpenAI | None = None
_anthropic_client: anthropic.Anthropic | None = None


def get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(
            base_url=os.environ.get("OPENAI_API_BASE", "http://localhost:8000/v1"),
            api_key=os.environ.get("OPENAI_API_KEY", "EMPTY"),
        )
    return _openai_client


def get_anthropic_client() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


def _chat(system: str, user: str, json_mode: bool = False) -> str:
    if LLM_BACKEND == "anthropic":
        client = get_anthropic_client()
        model = MODEL_NAME or "claude-opus-4-6"
        response = client.messages.create(
            model=model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=0.2,
        )
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""
    else:
        client = get_openai_client()
        kwargs = dict(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""


def _extract_json(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


@mlflow.trace(name="analyze", span_type="LLM")
def analyze(
    description: str, repo_url: str | None, namespace: str
) -> ResourcePlan:
    repo_line = f"GitHub repository: {repo_url}\n" if repo_url else ""
    user_msg = ANALYZE_USER_TEMPLATE.format(
        description=description, repo_line=repo_line, namespace=namespace
    )
    raw = _chat(ANALYZE_SYSTEM_PROMPT, user_msg, json_mode=True)
    data = _extract_json(raw)
    return ResourcePlan(**data)


@mlflow.trace(name="generate", span_type="LLM")
def generate(
    resource_plan: ResourcePlan, description: str, namespace: str, replicas: int
) -> str:
    user_msg = GENERATE_USER_TEMPLATE.format(
        app_name=resource_plan.app_name,
        app_type=resource_plan.app_type,
        description=description,
        namespace=namespace,
        replicas=replicas,
        resources=", ".join(resource_plan.resources),
        reasoning=resource_plan.reasoning,
    )
    return _chat(GENERATE_SYSTEM_PROMPT, user_msg)


@mlflow.trace(name="review", span_type="LLM")
def review(manifests: str, resource_plan: ResourcePlan) -> ReviewResult:
    user_msg = REVIEW_USER_TEMPLATE.format(
        expected_resources=", ".join(resource_plan.resources),
        manifests=manifests,
    )
    raw = _chat(REVIEW_SYSTEM_PROMPT, user_msg, json_mode=True)
    data = _extract_json(raw)
    return ReviewResult(**data)


@mlflow.trace(name="k8s_manifest_pipeline", span_type="CHAIN")
def run_pipeline(request: GenerateRequest) -> GenerateResponse:
    resource_plan = analyze(request.description, request.repo_url, request.namespace)
    raw_manifests = generate(
        resource_plan, request.description, request.namespace, request.replicas
    )
    review_result = review(raw_manifests, resource_plan)

    trace = mlflow.get_last_active_trace()
    trace_id = trace.info.request_id if trace else None

    return GenerateResponse(
        app_name=resource_plan.app_name,
        resource_plan=resource_plan,
        raw_manifests=raw_manifests,
        review=review_result,
        final_manifests=review_result.final_manifests,
        trace_id=trace_id,
    )
