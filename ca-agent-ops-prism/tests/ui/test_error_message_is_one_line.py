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

r"""A stored error is rendered as its first line, wherever it is rendered.

The services compose that line on purpose: a short description of the failure
and a reference id that finds the rest in the server log. Anything after it is
whatever the raising code happened to put there, and prism has no
authentication, so the page it lands on is readable by anyone who can reach the
port and goes into the screenshots attached to bugs.

Two places render a trial's error. The trial page's error card kept the rest in
a Details block, and the comparison page printed the message whole. Both now go
through ``cards.error_summary_line``, so a message that grows a second line
cannot leak through one of them alone.

A message may arrive with a real newline or with an escaped one, depending on
which service composed it, so both forms are checked.

``tests/services/test_trial_error_redaction.py`` covers the traceback, which is
the other half of what the card used to render.
"""

from __future__ import annotations

import datetime

from prism.common.schemas.execution import RunStatus
from prism.common.schemas.execution import Trial
from prism.ui.callbacks import run_comparison_callbacks
from prism.ui.components import cards
import pytest

# The comparison page's renderer is private, and reaching it through the page
# means seeding two runs and a pair of trials, which tests the seeding.
# pylint: disable=protected-access
_trial_summary = run_comparison_callbacks._render_trial_summary
# pylint: enable=protected-access

_SUMMARY = "PermissionDenied raised while running this trial. (ref abc123)"

# The second line is the part that has no business being on a page. This is the
# detail blob a GDA permission failure carries.
_DETAIL = (
    "caller: prism-runner@secret-project.iam.gserviceaccount.com on"
    " projects/secret-project/locations/us/dataAgents/orders"
)


def _trial(error_message: str) -> Trial:
  """A failed trial carrying ``error_message``, as the page receives it."""
  return Trial(
      id=1,
      run_id=1,
      example_snapshot_id=1,
      status=RunStatus.FAILED,
      created_at=datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc),
      output_text="No answer was produced.",
      error_message=error_message,
  )


@pytest.fixture(name="message", params=["real", "escaped"])
def _message(request) -> str:
  """The two-line error, with the newline as stored by either service."""
  separator = "\n" if request.param == "real" else "\\n"
  return f"{_SUMMARY}{separator}{_DETAIL}"


def test_the_error_card_renders_the_first_line_only(message: str):
  """The card used to put the rest in a collapsible Details block.

  Collapsed is still rendered: the text is in the page source, and the block
  is one click from whoever is taking the screenshot.
  """
  rendered = str(cards.render_error_card(message=message, stage="EXECUTING"))

  assert _SUMMARY in rendered
  assert "secret-project" not in rendered
  assert "dataAgents" not in rendered
  assert "Details" not in rendered


def test_the_comparison_trial_summary_renders_the_same_line(message: str):
  """The comparison page was the one left printing the message whole.

  It shows two trials side by side, so a failure appears here as often as it
  does on the trial page.
  """
  rendered = str(_trial_summary(_trial(message), is_base=True))

  assert _SUMMARY in rendered
  assert "secret-project" not in rendered
  assert "dataAgents" not in rendered


def test_a_one_line_error_is_rendered_unchanged():
  """Trimming to the first line must not trim the ordinary case.

  Almost every stored error is one line, and the reference id is at the end of
  it. Losing that leaves the page with no way back to the log.
  """
  assert cards.error_summary_line(_SUMMARY) == _SUMMARY
  assert _SUMMARY in str(cards.render_error_card(message=_SUMMARY))


def test_a_trial_with_no_error_gets_no_alert():
  """Only a failure shows one, and an empty string is not a failure."""
  rendered = str(_trial_summary(_trial(""), is_base=False))

  assert "Trial Error" not in rendered
