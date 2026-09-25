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

"""Tests for regenerating the suggested assertions of a trial.

suggest_assertions turns an LLM error into an empty list, and the regenerate
path used to delete the stored SuggestedAssertion rows before it called out.
A failed regenerate then wiped the suggestions the user already had and left
them with an empty panel and nothing to restore it from. The order is now
generate first, keep what is stored when nothing comes back, replace it when
something does.
"""

import logging
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


class _ImmediateThread:
  """Runs the target on the calling thread, so the test can assert after it."""

  def __init__(self, target):
    self._target = target

  def start(self):
    self._target()


def _make_trial_with_suggestions(session: orm.Session):
  """Builds a trial that already carries two stored suggestions."""
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

  for value in ("revenue", "2024"):
    session.add(
        SuggestedAssertion(
            trial_id=trial.id,
            type=assertion_schemas.AssertionType.TEXT_CONTAINS,
            weight=1.0,
            params={"value": value},
        )
    )
  session.commit()
  return trial


def _patch_background_work(monkeypatch, session_factory, suggestions):
  """Points the regenerate thread at the test database and a canned LLM."""
  service = mock.MagicMock()
  service.suggest_assertions.return_value = suggestions

  monkeypatch.setattr(run_client, "SessionLocal", session_factory)
  monkeypatch.setattr(run_client, "GenAIClient", mock.MagicMock())
  monkeypatch.setattr(
      run_client, "SuggestionService", mock.MagicMock(return_value=service)
  )
  monkeypatch.setattr(run_client.threading, "Thread", _ImmediateThread)


def _stored_values(session: orm.Session, trial_id: int) -> list[str]:
  session.expire_all()
  rows = (
      session.query(SuggestedAssertion)
      .filter(SuggestedAssertion.trial_id == trial_id)
      .order_by(SuggestedAssertion.id)
      .all()
  )
  return [row.params["value"] for row in rows]


def test_regenerate_that_returns_nothing_keeps_the_stored_suggestions(
    db_session: orm.Session, session_factory, monkeypatch, caplog
):
  trial = _make_trial_with_suggestions(db_session)
  _patch_background_work(monkeypatch, session_factory, [])

  with caplog.at_level(logging.WARNING, logger=run_client.__name__):
    run_client.RunsClient().regenerate_suggestions_async(
        trial_id=trial.id, app=mock.MagicMock()
    )

  assert _stored_values(db_session, trial.id) == ["revenue", "2024"]
  assert "keeping the existing ones" in caplog.text


def test_regenerate_that_returns_suggestions_replaces_the_stored_ones(
    db_session: orm.Session, session_factory, monkeypatch
):
  trial = _make_trial_with_suggestions(db_session)
  fresh = [assertion_schemas.TextContains(value="gross margin")]
  _patch_background_work(monkeypatch, session_factory, fresh)

  run_client.RunsClient().regenerate_suggestions_async(
      trial_id=trial.id, app=mock.MagicMock()
  )

  # Without this the test above would pass on a method that never deletes.
  assert _stored_values(db_session, trial.id) == ["gross margin"]
