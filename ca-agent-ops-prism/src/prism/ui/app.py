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
import sys

import dash
import dash_mantine_components as dmc
from prism.client.prism_client import PrismClient
from prism.ui import callbacks
from prism.ui import pages
from prism.ui.components import shell
from prism.ui.constants import GLOBAL_PROJECT_ID_STORE

# Configure logging
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

app.layout = dmc.MantineProvider(
    theme={
        "colorScheme": "light",
        "fontFamily": "Inter, sans-serif",
        "primaryColor": "indigo",  # #135bec is close to indigo
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
        dash.dcc.Location(id="redirect-handler", refresh=True),
        dash.dcc.Store(id=GLOBAL_PROJECT_ID_STORE, storage_type="session"),
        dmc.NotificationContainer(id="notification-container"),
        dmc.AppShell(
            header={"height": 64},
            padding="md",
            children=[
                shell.render_header(),
                dmc.AppShellMain(
                    style={"backgroundColor": "#f8fafc"},  # slate-50
                    children=[dash.page_container],
                ),
            ],
        ),
    ],
)

# Export the server instance, used in prod.py
server = app.server

if __name__ == "__main__":
  # Start the background worker pool
  # We check WERKZEUG_RUN_MAIN to prevent starting the worker twice.
  # Reloader starts a second process; we only want the worker in 'main'.
  debug = True
  if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not debug:
    PrismClient().system.start_worker_pool(num_workers=2)

  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port, debug=debug)
