# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM python:3.13-slim

# Nothing here needs root, so the container does not run as it. The USER
# switch is before the syncs rather than after, so the virtualenv and the
# application files are created owned by prism and no chown pass is needed.
# --create-home gives uv a cache directory it can write to.
RUN useradd --create-home --shell /usr/sbin/nologin prism

WORKDIR /app
RUN chown prism:prism /app

# uv is pinned, so rebuilding an old commit gets the uv that commit was tested
# with. With :latest the image depends on the day it was built.
COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /uvx /bin/

USER prism

COPY --chown=prism:prism pyproject.toml uv.lock ./

# Dependencies only, in their own layer, so editing application code does not
# re-download them. uv.lock is copied above, so this installs the same versions
# the sync after `COPY . .` will. Resolving fresh here instead made the layer
# useless: it fetched whatever was current, then the second sync replaced
# everything the lock pinned to an older version. --locked fails the build if
# the lock is out of date rather than quietly resolving something else.
RUN uv sync --locked --no-install-project --no-dev

COPY --chown=prism:prism . .

# This sync builds the project, and pyproject.toml names README.md as the
# readme, so setuptools needs the file. It arrives with the COPY above, which
# is why .dockerignore re-includes it. Keeping it out of the layer above means
# editing the README no longer re-downloads every dependency.
RUN uv sync --locked --no-dev --no-editable

# Metadata only, and only the default. The bind below is ${PORT:-8080}, so a
# deployment that sets PORT listens somewhere else and Cloud Run ignores EXPOSE
# either way.
EXPOSE 8080

ENV PYTHONUNBUFFERED=1

# Workers=1 because importing prism.prod starts a background worker pool, so a
# second gunicorn worker means a second pool against the same run queue.
# Timeout is 3600 to match scripts/run_prod.sh. Trials run in spawned
# subprocesses, so the request path does not need an unbounded timeout, and 0
# would turn the watchdog off entirely and let a wedged worker sit there.
#
# Shell form, so $PORT expands. Cloud Run injects it and only defaults it to
# 8080; a deployment that sets anything else fails its health check against a
# hardcoded bind. exec keeps gunicorn as PID 1, so it still gets the SIGTERM.
CMD ["/bin/sh", "-c", "exec /app/.venv/bin/gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 3600 prism.prod:app"]
