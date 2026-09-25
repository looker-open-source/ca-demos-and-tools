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

import time
import unittest.mock

from google.api_core import exceptions as api_exceptions
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.common.schemas.agent import LookerConfig
from prism.server.clients.gemini_data_analytics_client import AskQuestionResponse
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
from prism.server.models.run import RunStatus
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.repositories.trial_repository import TrialRepository
from prism.server.services.execution_service import ExecutionService
from prism.server.services.snapshot_service import SnapshotService
import pytest
from sqlalchemy.orm import Session


def test_create_run_service(db_session: Session):
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  mock_client = unittest.mock.MagicMock(spec=GeminiDataAnalyticsClient)
  mock_client.get_agent_context.return_value = {"system_instruction": "Test"}

  service = ExecutionService(
      db_session,
      snapshot_service,
      mock_client,
  )

  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      datasource=BigQueryConfig(tables=["t1"]),
  )
  agent = agent_repo.create(name="Execute Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")

  run = service.create_run(agent.id, suite.id)

  assert run.id is not None
  # Stored raw, exactly as the client reported it, with no wrapper key.
  assert run.agent_context_snapshot == {"system_instruction": "Test"}
  # project_id and location live on the run model, so the snapshot does not
  # repeat them.

  assert len(run.trials) == 1
  assert run.trials[0].example_snapshot.question == "Q1"


def test_execute_run_service(db_session: Session):
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  mock_client = unittest.mock.MagicMock(spec=GeminiDataAnalyticsClient)
  mock_client.get_agent_context.return_value = {"system_instruction": "Test"}
  response_mock = unittest.mock.MagicMock(spec=AskQuestionResponse)
  response_mock.protobuf_response = []
  response_mock.duration = unittest.mock.MagicMock(total_duration=123)
  response_mock.error_message = None
  mock_client.ask_question.return_value = response_mock

  service = ExecutionService(
      db_session,
      snapshot_service,
      mock_client,
  )

  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      datasource=BigQueryConfig(tables=["t1"]),
  )
  agent = agent_repo.create(name="Execute Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")

  run = service.create_run(agent.id, suite.id)

  for trial in run.trials:
    service.execute_trial(trial.id)

  db_session.refresh(run)
  assert len(run.trials) == 1
  trial = run.trials[0]
  assert trial.status == RunStatus.COMPLETED
  assert trial.duration_ms is not None

  mock_client.ask_question.assert_called_once()
  call_args = mock_client.ask_question.call_args[1]
  assert call_args["question"] == "Q1"
  assert call_args["agent_id"] == "projects/p/locations/l/dataAgents/r"


# How long the stand-in judge takes, and the bound the trial has to stay
# under. The agent call is a mock that returns at once, so the honest duration
# is a couple of milliseconds. Half the sleep is a wide margin either way.
_SLOW_JUDGE_SECONDS = 0.5
_DURATION_BOUND_MS = _SLOW_JUDGE_SECONDS * 1000 / 2


def test_the_trial_duration_is_the_agent_and_not_the_evaluation(
    db_session: Session,
):
  """completed_at is stamped when the agent answers, before the assertions run.

  Assertions include AI judges, which take seconds. Stamping after them folds
  the judge's round trip into every reported latency, and latency is what the
  duration assertions and the dashboard chart are reading.
  """
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  mock_client = unittest.mock.MagicMock(spec=GeminiDataAnalyticsClient)
  mock_client.get_agent_context.return_value = {"system_instruction": "Test"}
  response_mock = unittest.mock.MagicMock(spec=AskQuestionResponse)
  response_mock.protobuf_response = []
  response_mock.error_message = None
  mock_client.ask_question.return_value = response_mock

  service = ExecutionService(db_session, snapshot_service, mock_client)

  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      datasource=BigQueryConfig(tables=["t1"]),
  )
  agent = agent_repo.create(name="Slow Judge Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")
  run = service.create_run(agent.id, suite.id)

  def slow_evaluate_all(**_kwargs):
    time.sleep(_SLOW_JUDGE_SECONDS)
    return []

  with unittest.mock.patch(
      "prism.server.services.execution_service.assert_engine.evaluate_all",
      side_effect=slow_evaluate_all,
  ) as evaluate_all:
    service.execute_trial(run.trials[0].id)

  evaluate_all.assert_called_once()
  trial = run.trials[0]
  assert trial.status == RunStatus.COMPLETED
  assert trial.duration_ms is not None
  assert trial.duration_ms < _DURATION_BOUND_MS


