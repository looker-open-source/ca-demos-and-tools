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

"""Reusable badge components."""

import dash_mantine_components as dmc


def render_status_badge(label: str, color: str, size: str = "sm") -> dmc.Badge:
  """Renders a standardized status badge.

  Args:
      label: The text to display in the badge.
      color: The Mantine color to use.
      size: The size of the badge.

  Returns:
      A styled dmc.Badge component.
  """
  return dmc.Badge(
      label,
      color=color,
      variant="light",
      radius="md",
      size=size,
      tt="uppercase",
      fw=700,
      # Specific styles to match the mockup's high-density look
      style={
          "border": "none",
          "padding": "0 10px",
          "height": "24px" if size == "sm" else "32px",
      },
  )


def render_coverage_badge(
    label: str, color: str, size: str = "sm"
) -> dmc.Tooltip:
  """Renders a coverage badge with an explanatory tooltip.

  Args:
      label: The coverage label (Full, Partial, No).
      color: The badge color.
      size: The badge size.

  Returns:
      A dmc.Tooltip wrapping the badge.
  """
  descriptions = {
      "Full Coverage": (
          "All test cases in this test suite have at least one assertion."
      ),
      "Partial Coverage": (
          "Some test cases in this test suite have assertions, but some do not."
      ),
      "No Coverage": (
          "None of the test cases in this test suite have assertions."
      ),
      "No Test Cases": "This test suite does not contain any test cases.",
  }

  help_text = descriptions.get(label, "Assertion coverage for this test suite.")

  return dmc.Tooltip(
      label=help_text,
      position="top",
      withArrow=True,
      children=render_status_badge(label, color, size),
  )
