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

"""The numbers on summary badges, and what they are counting.

Both of these badges sit above the thing they describe, so a reader checks one
against the other. The suite card's count was never pluralised, and the
profiling badge counted a list the chart under it had already filtered.
"""

from __future__ import annotations

import datetime

from prism.common.schemas.example import Example
from prism.common.schemas.suite import SuiteDetail
from prism.ui.components import charts
from prism.ui.components import eval_run_modal
import pytest

_NOW = datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc)


def _suite(case_count: int) -> SuiteDetail:
  """A suite holding ``case_count`` unasserted test cases."""
  return SuiteDetail(
      id=1,
      name="A suite",
      created_at=_NOW,
      examples=[
          Example(
              id=i,
              test_suite_id=1,
              logical_id=f"tc-{i}",
              question=f"Question {i}?",
              created_at=_NOW,
          )
          for i in range(case_count)
      ],
  )


@pytest.mark.parametrize(
    "case_count,expected", [(1, "1 test case"), (2, "2 test cases")]
)
def test_the_suite_card_pluralises_its_test_case_count(case_count, expected):
  """A one-case suite read "1 test cases" in the Run Evaluation modal.

  The count was an unconditional f-string. A suite with one case is the normal
  way to start, so this was the first thing a new user saw in that modal.
  """
  rendered = str(eval_run_modal.render_suite_card(_suite(case_count)))

  assert expected in rendered
  if case_count == 1:
    assert "1 test cases" not in rendered


def test_the_profiling_badge_counts_the_bars_it_labels():
  """The badge counted every tool, the chart drew only the non-zero ones.

  A trial that called a tool which returned in under a millisecond showed a
  badge saying "3 tools" over two bars, and nothing on the card explained the
  missing one.
  """
  rendered = str(
      charts.render_trial_profiling({"slow": 800, "quick": 200, "idle": 0})
  )

  assert "2 tools" in rendered
  assert "3 tools" not in rendered
