FROM ghcr.io/astral-sh/uv:0.12.20 AS uv
FROM python:3.12.14-slim-bookworm AS base

COPY --from=uv /uv /usr/local/bin/uv
RUN apt-get update \
    && apt-get install -y --no-install-recommends libltdl7 libkrb5-3 libgssapi-krb5-2 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 workbench
WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY config ./config
COPY fixtures ./fixtures
COPY sql ./sql

FROM base AS test
RUN uv sync --locked --no-editable
COPY tests ./tests
COPY docs/evidence/p05/golden-evidence.json ./docs/evidence/p05/golden-evidence.json
USER workbench
ENTRYPOINT ["python", "-m", "pytest"]
CMD ["-q", "-p", "no:cacheprovider"]

FROM base AS runtime
RUN uv sync --locked --no-dev --no-editable
USER workbench
ENTRYPOINT ["workbench"]
CMD ["health"]
