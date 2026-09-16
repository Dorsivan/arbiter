#!/usr/bin/env python3
import os
import re

import yaml
import requests
import mlflow
from mlflow.genai.datasets import create_dataset
from mlflow.genai import scorer
from mlflow.genai.scorers import Correctness, Safety, RelevanceToQuery
from mlflow.genai.judges import make_judge

from config import (
    setup_mlflow, MODEL_NAME, MODEL_URL,
    JUDGE_MODEL_NAME, JUDGE_MODEL_URL, JUDGE_API_KEY,
)


DATASET_NAME = "arbiter_k8s_manifests_v1"
ARBITER_API_URL = os.environ.get("ARBITER_API_URL", "http://localhost:8000")


def create_evaluation_dataset():
    dataset = create_dataset(
        name=DATASET_NAME,
        tags={
            "version": "1.0",
            "domain": "kubernetes-manifests",
            "team": "ml-platform",
            "status": "active",
        },
    )

    records = [
        {
            "inputs": {
                "description": "A Python Flask web application with PostgreSQL database and Redis cache",
            },
            "expectations": {
                "expected_resources": ["Deployment", "Service", "ConfigMap", "Secret"],
                "expected_app_type": "web-app",
                "expected_response": (
                    "Kubernetes manifests with Deployment, Service, ConfigMap, "
                    "and Secret for a Flask app with PostgreSQL and Redis dependencies"
                ),
            },
        },
        {
            "inputs": {
                "description": "A Node.js microservice that processes messages from RabbitMQ",
            },
            "expectations": {
                "expected_resources": ["Deployment", "Service"],
                "expected_app_type": "worker",
                "expected_response": (
                    "Kubernetes manifests for a message-processing worker "
                    "with a Deployment and Service"
                ),
            },
        },
        {
            "inputs": {
                "description": "A Java Spring Boot REST API with MySQL backend and Elasticsearch",
            },
            "expectations": {
                "expected_resources": ["Deployment", "Service", "ConfigMap", "Secret"],
                "expected_app_type": "api-service",
                "expected_response": (
                    "Kubernetes manifests for a Spring Boot API service with "
                    "database and search engine dependencies"
                ),
            },
        },
        {
            "inputs": {
                "description": "A static website served by nginx with TLS termination",
            },
            "expectations": {
                "expected_resources": ["Deployment", "Service", "Ingress"],
                "expected_app_type": "web-app",
                "expected_response": (
                    "Kubernetes manifests for an nginx-based static site with "
                    "Ingress for TLS termination"
                ),
            },
        },
        {
            "inputs": {
                "description": "A Python Celery worker that processes image uploads with S3 storage",
            },
            "expectations": {
                "expected_resources": ["Deployment", "Secret"],
                "expected_app_type": "worker",
                "expected_response": (
                    "Kubernetes manifests for a Celery background worker "
                    "with S3 credentials stored in a Secret"
                ),
            },
        },
        {
            "inputs": {
                "description": "A Go gRPC service with MongoDB and Prometheus metrics",
            },
            "expectations": {
                "expected_resources": ["Deployment", "Service"],
                "expected_app_type": "api-service",
                "expected_response": (
                    "Kubernetes manifests for a gRPC service with MongoDB "
                    "connectivity and Prometheus scrape annotations"
                ),
            },
        },
        {
            "inputs": {
                "description": "A Ruby on Rails app with Sidekiq background jobs and PostgreSQL",
            },
            "expectations": {
                "expected_resources": ["Deployment", "Service", "ConfigMap", "Secret"],
                "expected_app_type": "web-app",
                "expected_response": (
                    "Kubernetes manifests for a Rails app with separate "
                    "Sidekiq worker deployment and PostgreSQL"
                ),
            },
        },
        {
            "inputs": {
                "description": "A scheduled data pipeline that runs ETL jobs every hour using Python",
            },
            "expectations": {
                "expected_resources": ["CronJob", "ConfigMap", "Secret"],
                "expected_app_type": "cronjob",
                "expected_response": (
                    "Kubernetes CronJob manifest for an hourly ETL pipeline "
                    "with configuration and credentials"
                ),
            },
        },
    ]

    dataset.merge_records(records)
    print(f"Created dataset '{DATASET_NAME}' with {len(records)} records")
    return dataset


