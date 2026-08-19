import requests
import streamlit as st

st.set_page_config(page_title="Arbiter", page_icon="⎈", layout="wide")
st.title("⎈ Arbiter")
st.caption("Generate Kubernetes manifests from application descriptions")

backend_url = st.sidebar.text_input(
    "Arbiter API URL", value="http://localhost:8000"
)

st.sidebar.divider()
st.sidebar.markdown("**Request options**")
namespace = st.sidebar.text_input("Namespace", value="default")
replicas = st.sidebar.number_input("Replicas", min_value=1, max_value=20, value=2)

description = st.text_area(
    "Describe your application",
    height=120,
    placeholder="e.g. A Python Flask web app with PostgreSQL database and Redis cache",
)

repo_url = st.text_input(
    "GitHub repository URL (optional)",
    placeholder="https://github.com/org/repo",
)

if st.button("Generate Manifests", type="primary", disabled=not description):
    payload = {
        "description": description,
        "namespace": namespace,
        "replicas": replicas,
    }
    if repo_url:
        payload["repo_url"] = repo_url

    with st.spinner("Running pipeline: analyze → generate → review ..."):
        try:
            resp = requests.post(
                f"{backend_url}/generate",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
        except requests.ConnectionError:
            st.error(f"Could not connect to Arbiter API at {backend_url}")
            st.stop()
        except requests.HTTPError as e:
            st.error(f"API error: {e.response.status_code} — {e.response.text}")
            st.stop()

    data = resp.json()

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Resource Plan")
        st.markdown(f"**App name:** `{data['app_name']}`")
        st.markdown(f"**App type:** `{data['resource_plan']['app_type']}`")
        st.markdown("**Resources:**")
        for r in data["resource_plan"]["resources"]:
            st.markdown(f"- `{r}`")
        with st.expander("Reasoning"):
            st.write(data["resource_plan"]["reasoning"])

    with col2:
        st.subheader("Review")
        if data["review"]["issues"]:
            st.markdown("**Issues found:**")
            for issue in data["review"]["issues"]:
                st.markdown(f"- {issue}")
        if data["review"]["corrections_applied"]:
            st.markdown("**Corrections applied:**")
            for c in data["review"]["corrections_applied"]:
                st.markdown(f"- {c}")
        if data["review"]["security_notes"]:
            st.markdown("**Security notes:**")
            for n in data["review"]["security_notes"]:
                st.markdown(f"- {n}")

    st.divider()
    st.subheader("Final Manifests")
    st.code(data["final_manifests"], language="yaml")

    with st.expander("Raw manifests (before review)"):
        st.code(data["raw_manifests"], language="yaml")

    if data.get("trace_id"):
        st.caption(f"MLflow trace ID: `{data['trace_id']}`")
