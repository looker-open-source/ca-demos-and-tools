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

"""Reusable Agent UI components."""

import dash_mantine_components as dmc
from prism.common.schemas.agent import Agent
from prism.ui.components.cards import render_detail_card


def render_agent_card(agent: Agent | None):
  """Renders the agent details card."""
  if not agent:
    return None

  config = {}
  if agent.config and agent.config.datasource:
    if hasattr(agent.config.datasource, "model_dump"):
      config = agent.config.datasource.model_dump()
    else:
      config = agent.config.datasource

  is_looker = "instance_uri" in config
  ds_type = "Looker" if is_looker else "BigQuery"

  details = []

  if agent.config:
    if agent.config.project_id:
      details.append({"label": "Project ID", "value": agent.config.project_id})
    if agent.config.location:
      details.append({"label": "Location", "value": agent.config.location})

  if is_looker:
    details.append(
        {"label": "Instance URI", "value": config.get("instance_uri", "")}
    )
    if config.get("model"):
      details.append({"label": "Model", "value": config["model"]})

    explores = config.get("explores", [])
    if explores:
      details.append({"label": "Explores", "value": ", ".join(explores)})
  else:
    tables = config.get("tables", [])
    if tables:
      details.append({"label": "Tables", "value": ", ".join(tables)})
    else:
      details.append({"label": "Tables", "value": "No tables configured"})

  items = []
  for d in details:
    items.append(
        dmc.Stack(
            gap=2,
            children=[
                dmc.Text(
                    d["label"], size="xs", fw=700, c="dimmed", tt="uppercase"
                ),
                dmc.Text(
                    d["value"],
                    size="sm",
                    fw=500,
                    style={"wordBreak": "break-all"},
                ),
            ],
            mb="sm",
        )
    )

  return render_detail_card(
      title=agent.name,
      icon="bi:robot",
      icon_color="var(--mantine-color-blue-6)",
      children=dmc.Stack(gap="xs", children=items),
      action=dmc.Badge(
          ds_type, variant="light", color="violet" if is_looker else "blue"
      ),
  )


# Colour per check status, and whether it counts as a pass. Not found and
# permission denied are both failures, but they are different failures: one is
# fixed in the form, the other by granting the service account access.
_BQ_CHECK_STATUS = {
    "ok": ("green", True),
    "invalid": ("red", False),
    "not_found": ("red", False),
    "denied": ("orange", False),
    "error": ("red", False),
}


def render_bq_check_results(results: list[dict[str, str]]):
  """Renders the result of checking BQ tables, for the test alert.

  Args:
    results: What ``check_bigquery_tables`` returned, one entry per table.

  Returns:
    A (children, color) pair for the alert.
  """
  if not results:
    return "No tables to check.", "orange"

  lines = []
  failed = 0
  for result in results:
    color, passed = _BQ_CHECK_STATUS.get(result["status"], ("red", False))
    if not passed:
      failed += 1
    lines.append(
        dmc.Group(
            gap="xs",
            align="flex-start",
            children=[
                dmc.Badge(
                    result["table"],
                    color=color,
                    variant="light",
                    size="sm",
                    tt="none",
                ),
                dmc.Text(result["message"], size="sm"),
            ],
        )
    )

  if failed:
    summary = f"{failed} of {len(results)} tables could not be read."
  else:
    summary = f"All {len(results)} tables are readable."

  return (
      dmc.Stack(
          gap="xs", children=[dmc.Text(summary, fw=600, size="sm")] + lines
      ),
      "red" if failed else "green",
  )
