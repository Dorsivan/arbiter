# Runs on OpenShift: non-root, arbitrary UID (group 0 writable), port 8000.
FROM registry.access.redhat.com/ubi9/python-312:latest

USER 0
WORKDIR /opt/app-root/src
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    python -c "import tomllib; print('\\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY app/ app/
COPY config.py register_prompts.py ./
RUN chgrp -R 0 /opt/app-root/src && chmod -R g=u /opt/app-root/src

USER 1001
ENV PYTHONUNBUFFERED=1 \
    APP_PORT=8000 \
    MLFLOW_DISABLE_AGENT_HINT=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