def test_a_failed_trial_records_the_stage_and_no_traceback(
    db_session: Session,
):
  """The stage is kept on the trial and the traceback is not.

  Nothing in the suite checks traceback capture, because there is none to
  check: error_traceback is nulled on purpose. The page has no authentication
  and used to render the traceback under an accordion on the trial detail
  page, next to a GDA error naming the project, the dataAgents path, the
  Looker instance and the caller service account. The old name promised the
  opposite of what the assertions check, so an audit of traceback capture
  read this as a green test for a guarantee the suite never makes.
  """
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  mock_client = unittest.mock.MagicMock(spec=GeminiDataAnalyticsClient)
  mock_client.get_agent_context.return_value = {"system_instruction": "Test"}
  mock_client.ask_question.side_effect = Exception("Agent Explosion!")

  service = ExecutionService(
      db_session,
      snapshot_service,
      mock_client,
  )

  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      datasource=BigQueryConfig(tables=["t1"]),
  )
  agent = agent_repo.create(name="Fail Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")
  run = service.create_run(agent.id, suite.id)

  # Not wrapped in try/except, and not allowed to be. execute_trial owns the
  # failure: it records the stage on the trial and returns.
  # worker.execute_trial wraps this call in a handler that writes
  # failed_stage="SETUP", so a re-raise would replace EXECUTING with SETUP and
  # the page would name the wrong stage. Catching the raise here is what let
  # that through unnoticed.
  service.execute_trial(run.trials[0].id)

  trial_repo = TrialRepository(db_session)
  trials = trial_repo.list_for_run(run.id)
  trial = trials[0]

  assert trial.status == RunStatus.FAILED
  assert trial.failed_stage == "EXECUTING"
  # The exception text and the traceback go to the log, not onto the trial.
  # The page has no authentication, and the traceback was rendered under an
  # accordion on the trial detail page.
  assert "Agent Explosion!" not in trial.error_message
  assert "Exception raised while running this trial." in trial.error_message
  assert trial.error_traceback is None


def _service(db_session: Session, kind: str | None) -> ExecutionService:
  """An ExecutionService whose agent reports ``kind`` as its datasource."""
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  mock_client = unittest.mock.MagicMock(spec=GeminiDataAnalyticsClient)
  mock_client.get_agent_context.return_value = {"system_instruction": "Test"}
  mock_client.get_datasource_kind.return_value = kind
  return ExecutionService(
      db_session,
      SnapshotService(db_session, suite_repo, example_repo),
      mock_client,
  )


def _agent_and_suite(db_session: Session, **config_kwargs):
  """One agent and a one question suite to run it against."""
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)

  config = AgentConfig(
      project_id="p", location="l", agent_resource_id="r", **config_kwargs
  )
  agent = agent_repo.create(name="Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")
  return agent, suite


def test_a_looker_agent_with_no_credentials_cannot_start_a_run(db_session):
  """Prism sends the credentials, so the run stops before the trials do."""
  service = _service(db_session, "looker")
  agent, suite = _agent_and_suite(db_session)

  with pytest.raises(ValueError, match="Client ID and Secret"):
    service.create_run(agent.id, suite.id)


def test_a_looker_agent_with_credentials_starts_a_run(db_session):
  """The check is on the credentials, not on the datasource being Looker."""
  service = _service(db_session, "looker")
  agent, suite = _agent_and_suite(
      db_session,
      datasource=LookerConfig(instance_uri="https://x.looker.com", explores=[]),
      looker_client_id="a-client-id",
      looker_client_secret="a-secret",
  )

  run = service.create_run(agent.id, suite.id)

  assert run.id is not None


def test_an_agent_with_no_datasource_cannot_start_a_run(db_session):
  """Every trial of that run fails at the service with REFERENCES_NOT_SET."""
  service = _service(db_session, None)
  agent, suite = _agent_and_suite(db_session)

  with pytest.raises(ValueError, match="no datasource"):
    service.create_run(agent.id, suite.id)


def test_a_datasource_prism_does_not_parse_starts_a_run(db_session):
  """Those agents answer questions, and prism stores no config for them.

  The kind is read from the service for this reason. Reading prism's own copy
  would make this agent indistinguishable from one with no datasource.
  """
  service = _service(db_session, "studio")
  agent, suite = _agent_and_suite(db_session)

  run = service.create_run(agent.id, suite.id)

  assert run.id is not None
  assert agent.datasource_config is None


def test_a_suite_whose_questions_are_all_archived_will_not_run(db_session):
  """The empty suite guard reads the set the snapshot is going to take.

  It used to read suite.examples, the unfiltered backref, while
  create_snapshot goes through list_by_suite_id, which filters the archived
  ones out. A suite whose questions had all been archived passed the guard
  and then snapshotted to nothing, leaving a run with no trials.
  """
  service = _service(db_session, "bigquery")
  agent, suite = _agent_and_suite(
      db_session, datasource=BigQueryConfig(tables=["t1"])
  )
  example_repo = ExampleRepository(db_session)
  for example in example_repo.list_by_suite_id(suite.id):
    example_repo.archive(example.id)

  with pytest.raises(ValueError, match="has no active questions"):
    service.create_run(agent.id, suite.id)


