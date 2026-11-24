import os
from contextlib import asynccontextmanager

import mlflow
import mlflow.openai
from fastapi import FastAPI

from app.models import GenerateRequest, GenerateResponse
from app.pipeline import run_pipeline
from app.prompt_store import clear_cache, resolved_prompts
from config import setup_mlflow


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_mlflow()
    backend = os.environ.get("LLM_BACKEND", "openai")
    if backend == "anthropic":
        import mlflow.anthropic

        mlflow.anthropic.autolog()
    else:
        mlflow.openai.autolog()
    if os.environ.get("ARBITER_REGISTER_PROMPTS_ON_START", "false").lower() == "true":
        from register_prompts import register_prompts

        register_prompts(commit_message="Registered on arbiter startup")
    yield


app = FastAPI(title="Arbiter", version="0.2.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/prompts")
def prompts(refresh: bool = False):
    """Prompt versions currently used for requests (alias + version or code fallback)."""
    if refresh:
        clear_cache()
    return resolved_prompts()


@app.post("/generate", response_model=GenerateResponse)
def generate_manifests(request: GenerateRequest):
    return run_pipeline(request)


def run():
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.environ.get("APP_HOST", "0.0.0.0"),
        port=int(os.environ.get("APP_PORT", "8000")),
    )


if __name__ == "__main__":
    run()
