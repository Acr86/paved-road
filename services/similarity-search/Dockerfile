# Build stage: resolve and install dependencies into an isolated venv.
# Dependency layers are keyed on pyproject.toml only, so source-only changes
# never re-download dependencies (numpy wheels are the slow part here).
FROM python:3.12-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
WORKDIR /build
ENV VIRTUAL_ENV=/opt/venv
RUN uv venv "$VIRTUAL_ENV"
COPY pyproject.toml ./
RUN uv pip install -r pyproject.toml
COPY src/ src/
RUN uv pip install --no-deps .

# Runtime stage: no compiler, no package manager state, non-root user.
# Model weights are deliberately NOT baked in: a real backend pulls them into
# MODEL_CACHE_DIR (an emptyDir in the manifests) at startup, so the image
# stays small, scannable, and independent of model release cadence.
FROM python:3.12-slim-bookworm
RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    SERVICE_NAME=similarity-search \
    MODEL_CACHE_DIR=/models
# Numeric UID: kubelets enforcing runAsNonRoot cannot verify a named user.
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
