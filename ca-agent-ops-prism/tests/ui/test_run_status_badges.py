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

"""What a run or trial status looks like on screen.

``run_status_display`` is the single map three pages read, so a status missing
from it is a grey badge showing the raw enum name. Every member has to be in
it, and the badge has to keep uppercasing what it is handed: the labels are
stored in title case and the browser tests match the rendered text, not the
text in the DOM.
"""

from __future__ import annotations

from prism.common.schemas.execution import RunStatus
from prism.ui import utils
from prism.ui.components.badges import render_status_badge
from prism.ui.utils import run_status_display
import pytest

# Spelled out, not rederived from the map, so a relabelling has to be made
# here too. Every member is listed because a member missing from the map is
# the grey fallback, which reads as a crashed run.
_EXPECTED = {
    RunStatus.PENDING: ("gray", "Pending"),
    RunStatus.RUNNING: ("blue", "In Progress"),
    RunStatus.EXECUTING: ("blue", "Executing"),
    RunStatus.EVALUATING: ("blue", "Evaluating"),
    RunStatus.COMPLETED: ("green", "Completed"),
    RunStatus.FAILED: ("red", "Failed"),
    RunStatus.CANCELLED: ("gray", "Cancelled"),
    RunStatus.PAUSED: ("yellow", "Paused"),
}


@pytest.mark.parametrize("status", list(RunStatus))
def test_every_status_has_a_colour_and_a_label(status):
  """Every member is drawn as itself, not as the fallback."""
  assert run_status_display(status) == _EXPECTED[status]


def test_a_status_missing_from_the_map_is_grey_and_keeps_its_name(monkeypatch):
  """The fallback the three maps this replaced did not have.

  A member added to RunStatus and not added here is what this catches. Deleting
  the entry stands in for never having written it.
  """
  trimmed = dict(utils._RUN_STATUS_DISPLAY)  # pylint: disable=protected-access
  del trimmed[RunStatus.PAUSED]
  monkeypatch.setattr(utils, "_RUN_STATUS_DISPLAY", trimmed)

  assert run_status_display(RunStatus.PAUSED) == ("gray", "PAUSED")


def test_the_raw_string_reads_the_same_as_the_enum():
  """The dashboard rows come back as dicts, so the value arrives as a str.

  Asserted against a literal. RunStatus is a str enum, so a member and its own
  value are equal strings and comparing the two calls to each other passes
  whatever coercion the function does or does not do.
  """
  assert run_status_display("COMPLETED") == ("green", "Completed")
  assert run_status_display("PAUSED") == ("yellow", "Paused")


def test_an_unknown_status_stays_legible():
  """Nothing writes one today, but a grey badge beats a traceback."""
  assert run_status_display("wat") == ("gray", "wat")


def test_the_badge_uppercases_its_label():
  """The labels are title case and the badge is what shouts them.

  The browser tests read the DOM, which holds the title-case label, so this is
  the only place the uppercase the customer sees is pinned.
  """
  badge = render_status_badge("Completed", "green")

  assert badge.tt == "uppercase"
