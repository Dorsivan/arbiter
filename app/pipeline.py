import json
import os
import re

import anthropic
from openai import OpenAI
from opentelemetry import trace

from app.models import GenerateRequest, GenerateResponse, ResourcePlan, ReviewResult
from app.prompts import (
    ANALYZE_SYSTEM_PROMPT,
    ANALYZE_USER_TEMPLATE,
    GENERATE_SYSTEM_PROMPT,
    GENERATE_USER_TEMPLATE,
    REVIEW_SYSTEM_PROMPT,
    REVIEW_USER_TEMPLATE,
)

tracer = trace.get_tracer("arbiter")

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


def _chat(system: str, user: str, span_name: str = "chat") -> str:
    with tracer.start_as_current_span(span_name, attributes={
        "gen_ai.system": LLM_BACKEND,
        "gen_ai.request.model": MODEL_NAME or "claude-opus-4-6",
    }) as span:
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
            span.set_attribute("gen_ai.usage.input_tokens", response.usage.input_tokens)
            span.set_attribute("gen_ai.usage.output_tokens", response.usage.output_tokens)
            for block in response.content:
                if block.type == "text":
                    return block.text
            return ""
        else:
            client = get_openai_client()
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
            )
            if response.usage:
                span.set_attribute("gen_ai.usage.input_tokens", response.usage.prompt_tokens)
                span.set_attribute("gen_ai.usage.output_tokens", response.usage.completion_tokens)
            return response.choices[0].message.content or ""


def _extract_json(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def analyze(
    description: str, repo_url: str | None, namespace: str
) -> ResourcePlan:
    with tracer.start_as_current_span("analyze"):
        repo_line = f"GitHub repository: {repo_url}\n" if repo_url else ""
        user_msg = ANALYZE_USER_TEMPLATE.format(
            description=description, repo_line=repo_line, namespace=namespace
        )
        raw = _chat(ANALYZE_SYSTEM_PROMPT, user_msg, "analyze_llm_call")
        data = _extract_json(raw)
        return ResourcePlan(**data)


def generate(
    resource_plan: ResourcePlan, description: str, namespace: str, replicas: int
) -> str:
    with tracer.start_as_current_span("generate"):
        user_msg = GENERATE_USER_TEMPLATE.format(
            app_name=resource_plan.app_name,
            app_type=resource_plan.app_type,
            description=description,
            namespace=namespace,
            replicas=replicas,
            resources=", ".join(resource_plan.resources),
            reasoning=resource_plan.reasoning,
        )
        return _chat(GENERATE_SYSTEM_PROMPT, user_msg, "generate_llm_call")


def review(manifests: str, resource_plan: ResourcePlan) -> ReviewResult:
    with tracer.start_as_current_span("review"):
        user_msg = REVIEW_USER_TEMPLATE.format(
            expected_resources=", ".join(resource_plan.resources),
            manifests=manifests,
        )
        raw = _chat(REVIEW_SYSTEM_PROMPT, user_msg, "review_llm_call")
        data = _extract_json(raw)
        return ReviewResult(**data)


def run_pipeline(request: GenerateRequest) -> GenerateResponse:
    with tracer.start_as_current_span("k8s_manifest_pipeline") as pipeline_span:
        resource_plan = analyze(request.description, request.repo_url, request.namespace)
        raw_manifests = generate(
            resource_plan, request.description, request.namespace, request.replicas
        )
        review_result = review(raw_manifests, resource_plan)

        trace_id = format(pipeline_span.get_span_context().trace_id, "032x")

        return GenerateResponse(
            app_name=resource_plan.app_name,
            resource_plan=resource_plan,
            raw_manifests=raw_manifests,
            review=review_result,
            final_manifests=review_result.final_manifests,
            trace_id=trace_id,
        )