def test_a_suite_with_one_question_left_unarchived_still_runs(db_session):
  """Archiving some of the questions leaves a run over the rest.

  Only a suite with nothing active is rejected. The trials come from the same
  filtered set as the guard, so the archived question gets no trial.
  """
  service = _service(db_session, "bigquery")
  agent, suite = _agent_and_suite(
      db_session, datasource=BigQueryConfig(tables=["t1"])
  )
  example_repo = ExampleRepository(db_session)
  example_repo.create(suite.id, "Q2")
  example_repo.archive(example_repo.list_by_suite_id(suite.id)[0].id)

  run = service.create_run(agent.id, suite.id)

  assert len(run.trials) == 1
  assert run.trials[0].example_snapshot.question == "Q2"


def test_a_datasource_read_that_fails_does_not_stop_a_run(db_session):
  """An agent can be added by typing a resource id the caller cannot read."""
  service = _service(db_session, None)
  service.client.get_datasource_kind.side_effect = (
      api_exceptions.PermissionDenied("nope")
  )
  agent, suite = _agent_and_suite(db_session)

  run = service.create_run(agent.id, suite.id)

  assert run.id is not None


def test_a_running_trial_always_has_a_start_time(db_session):
  """The stale sweep selects on started_at, and NULL never matches it.

  Execution used to clear started_at alongside the other per-attempt fields,
  and it commits that row before it sets EXECUTING. A trial that wedged in
  between was RUNNING with no start time, so the sweep could not see it, and
  it held its run's capacity for good.
  """
  service = _service(db_session, "bigquery")
  agent, suite = _agent_and_suite(
      db_session, datasource=BigQueryConfig(tables=["t1"])
  )
  response = unittest.mock.MagicMock(spec=AskQuestionResponse)
  response.protobuf_response = []
  response.duration = unittest.mock.MagicMock(total_duration=1)
  response.error_message = None
  service.client.ask_question.return_value = response

  run = service.create_run(agent.id, suite.id)
  trial = TrialRepository(db_session).pick_next_pending_trial(run_id=run.id)
  assert trial is not None

  # Every commit execution makes, not just the row it leaves behind. The gap
  # this covers is two commits wide and the second one fills the column in.
  seen = []
  real_commit = db_session.commit

  def record_then_commit():
    seen.append((trial.status, trial.started_at))
    real_commit()

  with unittest.mock.patch.object(
      db_session, "commit", side_effect=record_then_commit
  ):
    service.execute_trial(trial.id)

  assert seen
  assert [status for status, start in seen if start is None] == []


def test_a_trial_that_failed_in_the_agent_call_has_an_end_time(db_session):
  """A FAILED trial used to be committed with completed_at still NULL.

  The attempt clears completed_at and only the agent call stamps it, so a
  trial that died in the call had a start and no end. Nothing later fixed it:
  the worker only retries trials that are still in flight, and this one is
  terminal. Trial.duration_ms was None, so the trial dropped out of the agent
  dashboard's average duration and out of durations_by_day, and the BigQuery
  export wrote both duration_ms and completed_at NULL.
  """
  service = _service(db_session, "bigquery")
  agent, suite = _agent_and_suite(
      db_session, datasource=BigQueryConfig(tables=["t1"])
  )
  service.client.ask_question.side_effect = Exception("Agent Explosion!")
  run = service.create_run(agent.id, suite.id)

  service.execute_trial(run.trials[0].id)

  trial = TrialRepository(db_session).list_for_run(run.id)[0]
  assert trial.status == RunStatus.FAILED
  assert trial.completed_at is not None
  assert trial.duration_ms is not None


def test_a_failure_in_the_assertions_keeps_the_end_of_the_agent_call(
    db_session,
):
  """A trial ends when the agent answered, whether or not it then failed.

  The failure path fills completed_at in only when it is still NULL. Stamping
  a fresh one would fold the judge's round trip into the latency of a trial
  whose agent call had already returned, which is what the stamp after
  ask_question exists to avoid.
  """
  service = _service(db_session, "bigquery")
  agent, suite = _agent_and_suite(
      db_session, datasource=BigQueryConfig(tables=["t1"])
  )
  response = unittest.mock.MagicMock(spec=AskQuestionResponse)
  response.protobuf_response = []
  response.duration = unittest.mock.MagicMock(total_duration=1)
  response.error_message = None
  service.client.ask_question.return_value = response
  run = service.create_run(agent.id, suite.id)

  def slow_failing_evaluate_all(**_kwargs):
    time.sleep(_SLOW_JUDGE_SECONDS)
    raise RuntimeError("The judge fell over")

  with unittest.mock.patch(
      "prism.server.services.execution_service.assert_engine.evaluate_all",
      side_effect=slow_failing_evaluate_all,
  ):
    service.execute_trial(run.trials[0].id)

  trial = TrialRepository(db_session).list_for_run(run.id)[0]
  assert trial.status == RunStatus.FAILED
  assert trial.duration_ms is not None
  assert trial.duration_ms < _DURATION_BOUND_MS
