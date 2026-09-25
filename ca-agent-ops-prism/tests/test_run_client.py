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

"""Unit tests for RunsClient."""

from prism.client.run_client import RunsClient
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.execution import RunStatus
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.repositories.trial_repository import TrialRepository
from prism.server.services.snapshot_service import SnapshotService
from sqlalchemy.orm import Session


def test_cancel_run_cancels_pending_trials(db_session: Session):
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)
  run_repo = RunRepository(db_session)
  trial_repo = TrialRepository(db_session)

  config = AgentConfig(project_id="p", location="l", agent_resource_id="r")
  agent = agent_repo.create(name="Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")
  snapshot = snapshot_service.create_snapshot(suite.id)
  example_snapshot_id = snapshot.examples[0].id

  run = run_repo.create(snapshot.id, agent.id)
  pending = trial_repo.create(run.id, example_snapshot_id)
  running = trial_repo.create(run.id, example_snapshot_id)
  completed = trial_repo.create(run.id, example_snapshot_id)
  running.status = RunStatus.RUNNING
  completed.status = RunStatus.COMPLETED
  db_session.commit()

  # The UPDATE setting the pending trials to CANCELLED was built and never
  # executed, so only the run row changed. The worker pool selects by status,
  # so it kept picking the pending trials up and a cancelled run went on
  # calling a paid API.
  RunsClient().cancel_run(run_id=run.id, repo=run_repo)

  db_session.expire_all()
  assert run_repo.get_by_id(run.id).status == RunStatus.CANCELLED
  assert trial_repo.get_trial(pending.id).status == RunStatus.CANCELLED
  # Trials already started or finished are left alone.
  assert trial_repo.get_trial(running.id).status == RunStatus.RUNNING
  assert trial_repo.get_trial(completed.id).status == RunStatus.COMPLETED
