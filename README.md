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

## Workshop branch (`workshop`)

This branch is used by the *MLOps Enablement on OpenShift AI* hands-on labs. Compared with `main` it adds:

- **MLflow Prompt Registry**: the 6 prompts (`arbiter-{analyze,generate,review}-{system,user}`) are loaded by alias at request time (`app/prompt_store.py`). If the registry or alias is unavailable, the code constants in `app/prompts.py` are used (templates use MLflow `{{var}}` syntax).
- **Trace tags**: every `k8s_manifest_pipeline` trace carries `arbiter.prompt_alias`, `arbiter.model` and `arbiter.prompt.<name>=<version|code>`.
- **`GET /prompts`**: shows which prompt versions are in use (`?refresh=true` clears the cache).
- **OpenShift-ready image** (UBI 9 Python 3.12, arbitrary UID) and a **kustomize base** in `manifests/` plus a k6 Job in `k6/`.

### Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_BASE` | `http://localhost:8000/v1` | OpenAI-compatible endpoint (e.g. MaaS: `https://maas.<domain>/<ns>/<model>/v1`) |
| `OPENAI_API_KEY` | `EMPTY` | API key (MaaS `sk-oai-…` key) |
| `MODEL_NAME` | | served model name |
| `ARBITER_TEMPERATURE` | `0.2` | sampling temperature |
| `MLFLOW_TRACKING_URI` | `http://localhost:5000` | e.g. `https://<dashboard>/mlflow` on OpenShift AI |
| `MLFLOW_WORKSPACE` | | OpenShift AI project (namespace) |
| `MLFLOW_TRACKING_AUTH` | | `kubernetes-namespaced` to use the pod's service-account token |
| `MLFLOW_EXPERIMENT_NAME` | `arbiter` | experiment for traces |
| `ARBITER_PROMPT_SOURCE` | `registry` | `registry` or `code` |
| `ARBITER_PROMPT_ALIAS` | `production` | alias to load (`staging`, `production`, …) |
| `ARBITER_PROMPT_CACHE_TTL` | `30` | seconds a resolved prompt is cached |
| `ARBITER_REGISTER_PROMPTS_ON_START` | `false` | register the code prompts on startup |

### Prompt registry flow

```bash
# Register the code prompts (new version only if the text changed) and point an alias at them
python register_prompts.py --message "baseline" --alias production
python register_prompts.py --alias staging

# Promote / roll back without redeploying: move the alias (MLflow UI or SDK)
python -c "import mlflow.genai as g; g.set_prompt_alias('arbiter-review-system', alias='production', version=2)"
curl "$ARBITER_URL/prompts?refresh=true"
```

### Deploying with kustomize

```yaml
# overlay/kustomization.yaml
resources:
  - https://github.com/Dorsivan/arbiter//manifests?ref=workshop
namespace: user1
images:
  - name: quay.io/rh-ee-dsivan/arbiter
    newName: image-registry.openshift-image-registry.svc:5000/workshop-images/arbiter
    newTag: latest
```

```bash
oc create secret generic maas-api-key --from-literal=api-key="$(cat ~/.maas/api-key)" -n user1
oc apply -k overlay/
oc apply -k k6/ -n user1          # load test (delete the Job to re-run)
```
