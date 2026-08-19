from pydantic import BaseModel


class GenerateRequest(BaseModel):
    description: str
    repo_url: str | None = None
    namespace: str = "default"
    replicas: int = 2


class ResourcePlan(BaseModel):
    app_name: str
    app_type: str
    resources: list[str]
    reasoning: str


class ReviewResult(BaseModel):
    issues: list[str]
    corrections_applied: list[str]
    security_notes: list[str]
    final_manifests: str


class GenerateResponse(BaseModel):
    app_name: str
    resource_plan: ResourcePlan
    raw_manifests: str
    review: ReviewResult
    final_manifests: str
    trace_id: str | None = None
