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

"""Fixtures for driving the Dash app over HTTP.

The app is served by Flask, so a Flask test client reaches the real callback
dispatch route in-process. Nothing here starts a browser or a second server.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Iterator

from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.execution import RunStatus
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.repositories.trial_repository import TrialRepository
from prism.server.services.snapshot_service import SnapshotService
from prism.ui.app import app
import pytest
from sqlalchemy import orm


@pytest.fixture(name="dash_client")
def _dash_client(session_factory: orm.sessionmaker):
  """A Flask test client for the Dash app, on the test database.

  ``session_factory`` is only here for its side effects: it builds the schema
  and drops it again. The callbacks themselves reach the database through
  ``prism.client.dependencies.get_session``, which opens ``db.SessionLocal``.
  ``tests.db_guard.enforce()`` rebound that onto the test database at import,
  so no other wiring is needed.
  """
  del session_factory
  return app.server.test_client()


class _Collector(logging.Handler):
  """Keeps every record the UI logs at ERROR."""

  def __init__(self):
    super().__init__(level=logging.ERROR)
    self.records: list[logging.LogRecord] = []

  def emit(self, record: logging.LogRecord) -> None:
    self.records.append(record)


@dataclasses.dataclass
class CallbackErrors:
  """The errors a callback logged, and the assertion that there were none."""

  handler: _Collector

  @property
  def messages(self) -> list[str]:
    return [r.getMessage() for r in self.handler.records]

  def assert_none(self, context: str = "") -> None:
    """Fails with every logged error, plus ``context`` to locate it."""
    assert not self.handler.records, (
        f"callback(s) logged an error{' ' + context if context else ''}:\n  "
        + "\n  ".join(self.messages)
    )

  def assert_logged(self, fragment: str) -> None:
    """Consumes one error containing ``fragment``, and fails if none does.

    For a test that provoked the failure on purpose. Clearing without this
    would also pass when the callback swallowed the error and logged nothing,
    which is the case worth catching.
    """
    matches = [r for r in self.handler.records if fragment in r.getMessage()]
    assert (
        matches
    ), f"no error mentioning {fragment!r}. Logged:\n  " + "\n  ".join(
        self.messages
    )
    for record in matches:
      self.handler.records.remove(record)

  def clear(self) -> None:
    self.handler.records.clear()


@pytest.fixture(name="callback_errors")
def _callback_errors() -> Iterator[CallbackErrors]:
  """Captures errors a callback swallowed instead of returning.

  This is the logged half only. A callback with ``@handle_errors``
  (``prism.ui.utils.handle_errors``) logs the traceback and answers 200 with
  ``no_update``, which is indistinguishable from "nothing to do" unless the log
  is read. A callback without it propagates and the route answers 500, and
  nothing here sees that: ``dash_http.fire`` returns the response to the
  caller, so the caller is the one that has to assert ``status_code == 200``.
  """
  handler = _Collector()
  logger = logging.getLogger("prism")
  previous = logger.level
  # A caller's logging config could have raised this above ERROR, which would
  # make the gate pass by never seeing anything.
  if previous > logging.ERROR or previous == logging.NOTSET:
    logger.setLevel(logging.ERROR)
  logger.addHandler(handler)
  try:
    yield CallbackErrors(handler)
  finally:
    logger.removeHandler(handler)
    logger.setLevel(previous)


@dataclasses.dataclass
class Seeded:
  """Ids and names of the rows the pages should render."""

  agent_id: int
  agent_name: str
  suite_id: int
  suite_name: str
  run_id: int
  question: str


@pytest.fixture(name="seeded")
def _seeded(db_session: orm.Session) -> Seeded:
  """One agent, one suite, one snapshot and one run with three trials.

  Enough for every list page to have something to render. The names are
  distinctive so a test can tell a rendered row from an empty container.
  """
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)
  run_repo = RunRepository(db_session)
  trial_repo = TrialRepository(db_session)

  config = AgentConfig(project_id="p", location="l", agent_resource_id="r")
  agent = agent_repo.create(name="Seeded Agent", config=config)
  suite = suite_repo.create(name="Seeded Suite")
  question = "How many seeded orders are there?"
  example_repo.create(suite.id, question)

  snapshot = snapshot_service.create_snapshot(suite.id)
  example_snapshot_id = snapshot.examples[0].id

  run = run_repo.create(snapshot.id, agent.id)
  trial_repo.create(run.id, example_snapshot_id)
  running = trial_repo.create(run.id, example_snapshot_id)
  completed = trial_repo.create(run.id, example_snapshot_id)
  running.status = RunStatus.RUNNING
  completed.status = RunStatus.COMPLETED
  db_session.commit()

  return Seeded(
      agent_id=agent.id,
      agent_name=agent.name,
      suite_id=suite.id,
      suite_name=suite.name,
      run_id=run.id,
      question=question,
  )
