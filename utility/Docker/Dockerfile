# define an alias for the specific python version used in this file.
FROM docker.io/python:3.12.8-slim-bookworm AS python

# Python build stage
FROM python as python-build-stage

ARG BUILD_ENVIRONMENT=production

# Install apt packages
RUN apt-get update && apt-get install --no-install-recommends -y \
  # dependencies for building Python packages
  build-essential \
  curl \
  # psycopg2 dependencies
  libpq-dev

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy project files for dependency installation
COPY pyproject.toml uv.lock ./

# Create virtual environment and install dependencies from lockfile
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$BUILD_ENVIRONMENT" = "production" ]; then \
      uv sync --frozen --no-install-project --no-dev --extra production; \
    else \
      uv sync --frozen --no-install-project; \
    fi


# Python 'run' stage
FROM python as python-run-stage

ARG BUILD_ENVIRONMENT=production
ARG APP_HOME=/app

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV BUILD_ENV ${BUILD_ENVIRONMENT}

WORKDIR ${APP_HOME}

RUN addgroup --system django \
    && adduser --system --ingroup django django


# Install required system dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
  # psycopg2 dependencies
  libpq-dev \
  # Translations dependencies
  gettext \
  curl \
  libmagic1 \
  # cleaning up unused files
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && rm -rf /var/lib/apt/lists/*

# All absolute dir copies ignore workdir instruction. All relative dir copies are wrt to the workdir instruction
# copy virtual environment from python-build-stage
COPY --from=python-build-stage /.venv ${APP_HOME}/.venv

# Activate virtual environment
ENV PATH="${APP_HOME}/.venv/bin:$PATH"
ENV VIRTUAL_ENV="${APP_HOME}/.venv"


COPY --chown=django:django ./utility/Docker/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint


COPY --chown=django:django ./utility/Docker/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start


# copy application code to WORKDIR
COPY --chown=django:django . ${APP_HOME}

# make django owner of the WORKDIR directory as well.
RUN chown -R django:django ${APP_HOME}

# Install uv for project installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install the project itself into the virtual environment
RUN uv sync --frozen --no-dev --extra production

USER django

RUN DATABASE_URL="" \
  DJANGO_SETTINGS_MODULE="config.settings.test" \
  python manage.py compilemessages

ENTRYPOINT ["/entrypoint"]
CMD ${STARTUP_COMMAND}
