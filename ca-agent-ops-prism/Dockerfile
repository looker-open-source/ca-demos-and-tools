# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy pyproject.toml and README.md (referenced in pyproject.toml) to ensure fresh lockfile
COPY pyproject.toml README.md ./

# Install dependencies (generates uv.lock inside the container)
RUN uv sync --no-install-project --no-dev

# Copy the rest of the application code
COPY . .

# Install the application as a non-editable package
RUN uv sync --no-dev --no-editable

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Define environment variable
ENV PYTHONUNBUFFERED=1

# Run the application using Gunicorn from the virtual environment
# Workers=1 to prevent multiple backend dispatchers (if applicable, though Prism UI seems stateless mostly)
# Threads=8 for concurrency
# Timeout=0 to allow long-running requests (if any)
CMD ["/app/.venv/bin/gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "0", "prism.prod:app"]
