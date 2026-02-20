"""Unit tests for RunRepository."""

from prism.common.schemas.agent import AgentConfig
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.snapshot_service import SnapshotService
from sqlalchemy.orm import Session


def test_create_run(db_session: Session):
  """Tests creating a new run."""
  # Setup prerequisites
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  agent = agent_repo.create(name="Bot", config=config)
  suite = suite_repo.create(name="Suite")
  snapshot = snapshot_service.create_snapshot(suite.id)

  # Test
  repo = RunRepository(db_session)
  run = repo.create(
      test_suite_snapshot_id=snapshot.id,
      agent_id=agent.id,
      agent_context_snapshot={"p": "v"},
  )

  assert run.id is not None
  assert run.agent_id == agent.id
  assert run.agent_context_snapshot == {"p": "v"}
  assert not run.is_archived


def test_list_runs(db_session: Session):
  """Tests listing runs."""
  # Setup prerequisites
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  agent = agent_repo.create(name="Bot", config=config)
  suite = suite_repo.create(name="Suite")
  snapshot = snapshot_service.create_snapshot(suite.id)

  repo = RunRepository(db_session)
  repo.create(snapshot.id, agent.id)
  repo.create(snapshot.id, agent.id)

  runs = repo.list_all()
  assert len(runs) == 2


def test_archive_run(db_session: Session):
  """Tests archiving a run."""
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  agent = agent_repo.create(
      name="Bot",
      config=AgentConfig(project_id="p", location="l", agent_resource_id="r"),
  )
  suite = suite_repo.create(name="Suite")
  snapshot = snapshot_service.create_snapshot(suite.id)

  repo = RunRepository(db_session)
  run = repo.create(snapshot.id, agent.id)
  assert not run.is_archived

  repo.archive(run.id)
  db_session.refresh(run)
  assert run.is_archived


def test_unarchive_run(db_session: Session):
  """Tests unarchiving a run."""
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  agent = agent_repo.create(
      name="Bot",
      config=AgentConfig(project_id="p", location="l", agent_resource_id="r"),
  )
  suite = suite_repo.create(name="Suite")
  snapshot = snapshot_service.create_snapshot(suite.id)

  repo = RunRepository(db_session)
  run = repo.create(snapshot.id, agent.id)
  repo.archive(run.id)
  db_session.refresh(run)
  assert run.is_archived

  repo.unarchive(run.id)
  db_session.refresh(run)
  assert not run.is_archived
