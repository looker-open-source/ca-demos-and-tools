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

"""Regenerated suggestions keep their reasoning.

regenerate_suggestions_async was the only writer of suggested_assertions that
built the row by hand instead of calling schema_to_suggested_model. It dumped
everything except id, type and weight into params, so the model's reasoning
landed in the JSON blob and the reasoning column stayed NULL.

The read path then made the NULL win. AssertionSchema.flatten_params merges
params in and afterwards overwrites reasoning from the attribute whenever the
row has one, which SuggestedAssertion always does. So clicking Regenerate on a
trial's suggestions returned every card with a blank reasoning line, with the
text still in the row and unreachable through the schema.
"""

from unittest import mock

from prism.client import run_client
from prism.common.schemas import assertion as assertion_schemas
from prism.common.schemas.agent import AgentConfig
from prism.server.models.assertion import SuggestedAssertion
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.repositories.trial_repository import TrialRepository
from prism.server.services.snapshot_service import SnapshotService
from sqlalchemy import orm

_REASONING = "The trace shows the model quoting a figure from the result set."


class _ImmediateThread:
  """Runs the target on the calling thread, so the test can assert after it."""

  def __init__(self, target):
    self._target = target

  def start(self):
    self._target()


def _make_trial(session: orm.Session):
  """A trial with no suggestions yet, for regenerate to fill."""
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
  return trial_repo.create(run.id, snapshot.examples[0].id)


def _regenerate(monkeypatch, session_factory, trial_id, suggestions):
  """Points the regenerate thread at the test database and a canned LLM."""
  service = mock.MagicMock()
  service.suggest_assertions.return_value = suggestions

  monkeypatch.setattr(run_client, "SessionLocal", session_factory)
  monkeypatch.setattr(run_client, "GenAIClient", mock.MagicMock())
  monkeypatch.setattr(
      run_client, "SuggestionService", mock.MagicMock(return_value=service)
  )
  monkeypatch.setattr(run_client.threading, "Thread", _ImmediateThread)

  run_client.RunsClient().regenerate_suggestions_async(
      trial_id=trial_id, app=mock.MagicMock()
  )


def test_regenerate_writes_the_reasoning_to_its_column_not_into_params(
    db_session: orm.Session, session_factory, monkeypatch
):
  """The row the LLM produced has to come back out with its reasoning."""
  trial = _make_trial(db_session)
  suggestion = assertion_schemas.TextContains(
      value="gross margin", reasoning=_REASONING
  )

  _regenerate(monkeypatch, session_factory, trial.id, [suggestion])

  db_session.expire_all()
  rows = (
      db_session.query(SuggestedAssertion)
      .filter(SuggestedAssertion.trial_id == trial.id)
      .all()
  )
  assert len(rows) == 1
  assert rows[0].reasoning == _REASONING
  assert "reasoning" not in rows[0].params


def test_the_regenerated_row_reads_back_through_the_schema_with_reasoning(
    db_session: orm.Session, session_factory, monkeypatch
):
  """The column, not the params copy, is what flatten_params reads.

  Asserting on the row alone would pass on a writer that filled both, which is
  not what the mapper does and not what the UI reads.
  """
  trial = _make_trial(db_session)
  suggestion = assertion_schemas.TextContains(
      value="gross margin", reasoning=_REASONING
  )

  _regenerate(monkeypatch, session_factory, trial.id, [suggestion])

  db_session.expire_all()
  row = (
      db_session.query(SuggestedAssertion)
      .filter(SuggestedAssertion.trial_id == trial.id)
      .one()
  )
  schema = assertion_schemas.TextContains.model_validate(row)
  assert schema.reasoning == _REASONING
  assert schema.value == "gross margin"
