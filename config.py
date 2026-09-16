import os

import mlflow

MODEL_NAME = os.environ.get("MODEL_NAME", "")
MODEL_URL = os.environ.get("OPENAI_API_BASE", "http://localhost:8000/v1")

JUDGE_MODEL_NAME = os.environ.get("JUDGE_MODEL_NAME", MODEL_NAME)
JUDGE_MODEL_URL = os.environ.get("JUDGE_MODEL_URL", MODEL_URL)
JUDGE_API_KEY = os.environ.get("JUDGE_API_KEY", os.environ.get("OPENAI_API_KEY", ""))


def setup_mlflow():
    mlflow.set_tracking_uri(
        os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
    )
    workspace = os.environ.pop("MLFLOW_WORKSPACE", None)
    if workspace:
        mlflow.set_workspace(workspace)
    mlflow.set_experiment(
        os.environ.get("MLFLOW_EXPERIMENT_NAME", "arbiter")
    )
