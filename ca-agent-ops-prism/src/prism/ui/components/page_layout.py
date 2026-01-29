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

"""Standardized page layout components."""

from typing import Any
from dash import html
import dash_mantine_components as dmc


def render_page_header(
    title: str,
    description: Any | None = None,
    actions: list[Any] | None = None,
    breadcrumbs: Any | None = None,
    title_id: str | None = None,
    description_id: str | None = None,
    actions_id: str | None = None,
    breadcrumbs_id: str | None = None,
    status: Any | None = None,
    status_id: str | None = None,
) -> dmc.Group:
  """Renders a standardized page header.

  Args:
      title: The page title (rendered as dmc.Title order=1).
      description: Optional page description (rendered as dimmed text).
      actions: Optional list of buttons or other components to render on the
        right.
      breadcrumbs: Optional breadcrumbs component to render above the title.
      title_id: Optional ID for the title component.
      description_id: Optional ID for the description component.
      actions_id: Optional ID for the actions component.
      breadcrumbs_id: Optional ID for the breadcrumbs container.
      status: Optional status component (rendered next to title).
      status_id: Optional ID for the status component.

  Returns:
      A dmc.Group containing the standardized header.
  """
  title_kwargs = {"order": 1}
  if title_id:
    title_kwargs["id"] = title_id

  description_kwargs = {"c": "dimmed", "size": "sm"}
  if description_id:
    description_kwargs["id"] = description_id

  actions_kwargs = {"gap": "sm"}
  if actions_id:
    actions_kwargs["id"] = actions_id

  # Handle breadcrumbs robustness
  breadcrumb_items = []
  if breadcrumbs:
    breadcrumb_items = (
        breadcrumbs if isinstance(breadcrumbs, list) else [breadcrumbs]
    )

  breadcrumb_container_kwargs = {}
  if breadcrumbs_id:
    breadcrumb_container_kwargs["id"] = breadcrumbs_id

  status_badge_kwargs = {
      "variant": "light",
      "size": "md",
      "radius": "md",
  }
  if status_id:
    status_badge_kwargs["id"] = status_id

  return dmc.Group(
      justify="space-between",
      align="flex-end",
      mb="xl",
      children=[
          html.Div(
              id="header-title-container",
              children=(
                  [html.Div(breadcrumb_items, **breadcrumb_container_kwargs)]
                  if breadcrumbs or breadcrumbs_id
                  else []
              )
              + [
                  dmc.Group(
                      gap="sm",
                      align="center",
                      children=[
                          dmc.Title(title, **title_kwargs),
                          *(
                              [
                                  dmc.Badge(
                                      status,
                                      **status_badge_kwargs,
                                  )
                              ]
                              if status or status_id
                              else []
                          ),
                      ],
                  )
              ]
              + (
                  [dmc.Text(description, **description_kwargs)]
                  if description or description_id
                  else []
              ),
              style={"display": "flex", "flexDirection": "column", "gap": "0"},
          ),
          *(
              [dmc.Group(children=actions, **actions_kwargs)]
              if actions or actions_id
              else []
          ),
      ],
  )


def render_page(
    title: str,
    description: Any | None = None,
    actions: list[Any] | None = None,
    children: list[Any] | None = None,
    breadcrumbs: Any | None = None,
    title_id: str | None = None,
    description_id: str | None = None,
    actions_id: str | None = None,
    breadcrumbs_id: str | None = None,
    status: Any | None = None,
    status_id: str | None = None,
    container_id: str | None = None,
    fluid: bool = False,
) -> dmc.Container:
  """Renders a standardized page with header and content.

  Args:
    title: The page title.
    description: Optional page description.
    actions: Optional action buttons.
    children: The main page content.
    breadcrumbs: Optional breadcrumbs component.
    title_id: Optional ID for the title component.
    description_id: Optional ID for the description component.
    actions_id: Optional ID for the actions component.
    breadcrumbs_id: Optional ID for the breadcrumbs container.
    status: Optional status component.
    status_id: Optional ID for the status component.
    container_id: Optional ID for the container component.
    fluid: Whether the container should be fluid (full width).

  Returns:
    A dmc.Container with standard sizing and padding.
  """
  container_kwargs = {"size": "xl", "py": "xl", "fluid": fluid}
  if container_id:
    container_kwargs["id"] = container_id

  return dmc.Container(
      **container_kwargs,
      children=[
          render_page_header(
              title=title,
              description=description,
              actions=actions,
              breadcrumbs=breadcrumbs,
              title_id=title_id,
              description_id=description_id,
              actions_id=actions_id,
              breadcrumbs_id=breadcrumbs_id,
              status=status,
              status_id=status_id,
          ),
          *(children or []),
      ],
  )
