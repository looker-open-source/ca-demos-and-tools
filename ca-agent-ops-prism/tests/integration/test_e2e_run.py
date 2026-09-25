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

"""End-to-end integration tests for Prism."""

import json
import os
import time
from unittest.mock import MagicMock
from unittest.mock import patch

from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.common.schemas.assertion import ChartCheckType
from prism.common.schemas.assertion import DataCheckRow
from prism.common.schemas.assertion import DataCheckRowCount
from prism.common.schemas.assertion import DurationMaxMs
from prism.common.schemas.assertion import LookerQueryMatch
from prism.common.schemas.assertion import QueryContains
from prism.common.schemas.assertion import TextContains
from prism.common.schemas.trace import AskQuestionResponse
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
from prism.server.clients.gen_ai_client import GenAIClient
from prism.server.models.run import RunStatus
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services import assert_engine
from prism.server.services.execution_service import ExecutionService
from prism.server.services.snapshot_service import SnapshotService
from sqlalchemy.orm import Session

# How long the assertion phase is made to take, and the bound the trial
# duration has to stay under. The agent call is a mock that returns at once, so
# the honest duration is a couple of milliseconds.
_SLOW_JUDGE_SECONDS = 0.5
_DURATION_BOUND_MS = _SLOW_JUDGE_SECONDS * 1000 / 2


class MockProtoMessage:
  """Mocks a proto-plus message wrapper."""

  def __init__(self, data_dict):
    self._data_dict = data_dict
    for k, v in data_dict.items():
      if isinstance(v, dict):
        setattr(self, k, MockProtoMessage(v))
      else:
        setattr(self, k, v)

    # ExecutionService reads ._pb, and the patched MessageToDict reads
    # data_dict back off it.
    self._pb = MagicMock()
    self._pb.data_dict = data_dict

  def __contains__(self, key):
    return key in self._data_dict

  def __getitem__(self, key):
    return self._data_dict[key]

  def __iter__(self):
    return iter(self._data_dict)

  def keys(self):
    return self._data_dict.keys()

  def values(self):
    return self._data_dict.values()

  def items(self):
    return self._data_dict.items()

  def to_dict(self):
    """Support for type(msg).to_dict(msg) usage."""
    return self._data_dict

  def get(self, key, default=None):
    return self._data_dict.get(key, default)


def load_mock_response(filename: str) -> list[dict]:
  """Loads a mock response from the data directory."""
  base_path = os.path.dirname(__file__)
  file_path = os.path.join(base_path, "data", filename)
  with open(file_path, "r", encoding="utf-8") as f:
    return json.load(f)


def _label(assertion) -> str:
  """Names an assertion in a way a failure message can be read.

  Weight is excluded because it is the same on all fourteen, and id because
  the schema objects below have not been stored yet.
  """
  return assertion.model_dump_json(exclude={"id", "weight"})


def test_successful_run_flow(db_session: Session):
  """Fourteen assertions, seven written to pass and seven to fail."""
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  mock_client = MagicMock(spec=GeminiDataAnalyticsClient)
  mock_client.get_agent_context.return_value = {"system_instruction": "Test"}

  mock_gen_ai_client = MagicMock(spec=GenAIClient)

  service = ExecutionService(
      db_session,
      snapshot_service,
      mock_client,
      gen_ai_client=mock_gen_ai_client,
  )

  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      datasource=BigQueryConfig(tables=["t1"]),
  )
  agent = agent_repo.create(name="E2E Agent", config=config)
  suite = suite_repo.create(name="Revenue Suite")

  # One of each assertion type, written to match success_response.json.
  written_to_pass = [
      TextContains(value="revenue"),
      DurationMaxMs(value=5000),
      QueryContains(value="SELECT *"),
      ChartCheckType(value="bar"),
      DataCheckRowCount(value=2),
      DataCheckRow(columns={"col": "val"}),
      LookerQueryMatch(params={"model": "the_model"}),
  ]
  # The same seven types against the same trace, written not to match.
  written_to_fail = [
      TextContains(value="this should fail"),
      DurationMaxMs(value=1),
      QueryContains(value="DELETE FROM"),
      ChartCheckType(value="line"),
      DataCheckRowCount(value=99),
      DataCheckRow(columns={"col": "does_not_exist"}),
      LookerQueryMatch(params={"model": "wrong_model"}),
  ]

  # ExampleRepository.create takes no assertions, so they go on one at a time.
  example = example_repo.create(suite.id, "What is the revenue?")
  labels = {}
  for assertion in written_to_pass + written_to_fail:
    stored = example_repo.add_assertion(example.id, assertion)
    labels[stored.id] = _label(assertion)

  trace_data = load_mock_response("success_response.json")

  real_evaluate_all = assert_engine.evaluate_all

  def slow_evaluate_all(**kwargs):
    """The fourteen real assertions, with an AI judge's latency in front."""
    time.sleep(_SLOW_JUDGE_SECONDS)
    return real_evaluate_all(**kwargs)

  with (
      # Patched instead of building real protos. The fixtures are already
      # dicts, so MockProtoMessage carries one through untouched.
      patch("google.protobuf.json_format.MessageToDict") as mock_to_dict,
      patch.object(
          assert_engine, "evaluate_all", side_effect=slow_evaluate_all
      ),
  ):
    mock_to_dict.side_effect = (
        lambda pb, **kwargs: pb.data_dict if hasattr(pb, "data_dict") else pb
    )

    response_mock = MagicMock(spec=AskQuestionResponse)
    response_mock.protobuf_response = [
        MockProtoMessage(item) for item in trace_data
    ]
    response_mock.error_message = None
    # A Duration-like object, so it needs total_duration in milliseconds.
    response_mock.duration = MagicMock()
    response_mock.duration.total_duration = 100

    mock_client.ask_question.return_value = response_mock

    run = service.create_run(agent.id, suite.id)
    for trial in run.trials:
      service.execute_trial(trial.id)

    db_session.refresh(run)
    assert len(run.trials) == 1
    trial = run.trials[0]

    assert trial.status == RunStatus.COMPLETED
    assert trial.duration_ms is not None
    # completed_at is stamped when the agent answers, before the assertions
    # run, so the slow judge above must leave no mark on the duration.
    assert trial.duration_ms < _DURATION_BOUND_MS

    # Which seven passed, not how many. Counting alone passed while the
    # matching and the non-matching assertion of a type swapped answers, which
    # is the way an assertion type breaks.
    outcomes = {
        labels[result.assertion_snapshot.original_assertion_id]: result.passed
        for result in trial.assertion_results
    }

    assert len(trial.assertion_results) == 14
    assert {l for l, ok in outcomes.items() if ok} == {
        _label(a) for a in written_to_pass
    }
    assert {l for l, ok in outcomes.items() if not ok} == {
        _label(a) for a in written_to_fail
    }
