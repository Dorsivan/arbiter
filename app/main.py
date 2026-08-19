import os
from contextlib import asynccontextmanager

import mlflow
import mlflow.anthropic
import mlflow.openai
from fastapi import FastAPI

from app.models import GenerateRequest, GenerateResponse
from app.pipeline import run_pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    mlflow.set_tracking_uri(
        os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
    )
    # MLFLOW_WORKSPACE triggers a workspace-support probe that fails on
    # servers (e.g. OpenShift AI) that don't expose that endpoint as JSON.
    # Strip it so set_experiment doesn't crash, then restore it.
    workspace = os.environ.pop("MLFLOW_WORKSPACE", None)
    try:
        mlflow.set_experiment(os.environ.get("MLFLOW_EXPERIMENT_NAME", "arbiter"))
    finally:
        if workspace is not None:
            os.environ["MLFLOW_WORKSPACE"] = workspace
    backend = os.environ.get("LLM_BACKEND", "openai")
    if backend == "anthropic":
        mlflow.anthropic.autolog()
    else:
        mlflow.openai.autolog()
    yield


app = FastAPI(title="Arbiter", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


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
