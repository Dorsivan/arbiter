import os

import mlflow

MODEL_NAME = os.environ.get("MODEL_NAME", "")
MODEL_URL = os.environ.get("OPENAI_API_BASE", "http://localhost:8000/v1")

JUDGE_MODEL_NAME = os.environ.get("JUDGE_MODEL_NAME", MODEL_NAME)
JUDGE_MODEL_URL = os.environ.get("JUDGE_MODEL_URL", MODEL_URL)
JUDGE_API_KEY = os.environ.get("JUDGE_API_KEY", os.environ.get("OPENAI_API_KEY", ""))


def setup_mlflow(experiment_name: str | None = None) -> None:
    """Point MLflow at the tracking server, workspace and experiment.

    On OpenShift AI the workspace is the project (namespace). The env var is
    left in place: MLflow 3.x clients with workspace support read it too.
    """
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    workspace = os.environ.get("MLFLOW_WORKSPACE")
    if workspace:
        mlflow.set_workspace(workspace)
    mlflow.set_experiment(
        experiment_name or os.environ.get("MLFLOW_EXPERIMENT_NAME", "arbiter")
    )
