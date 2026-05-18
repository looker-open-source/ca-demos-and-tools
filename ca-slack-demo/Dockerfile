FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock* ./

# Install dependencies (no dev extras, no editable install)
RUN uv sync --frozen --no-dev --no-install-project

# Copy source
COPY src/ src/
COPY scripts/ scripts/
COPY context/ context/

# Cloud Run sets PORT; the health server in app.py listens on it.
# Socket Mode connects outbound to Slack — no inbound port configuration needed.
ENV PORT=8080

CMD ["uv", "run", "--no-dev", "python", "scripts/run_slack.py"]
