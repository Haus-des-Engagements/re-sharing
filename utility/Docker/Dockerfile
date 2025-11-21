# Build stage - install dependencies
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0

# Install build dependencies for psycopg and other packages
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    libpq-dev

WORKDIR /app

# Install dependencies (without the project itself)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev --extra production

# Copy application code
COPY . /app

# Install the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --extra production


# Final runtime stage
FROM python:3.12-slim-bookworm

ARG APP_HOME=/app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install runtime dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install --no-install-recommends -y \
    libpq-dev \
    gettext \
    libmagic1 \
    curl \
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --system --gid 999 django \
    && useradd --system --gid 999 --uid 999 --create-home django

# Copy application and virtual environment from builder
COPY --from=builder --chown=django:django /app ${APP_HOME}

# Copy entrypoint and start scripts
COPY --chown=django:django ./utility/Docker/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint && chmod +x /entrypoint

COPY --chown=django:django ./utility/Docker/start /start
RUN sed -i 's/\r$//g' /start && chmod +x /start

# Place executables in the environment at the front of the path
ENV PATH="${APP_HOME}/.venv/bin:$PATH"

# Use the non-root user
USER django

# Use /app as the working directory
WORKDIR ${APP_HOME}

# Compile translation messages
RUN DATABASE_URL="" \
    DJANGO_SETTINGS_MODULE="config.settings.test" \
    python manage.py compilemessages

ENTRYPOINT ["/entrypoint"]
CMD ["/start"]
