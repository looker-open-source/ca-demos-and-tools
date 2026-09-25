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

"""Two workers picking a trial at the same time.

pick_next_pending_trial is the claim. Its subquery takes a row lock with
``skip_locked=True`` so the second worker takes the next trial instead of
queueing behind the first one's lock, and ``of=Trial`` so the joined run row is
not locked with it. Every test in test_worker_concurrency.py patches the method
out, so the statement itself had never run against two sessions.
"""

from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.execution import RunStatus
from prism.server.models.run import Trial
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.repositories.trial_repository import TrialRepository
from prism.server.services.snapshot_service import SnapshotService
import sqlalchemy
from sqlalchemy import orm


def _run_with_two_pending_trials(db_session: orm.Session):
  """Returns the run id and the two trial ids, oldest first."""
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)
  trial_repo = TrialRepository(db_session)

  agent = agent_repo.create(
      name="Bot",
      config=AgentConfig(project_id="p", location="l", agent_resource_id="r"),
  )
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")
  snapshot = snapshot_service.create_snapshot(suite.id)
  example_snapshot_id = snapshot.examples[0].id

  run = RunRepository(db_session).create(snapshot.id, agent.id)
  first = trial_repo.create(run.id, example_snapshot_id)
  second = trial_repo.create(run.id, example_snapshot_id)
  db_session.commit()

  return run.id, first.id, second.id


def test_a_locked_trial_is_skipped_rather_than_waited_on(
    db_session: orm.Session, session_factory: orm.sessionmaker
):
  """The second worker takes the next trial and does not block on the first.

  One session holds a row lock on the older trial, which is what the winner of
  a race holds between its SELECT and its commit. The other session then picks
  and has to come back with the other trial.
  """
  run_id, first_id, second_id = _run_with_two_pending_trials(db_session)

  holder = session_factory()
  claimer = session_factory()
  try:
    locked = holder.execute(
        sqlalchemy.select(Trial).where(Trial.id == first_id).with_for_update()
    ).scalar_one()
    assert locked.id == first_id

    # Without skip_locked the pick below waits on that lock until the holder
    # commits, which here is never. A lock timeout turns the hang into a
    # failure with a stack trace instead of a suite that has to be killed.
    claimer.execute(sqlalchemy.text("SET lock_timeout = '5s'"))
    claimed = TrialRepository(claimer).pick_next_pending_trial(run_id=run_id)

    assert claimed is not None, "the locked trial was not the only one on offer"
    assert claimed.id == second_id
    assert claimed.status == RunStatus.RUNNING
  finally:
    holder.rollback()
    holder.close()
    claimer.close()


def test_a_claimed_trial_is_not_handed_out_again(
    db_session: orm.Session, session_factory: orm.sessionmaker
):
  """A claim commits the trial as RUNNING, so the next pick cannot see it.

  This is the claim doing its job across two sessions rather than inside one.
  The third pick has nothing PENDING left and must say so instead of handing
  back a trial that is already running.
  """
  run_id, first_id, second_id = _run_with_two_pending_trials(db_session)

  worker_one = session_factory()
  worker_two = session_factory()
  try:
    claimed_one = TrialRepository(worker_one).pick_next_pending_trial(
        run_id=run_id
    )
    claimed_two = TrialRepository(worker_two).pick_next_pending_trial(
        run_id=run_id
    )

    assert {claimed_one.id, claimed_two.id} == {first_id, second_id}
    assert (
        TrialRepository(worker_two).pick_next_pending_trial(run_id=run_id)
        is None
    )
  finally:
    worker_one.close()
    worker_two.close()
