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

"""How an assertion result is allowed to look on screen.

Accuracy and diagnostic assertions both report PASS or FAIL, but only accuracy
moves the run's score. A customer reading the trial detail table could not tell
them apart, because STATUS was computed from ``passed`` alone and the category
next to it was plain text. These tests pin the distinction down: the four
combinations have to be four distinct badges.
"""

from __future__ import annotations

from typing import Any, Iterator

import dash_mantine_components as dmc
from prism.ui.components import assertion_components
import pytest


def _walk(component: Any) -> Iterator[Any]:
  """Yields every component in a rendered tree, depth first.

  The renderers nest badges several layers inside Tables, Tooltips and Groups,
  and the depth is not what is under test.
  """
  yield component
  children = getattr(component, "children", None)
  if children is None:
    return
  if not isinstance(children, (list, tuple)):
    children = [children]
  for child in children:
    if child is not None and not isinstance(child, (str, int, float)):
      yield from _walk(child)


def _badges(component: Any, *labels: str) -> list[dmc.Badge]:
  """Every Badge in the tree whose label is one of ``labels``."""
  return [
      c
      for c in _walk(component)
      if isinstance(c, dmc.Badge) and _label(c) in labels
  ]


def _label(badge: dmc.Badge) -> str:
  """The text of a badge, whether or not it carries a leading icon."""
  children = badge.children
  if isinstance(children, (list, tuple)):
    return next((c for c in children if isinstance(c, str)), "")
  return children


def _result(passed: bool, weight: float) -> dict[str, Any]:
  """One row of the trial detail assertion table."""
  return {
      "type": "text-contains",
      "value": "revenue",
      "passed": passed,
      "weight": weight,
      "reasoning": "because",
  }


# The four states, and the badge each one has to produce. Weight is what makes
# an assertion accuracy or diagnostic; there is no separate flag.
_ACCURACY_PASS = (True, 1.0, "teal", "filled")
_ACCURACY_FAIL = (False, 1.0, "red", "filled")
_DIAGNOSTIC_PASS = (True, 0.0, "gray", "outline")
_DIAGNOSTIC_FAIL = (False, 0.0, "orange", "outline")
_ALL_STATES = [
    _ACCURACY_PASS,
    _ACCURACY_FAIL,
    _DIAGNOSTIC_PASS,
    _DIAGNOSTIC_FAIL,
]


@pytest.mark.parametrize(
    "weight,expected",
    [
        (1.0, True),
        (0.5, True),
        (0.0, False),
        (0, False),
        (None, False),
        ("", False),
    ],
)
def test_only_a_positive_weight_is_an_accuracy_assertion(weight, expected):
  """Weight comes off a JSON store, so it arrives as whatever was stored.

  A None or an empty string reaching ``weight > 0`` is a TypeError, which
  ``handle_errors`` turns into a toast and an unrendered page.
  """
  assert assertion_components.is_accuracy_assertion(weight) is expected


@pytest.mark.parametrize("passed,weight,color,variant", _ALL_STATES)
def test_each_state_gets_its_own_badge(passed, weight, color, variant):
  """Four states, four badges."""
  is_accuracy = assertion_components.is_accuracy_assertion(weight)
  badge = assertion_components.render_assertion_status_badge(
      passed, is_accuracy
  )

  assert _label(badge) == ("PASS" if passed else "FAIL")
  assert badge.color == color
  assert badge.variant == variant


def test_no_two_states_look_alike():
  """The point of the change. Colour alone did not separate all four.

  Without the variant, a diagnostic PASS and an accuracy PASS differ only by
  colour, and the customer's complaint was that the failures looked the same.
  """
  looks = set()
  for passed, weight, _, _ in _ALL_STATES:
    badge = assertion_components.render_assertion_status_badge(
        passed, assertion_components.is_accuracy_assertion(weight)
    )
    looks.add((_label(badge), badge.color, badge.variant))

  assert len(looks) == 4, looks


def test_a_diagnostic_failure_is_not_red():
  """Red is the run-is-broken colour, and a diagnostic failure is not that.

  Diagnostic assertions are monitoring. One failing does not move the score,
  so it must not read like a failed accuracy check.
  """
  diagnostic = assertion_components.render_assertion_status_badge(False, False)
  accuracy = assertion_components.render_assertion_status_badge(False, True)

  assert diagnostic.color != "red"
  assert accuracy.color == "red"


@pytest.mark.parametrize("passed,weight,color,variant", _ALL_STATES)
def test_the_trial_detail_table_uses_the_shared_badge(
    passed, weight, color, variant
):
  """The page the customer was looking at.

  ``render_assertion_results_table`` had its own inline teal/red, which is how
  it drifted from the rest of the app in the first place.
  """
  table = assertion_components.render_assertion_results_table(
      [_result(passed, weight)]
  )

  status = _badges(table, "PASS", "FAIL")
  assert len(status) == 1, f"expected one status badge, got {len(status)}"
  assert status[0].color == color
  assert status[0].variant == variant


@pytest.mark.parametrize(
    "weight,label", [(1.0, "Accuracy"), (0.0, "Diagnostic")]
)
def test_the_table_renders_the_category_as_a_badge(weight, label):
  """It was a bare dmc.Text, while the suite questions page used a badge.

  Two pages showing the same property two different ways is what made the
  category easy to miss.
  """
  table = assertion_components.render_assertion_results_table(
      [_result(True, weight)]
  )

  category = _badges(table, "Accuracy", "Diagnostic")
  assert len(category) == 1, f"expected one category badge, got {len(category)}"
  assert _label(category[0]) == label


def test_the_table_still_renders_every_column():
  """The badge change must not have cost the row its other cells."""
  table = assertion_components.render_assertion_results_table(
      [_result(False, 1.0)]
  )
  rendered = str(table)

  for expected in ("STATUS", "CATEGORY", "TYPE", "VALUE", "REASONING"):
    assert expected in rendered, f"{expected} column is gone"
  assert "because" in rendered, "the reasoning is gone"