def predict_fn(description: str) -> str:
    resp = requests.post(
        f"{ARBITER_API_URL}/generate",
        json={"description": description, "namespace": "evaluation", "replicas": 2},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["final_manifests"]


# --- Custom Code Scorers ---

@scorer
def is_valid_yaml(outputs: str) -> bool:
    try:
        docs = list(yaml.safe_load_all(outputs))
        return len(docs) > 0 and all(isinstance(d, dict) for d in docs if d is not None)
    except yaml.YAMLError:
        return False


@scorer
def has_deployment(outputs: str) -> bool:
    try:
        docs = list(yaml.safe_load_all(outputs))
        return any(
            d.get("kind") == "Deployment"
            for d in docs
            if isinstance(d, dict)
        )
    except yaml.YAMLError:
        return False


@scorer
def has_service(outputs: str) -> bool:
    try:
        docs = list(yaml.safe_load_all(outputs))
        return any(
            d.get("kind") == "Service"
            for d in docs
            if isinstance(d, dict)
        )
    except yaml.YAMLError:
        return False


@scorer
def has_resource_limits(outputs: str) -> bool:
    try:
        docs = list(yaml.safe_load_all(outputs))
        for doc in docs:
            if not isinstance(doc, dict) or doc.get("kind") != "Deployment":
                continue
            containers = (
                doc.get("spec", {})
                .get("template", {})
                .get("spec", {})
                .get("containers", [])
            )
            for container in containers:
                resources = container.get("resources", {})
                if not resources.get("limits") or not resources.get("requests"):
                    return False
        return True
    except yaml.YAMLError:
        return False


@scorer
def has_security_context(outputs: str) -> bool:
    try:
        docs = list(yaml.safe_load_all(outputs))
        for doc in docs:
            if not isinstance(doc, dict) or doc.get("kind") != "Deployment":
                continue
            pod_spec = (
                doc.get("spec", {})
                .get("template", {})
                .get("spec", {})
            )
            pod_security = pod_spec.get("securityContext", {})
            containers = pod_spec.get("containers", [])
            has_run_as_non_root = pod_security.get("runAsNonRoot", False)
            has_container_security = all(
                c.get("securityContext") for c in containers
            )
            if has_run_as_non_root or has_container_security:
                return True
        return False
    except yaml.YAMLError:
        return False


@scorer
def has_health_probes(outputs: str) -> bool:
    try:
        docs = list(yaml.safe_load_all(outputs))
        for doc in docs:
            if not isinstance(doc, dict) or doc.get("kind") != "Deployment":
                continue
            containers = (
                doc.get("spec", {})
                .get("template", {})
                .get("spec", {})
                .get("containers", [])
            )
            for container in containers:
                if not container.get("livenessProbe") and not container.get("readinessProbe"):
                    return False
        return True
    except yaml.YAMLError:
        return False


@scorer
def uses_correct_namespace(outputs: str) -> bool:
    try:
        docs = list(yaml.safe_load_all(outputs))
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            ns = doc.get("metadata", {}).get("namespace")
            if ns and ns != "evaluation":
                return False
        return True
    except yaml.YAMLError:
        return False


# --- Custom LLM Judge ---

def _judge_headers() -> dict[str, str] | None:
    if JUDGE_API_KEY:
        return {"Authorization": f"Bearer {JUDGE_API_KEY}"}
    return None


def create_k8s_quality_judge():
    judge_model_uri = f"openai:/{JUDGE_MODEL_NAME}"

    return make_judge(
        name="k8s_manifest_quality",
        model=judge_model_uri,
        base_url=JUDGE_MODEL_URL,
        extra_headers=_judge_headers(),
        description="Evaluates if generated Kubernetes manifests follow production best practices",
        instructions=(
            "Evaluate whether the following Kubernetes manifests are production-ready. "
            "Good manifests should:\n"
            "- Use correct and current API versions (apps/v1 for Deployments)\n"
            "- Include resource requests and limits on all containers\n"
            "- Have security contexts (runAsNonRoot, drop capabilities)\n"
            "- Include liveness and readiness probes\n"
            "- Use standard Kubernetes labels (app.kubernetes.io/*)\n"
            "- Set appropriate service types\n"
            "- Avoid using 'latest' tags without image pull policy\n"
            "- Include all resources needed for the described application\n\n"
            "Application description: {{ inputs }}\n"
            "Generated manifests:\n{{ outputs }}\n\n"
            "Are these manifests production-ready?"
        ),
        feedback_value_type=bool,
    )


def run_evaluation(dataset):
    judge_model_uri = f"openai:/{JUDGE_MODEL_NAME}"
    headers = _judge_headers()

    all_scorers = [
        # Code-based scorers
        is_valid_yaml,
        has_deployment,
        has_service,
        has_resource_limits,
        has_security_context,
        has_health_probes,
        uses_correct_namespace,
        # Built-in LLM-as-judge scorers
        Correctness(model=judge_model_uri, extra_headers=headers),
        Safety(model=judge_model_uri, extra_headers=headers),
        RelevanceToQuery(model=judge_model_uri, extra_headers=headers),
        # Custom LLM judge
        create_k8s_quality_judge(),
    ]

    print(f"\nRunning evaluation with {len(all_scorers)} scorers...")
    print(f"Judge model: {JUDGE_MODEL_NAME} at {JUDGE_MODEL_URL}")

    results = mlflow.genai.evaluate(
        data=dataset,
        predict_fn=predict_fn,
        scorers=all_scorers,
    )

    print("\n=== Evaluation Results ===")
    print(results.tables[0] if results.tables else "No results table available")
    return results


def main():
    setup_mlflow()

    print("=== Arbiter Evaluation Pipeline ===\n")

    # Step 1: Create or get dataset
    dataset = create_evaluation_dataset()

    # Step 2: Run evaluation with all scorers
    results = run_evaluation(dataset)

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
