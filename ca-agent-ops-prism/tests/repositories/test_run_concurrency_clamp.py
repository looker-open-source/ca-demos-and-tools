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

"""Run.concurrency is bounded server-side.

The value comes from a Dash NumberInput whose min=1 and max=100 are client-side
props, and nothing between the callback and the column checked it. The worker
does `for _ in range(capacity)` and spawns a subprocess per iteration, so a
hand-built POST carrying concurrency 50000 took the instance down. Even the
nominal UI maximum of 100 concurrent Python interpreters is past what one
instance survives.

RunRepository.create is the clamp site because it is the one place every writer
of a run row passes through.
"""

from prism.common.schemas.agent import AgentConfig
from prism.server.repositories import run_repository
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.snapshot_service import SnapshotService
import pytest
from sqlalchemy.orm import Session


def _snapshot_and_agent(session: Session):
  agent_repo = AgentRepository(session)
  suite_repo = SuiteRepository(session)
  example_repo = ExampleRepository(session)
  snapshot_service = SnapshotService(session, suite_repo, example_repo)

  config = AgentConfig(project_id="p", location="l", agent_resource_id="r")
  agent = agent_repo.create(name="Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")
  return snapshot_service.create_snapshot(suite.id), agent


@pytest.mark.parametrize("requested", [50000, 101, 100])
def test_a_concurrency_above_the_ceiling_is_clamped_to_it(
    db_session: Session, requested
):
  """50000 is the reported POST. 100 is the nominal UI maximum."""
  snapshot, agent = _snapshot_and_agent(db_session)

  run = run_repository.RunRepository(db_session).create(
      snapshot.id, agent.id, concurrency=requested
  )

  db_session.expire_all()
  assert run.concurrency == run_repository.MAX_CONCURRENCY


@pytest.mark.parametrize("requested", [0, -1])
def test_a_concurrency_below_one_is_clamped_to_one(
    db_session: Session, requested
):
  """A run with capacity zero never starts a trial and never completes."""
  snapshot, agent = _snapshot_and_agent(db_session)

  run = run_repository.RunRepository(db_session).create(
      snapshot.id, agent.id, concurrency=requested
  )

  db_session.expire_all()
  assert run.concurrency == 1


def test_a_concurrency_inside_the_range_is_stored_as_asked(
    db_session: Session,
):
  """Guards the clamp.

  One that clamped everything would pass the tests above.
  """
  snapshot, agent = _snapshot_and_agent(db_session)

  run = run_repository.RunRepository(db_session).create(
      snapshot.id, agent.id, concurrency=4
  )

  db_session.expire_all()
  assert run.concurrency == 4


def test_a_cleared_number_input_falls_back_to_the_default(
    db_session: Session,
):
  """A cleared NumberInput sends None, and the column is NOT NULL."""
  snapshot, agent = _snapshot_and_agent(db_session)

  run = run_repository.RunRepository(db_session).create(
      snapshot.id, agent.id, concurrency=None
  )

  db_session.expire_all()
  assert run.concurrency == 2
