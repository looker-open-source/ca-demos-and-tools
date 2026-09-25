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

"""Main entry point for the Prism UI."""

import logging
import os
import secrets
import sys
import dash
import dash_mantine_components as dmc
from prism.client.prism_client import PrismClient
from prism.ui import callbacks
from prism.ui import pages
from prism.ui.components import shell
from prism.ui.constants import GLOBAL_PROJECT_ID_STORE
from prism.ui.constants import NOTIFICATION_CONTAINER
from prism.ui.constants import REDIRECT_HANDLER

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
logger = logging.getLogger(__name__)

app = dash.Dash(
    __name__,
    use_pages=True,
    pages_folder="",
    suppress_callback_exceptions=True,
    title="Prism",
)

pages.register_all_pages()
callbacks.register_all_callbacks()

# Flask will not open a session without a signing key, and utils keeps the
# error-toast throttle in the session so one reader's failure cannot silence
# another's toast. A key generated per process is enough: the Dockerfile runs a
# single gunicorn worker, and a restart only reopens the throttle. Nothing
# sensitive goes in the session.
app.server.secret_key = secrets.token_bytes(32)

app.layout = dmc.MantineProvider(
    theme={
        "colorScheme": "light",
        "fontFamily": "Inter, sans-serif",
        # The brand blue #135bec sits at shade 6 of the indigo scale below,
        # so indigo is the primary.
        "primaryColor": "indigo",
        "defaultRadius": "md",
        "colors": {
            "slate": [
                "#f8fafc",
                "#f1f5f9",
                "#e2e8f0",
                "#cbd5e1",
                "#94a3b8",
                "#64748b",
                "#475569",
                "#334155",
                "#1e293b",
                "#0f172a",
            ],
            "indigo": [
                "#edf2ff",
                "#d0dbff",
                "#a1b4fe",
                "#6d86fd",
                "#445dfc",
                "#2e44fb",
                "#135bec",
                "#1e37d5",
                "#162fbf",
                "#1126a8",
            ],
        },
        "components": {
            "Button": {"defaultProps": {"fw": 500}},
            "Paper": {"defaultProps": {"shadow": "none", "withBorder": True}},
            "Card": {"defaultProps": {"shadow": "none", "withBorder": True}},
        },
        "shadows": {
            "xs": "none",
            "sm": "none",
            "md": "none",
            "lg": "none",
            "xl": "none",
        },
    },
    children=[
        dash.dcc.Location(id="url", refresh=False),
        dash.dcc.Location(id=REDIRECT_HANDLER, refresh=True),
        dash.dcc.Store(id=GLOBAL_PROJECT_ID_STORE, storage_type="session"),
        dmc.NotificationContainer(id=NOTIFICATION_CONTAINER),
        dmc.AppShell(
            header={"height": 64},
            padding="md",
            children=[
                shell.render_header(),
                dmc.AppShellMain(
                    style={"backgroundColor": "#f8fafc"},
                    children=[dash.page_container],
                ),
            ],
        ),
    ],
)

# prod.py serves this under gunicorn.
server = app.server

if __name__ == "__main__":
  # Development server only. Deployments run prism.prod:app under gunicorn.
  #
  # The Werkzeug debugger runs arbitrary Python for anyone who can reach the
  # port, and Prism has no auth of its own, so debug is off and the bind
  # address is loopback unless PRISM_DEBUG / PRISM_HOST say otherwise.
  #
  # Read the environment directly: prism.ui can't import prism.server
  # (tests/test_ui_isolation.py).
  debug = os.environ.get("PRISM_DEBUG", "false").lower() == "true"
  # WERKZEUG_RUN_MAIN keeps the worker out of the reloader's second process,
  # so it only starts once.
  if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not debug:
    PrismClient().system.start_worker_pool()

  host = os.environ.get("PRISM_HOST", "127.0.0.1")
  port = int(os.environ.get("PORT", 8080))
  app.run(host=host, port=port, debug=debug)
