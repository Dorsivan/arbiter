# Arbiter

Kubernetes manifest generator powered by an LLM, with MLflow tracing and k6 load testing.

Arbiter takes a natural-language description of an application and generates production-ready Kubernetes manifests through a 3-step pipeline:

1. **Analyze** — Determines what K8s resources the application needs
2. **Generate** — Produces the YAML manifests
3. **Review** — Audits for security and best practices, outputs corrected manifests

Each step is a separate LLM call, all traced by MLflow.

## Setup

```bash
# Install dependencies
uv sync

# Copy and edit environment variables
cp .env.example .env
```

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_BASE` | Yes | vLLM chat completions endpoint (e.g. `http://localhost:8000/v1`) |
| `MODEL_NAME` | Yes | Model name served by vLLM |
| `OPENAI_API_KEY` | No | API key (default: `EMPTY`) |
| `MLFLOW_TRACKING_URI` | No | MLflow server URL |
| `MLFLOW_TRACKING_TOKEN` | No | MLflow bearer auth token |
| `MLFLOW_WORKSPACE` | No | MLflow workspace name |

## Run

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or with Docker:

```bash
docker compose up --build
```

## API

### `GET /health`

Returns `{"status": "ok"}`.

### `POST /generate`

```bash
curl -X POST http://localhost:8000/generate \
  -H 'Content-Type: application/json' \
  -d '{"description": "A Python Flask web app with PostgreSQL and Redis"}'
```

Request body:

```json
{
  "description": "A Python Flask web app with PostgreSQL and Redis",
  "repo_url": null,
  "namespace": "default",
  "replicas": 2
}
```

## Load testing with k6

```bash
k6 run k6/load_test.js
```

Override the base URL:

```bash
k6 run -e BASE_URL=http://your-host:8000 k6/load_test.js
```

## MLflow tracing

Each request produces a trace tree visible in the MLflow UI:

```
k8s_manifest_pipeline (CHAIN)
  ├── analyze (LLM)
  │   └── ChatCompletion (CHAT_MODEL)  [autologged]
  ├── generate (LLM)
  │   └── ChatCompletion (CHAT_MODEL)  [autologged]
  └── review (LLM)
      └── ChatCompletion (CHAT_MODEL)  [autologged]
```
