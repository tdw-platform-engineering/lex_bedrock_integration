# syntax=docker/dockerfile:1.6

# --- Stage 1: Builder ---
FROM public.ecr.aws/docker/library/python:3.14-rc-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_CACHE_DIR=/root/.cache/uv

WORKDIR /build

RUN --mount=type=bind,source=requirements.txt,target=requirements.txt \
    --mount=type=cache,target=/root/.cache/uv \
    uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install --no-cache -r requirements.txt awslambdaric

# --- Stage 2: Runtime ---
FROM public.ecr.aws/docker/library/python:3.14-rc-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    LAMBDA_TASK_ROOT="/var/task" \
    PYTHONPATH="/opt/venv/lib/python3.14/site-packages:/var/task"

WORKDIR ${LAMBDA_TASK_ROOT}

COPY --from=builder /opt/venv /opt/venv
COPY src ./src

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL -o /usr/local/bin/aws-lambda-rie https://github.com/aws/aws-lambda-runtime-interface-emulator/releases/latest/download/aws-lambda-rie \
    && chmod +x /usr/local/bin/aws-lambda-rie \
    && rm -rf /var/lib/apt/lists/*

RUN printf '%s\n' \
    '#!/bin/sh' \
    'if [ -z "${AWS_LAMBDA_RUNTIME_API}" ]; then' \
    '  exec /usr/local/bin/aws-lambda-rie /opt/venv/bin/python -m awslambdaric "$@"' \
    'else' \
    '  exec /opt/venv/bin/python -m awslambdaric "$@"' \
    'fi' > /entry.sh && chmod +x /entry.sh

ENTRYPOINT ["/entry.sh"]
CMD ["src.lambda_function.lambda_handler"]
