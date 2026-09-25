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

"""Tests for the tool timings run_client hands the UI.

TimelineService spreads the gap between the last trace event and the end of
the trial over the final group, so the numbers only reflect the trial unless
the caller passes its real duration. run_client used to let total_duration_ms
default to 0, which pinned the trial's end to its last trace event. Everything
the agent spent after that event vanished from the breakdown, so the tool times
on a run detail page did not add up to the duration shown beside them. Every
call site that renders tool timings is covered here.
"""

import datetime
from unittest import mock

from prism.client import run_client
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.execution import RunStatus
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.repositories.trial_repository import TrialRepository
from prism.server.services.execution_service import ExecutionService
from prism.server.services.snapshot_service import SnapshotService
from prism.server.services.timeline_service import TimelineService
import pytest
from sqlalchemy import orm

_TRACE_START = datetime.datetime(
    2023, 10, 27, 10, 0, 0, tzinfo=datetime.timezone.utc
)
_TTFR_MS = 500
_DURATION_MS = 9000

_TRACE = [
    {
        "timestamp": "2023-10-27T10:00:00Z",
        "system_message": {
            "text": {"parts": ["Thinking..."], "text_type": "THOUGHT"}
        },
    },
    {
        "timestamp": "2023-10-27T10:00:01Z",
        "system_message": {"data": {"generated_sql": "SELECT * FROM table"}},
    },
    {
        "timestamp": "2023-10-27T10:00:02Z",
        "system_message": {"data": {"result": {"data": "some data"}}},
    },
    {
        "timestamp": "2023-10-27T10:00:03Z",
        "system_message": {
            "text": {"parts": ["Done"], "text_type": "FINAL_RESPONSE"}
        },
    },
]

# The thought plus the SQL that follows it (500 + 1000), the query result
# (1000), then the final response (1000) plus the 5500 ms between the last
# trace event and the end of a 9000 ms trial.
_EXPECTED_TIMINGS = {
    "Agent Reasoning - Data Query": 1500,
    "Data Query": 1000,
    "Final Response": 6500,
}

# The same trace when total_duration_ms defaults to 0: the trial ends at its
# last trace event, so the 5500 ms the agent was still working is charged to
# nothing.
_TIMINGS_WITHOUT_DURATION = {
    "Agent Reasoning - Data Query": 1500,
    "Data Query": 1000,
    "Final Response": 1000,
}


def _make_trial(session: orm.Session):
  """Builds a completed trial with a known trace and a known duration."""
  agent_repo = AgentRepository(session)
  suite_repo = SuiteRepository(session)
  example_repo = ExampleRepository(session)
  snapshot_service = SnapshotService(session, suite_repo, example_repo)
  run_repo = RunRepository(session)
  trial_repo = TrialRepository(session)

  config = AgentConfig(project_id="p", location="l", agent_resource_id="r")
  agent = agent_repo.create(name="Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")
  snapshot = snapshot_service.create_snapshot(suite.id)

  run = run_repo.create(snapshot.id, agent.id)
  trial = trial_repo.create(run.id, snapshot.examples[0].id)
  trial.status = RunStatus.COMPLETED
  # duration_ms and ttfr_ms are both derived. started_at sits _TTFR_MS before
  # the first trace event, so the timeline path (which measures the first gap
  # from started_at) and the others (which use ttfr_ms) see the same trace.
  trial.started_at = _TRACE_START - datetime.timedelta(milliseconds=_TTFR_MS)
  trial.completed_at = trial.started_at + datetime.timedelta(
      milliseconds=_DURATION_MS
  )
  trial.trace_results = _TRACE
  session.commit()
  return trial


def _from_get_run(session: orm.Session, trial):
  # get_run only reads the run repository, so the snapshot service and the
  # agent client it is built with are never touched.
  service = ExecutionService(session, mock.MagicMock(), mock.MagicMock())
  run = run_client.RunsClient().get_run(
      run_id=trial.run_id,
      service=service,
      timeline_service=TimelineService(),
  )
  return run.tool_timings


def _from_list_trials(session: orm.Session, trial):
  service = ExecutionService(session, mock.MagicMock(), mock.MagicMock())
  trials = run_client.RunsClient().list_trials(
      run_id=trial.run_id,
      service=service,
      timeline_service=TimelineService(),
  )
  return trials[0].tool_timings


def _from_get_trial(session: orm.Session, trial):
  fetched = run_client.RunsClient().get_trial(
      trial_id=trial.id,
      repo=TrialRepository(session),
      timeline_service=TimelineService(),
  )
  return fetched.tool_timings


def _from_get_trial_timeline(session: orm.Session, trial):
  timeline = run_client.RunsClient().get_trial_timeline(
      trial_id=trial.id,
      repo=TrialRepository(session),
      timeline_service=TimelineService(),
  )
  # The question is prepended as a group of its own, and it is not a tool.
  return {
      g.title: g.duration_ms for g in timeline.groups if g.title != "Question"
  }


@pytest.mark.parametrize(
    "call_site",
    [
        _from_get_run,
        _from_list_trials,
        _from_get_trial,
        _from_get_trial_timeline,
    ],
    ids=["get_run", "list_trials", "get_trial", "get_trial_timeline"],
)
def test_call_site_times_the_tools_against_the_real_trial_duration(
    call_site, db_session: orm.Session
):
  trial = _make_trial(db_session)

  timings = call_site(db_session, trial)

  # Checked before the equality below, not after it. After it the comparison
  # can only run on timings already known to equal _EXPECTED_TIMINGS, which
  # makes it constant-true and silent on the one regression it was written
  # for. First, it is the assertion that fires on that regression, and it says
  # so.
  assert timings != _TIMINGS_WITHOUT_DURATION, (
      "This call site let total_duration_ms default to 0. The trial ends at"
      " its last trace event and the final group gets 100 ms of padding"
      " instead of the rest of the trial."
  )
  assert timings == _EXPECTED_TIMINGS


def test_the_question_opens_the_timeline(db_session: orm.Session):
  """It was prepended to the events, which nothing reads.

  render_trace_timeline walks the groups, so the timeline opened on the agent's
  first step with no sign of what had been asked. The question lives on the
  example snapshot, not in the trace, so it is the only place it can come from.
  """
  trial = _make_trial(db_session)

  timeline = run_client.RunsClient().get_trial_timeline(
      trial_id=trial.id,
      repo=TrialRepository(db_session),
      timeline_service=TimelineService(),
  )

  first = timeline.groups[0]
  assert first.title == "Question"
  assert [e.content for e in first.events] == ["Q1"]
  # Zero, so it takes no width off the bars and adds nothing to the tool times.
  assert first.duration_ms == 0
