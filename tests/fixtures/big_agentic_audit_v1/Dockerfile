FROM ghcr.io/astral-sh/uv:0.11.29@sha256:eb2843a1e56fd9e30c7276ce1a52cba86e64c7b385f5e3279a0e08e02dd058fc AS uv
FROM python:3.13.14-bookworm@sha256:8b9a8b28d9cc221c6ab5d40e9cfcd99429959f6a8f5171612a99147975ab043f
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PYTHON_INSTALL_DIR=/opt/python UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /opt/runtime
COPY pyproject.toml uv.lock .python-version ./
RUN uv python install 3.13.14 && uv sync --locked --managed-python --no-dev && /opt/venv/bin/python -c "import sys; assert sys.version_info[:3] == (3, 13, 14)"
ENV PATH=/opt/venv/bin:/usr/local/bin:/usr/bin:/bin UV_OFFLINE=1 UV_NO_SYNC=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp/baa-home TMPDIR=/audit/tmp XDG_CACHE_HOME=/tmp/cache XDG_CONFIG_HOME=/tmp/config
ENV GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0=/repo
USER 1000:1000
WORKDIR /repo
