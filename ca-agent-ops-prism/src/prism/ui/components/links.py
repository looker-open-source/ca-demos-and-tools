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

"""Common UI link components."""

from dash_iconify import DashIconify
import dash_mantine_components as dmc


def render_agent_link(agent_id: int | str, agent_name: str) -> dmc.Anchor:
  """Renders a linked agent name with a blue robot icon."""
  return dmc.Anchor(
      dmc.Group(
          [
              dmc.ThemeIcon(
                  DashIconify(icon="bi:robot", width=20),
                  variant="light",
                  color="blue",
                  size="md",
                  radius="md",
              ),
              dmc.Text(agent_name, size="sm", fw=500),
          ],
          gap="sm",
      ),
      href=f"/agents/view/{agent_id}",
      underline=False,
      c="dark",
      style={"&:hover": {"opacity": 0.8}},
  )


def render_test_suite_link(suite_id: int | str, suite_name: str) -> dmc.Anchor:
  """Renders a linked test suite name with a blue folder icon."""

  return dmc.Anchor(
      dmc.Group(
          [
              dmc.ThemeIcon(
                  DashIconify(icon="material-symbols:folder-open", width=20),
                  variant="light",
                  color="blue",
                  size="md",
                  radius="md",
              ),
              dmc.Text(suite_name, size="sm", fw=500),
          ],
          gap="sm",
      ),
      href=f"/test_suites/view/{suite_id}",
      underline=False,
      c="dark",
      style={"&:hover": {"opacity": 0.8}},
  )
