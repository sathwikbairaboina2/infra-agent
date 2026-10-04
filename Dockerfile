FROM hashicorp/terraform:1.16.5 AS tf
FROM openpolicyagent/opa:1.21.1-static AS opa
FROM ghcr.io/astral-sh/uv:0.12.21 AS uv

FROM python:3.12-slim AS dev
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && git config --system --add safe.directory '*'
COPY --from=tf /bin/terraform /usr/local/bin/terraform
COPY --from=opa /opa /usr/local/bin/opa
COPY --from=uv /uv /uvx /usr/local/bin/
COPY docker/terraformrc /opt/terraform/terraformrc
ENV TF_CLI_CONFIG_FILE=/opt/terraform/terraformrc \
    TF_IN_AUTOMATION=1 \
    CHECKPOINT_DISABLE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1
COPY docker/mirror/versions.tf /tmp/mirror/versions.tf
RUN mkdir -p /opt/terraform/plugin-cache \
 && cd /tmp/mirror \
 && TF_CLI_CONFIG_FILE= terraform providers mirror -platform=linux_amd64 /opt/terraform/mirror \
 && terraform init -backend=false -input=false >/dev/null \
 && rm -rf /tmp/mirror
WORKDIR /work

FROM dev AS runtime
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY examples ./examples
RUN uv sync --frozen --no-dev && ln -s /app/.venv/bin/infra-agent /usr/local/bin/infra-agent
ENV INFRA_AGENT_HOME=/data
ENTRYPOINT ["infra-agent"]
