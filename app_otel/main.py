import os

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
MLFLOW_EXPERIMENT_ID = os.environ.get("MLFLOW_EXPERIMENT_ID", "0")
MLFLOW_TRACKING_TOKEN = os.environ.get("MLFLOW_TRACKING_TOKEN", "")

headers = f"x-mlflow-experiment-id={MLFLOW_EXPERIMENT_ID}"
if MLFLOW_TRACKING_TOKEN:
    headers += f",Authorization=Bearer {MLFLOW_TRACKING_TOKEN}"

os.environ.setdefault(
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    f"{MLFLOW_TRACKING_URI}/v1/traces",
)
os.environ.setdefault("OTEL_EXPORTER_OTLP_TRACES_HEADERS", headers)
os.environ.setdefault("OTEL_SERVICE_NAME", "arbiter")

import uvicorn
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app_otel.models import GenerateRequest, GenerateResponse
from app_otel.pipeline import run_pipeline

app = FastAPI(title="Arbiter (OTel)", version="0.1.0")
FastAPIInstrumentor.instrument_app(app)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate", response_model=GenerateResponse)
def generate_manifests(request: GenerateRequest):
    return run_pipeline(request)


def run():
    uvicorn.run(
        "app_otel.main:app",
        host=os.environ.get("APP_HOST", "0.0.0.0"),
        port=int(os.environ.get("APP_PORT", "8000")),
    )


if __name__ == "__main__":
    run()
