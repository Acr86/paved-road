# Image for the in-cluster preview janitor: the same CLI a developer runs
# locally, so the janitor's behavior is exactly the unit-tested code path.
FROM python:3.12-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
WORKDIR /build
ENV VIRTUAL_ENV=/opt/venv
RUN uv venv "$VIRTUAL_ENV"
COPY pyproject.toml README.md ./
COPY src/ src/
RUN uv pip install .

FROM python:3.12-slim-bookworm
ARG KUBECTL_VERSION=v1.33.4
ADD --chmod=0755 https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl /usr/local/bin/kubectl
RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
USER app
ENTRYPOINT ["platform"]
CMD ["--help"]
