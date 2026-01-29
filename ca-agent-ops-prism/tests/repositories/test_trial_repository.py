"""Unit tests for TrialRepository."""

from prism.common.schemas.agent import AgentConfig
from prism.server.models.assertion import SuggestedAssertion
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.repositories.trial_repository import TrialRepository
from prism.server.services.snapshot_service import SnapshotService
from sqlalchemy.orm import Session


def test_create_trial(db_session: Session):
  """Tests creating a trial."""
  # Setup prerequisites
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)
  run_repo = RunRepository(db_session)

  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  agent = agent_repo.create(name="Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")
  snapshot = snapshot_service.create_snapshot(suite.id)
  run = run_repo.create(snapshot.id, agent.id)

  # Test
  repo = TrialRepository(db_session)
  trial = repo.create(
      run_id=run.id, example_snapshot_id=snapshot.examples[0].id
  )

  assert trial.id is not None
  assert trial.run_id == run.id
  assert not trial.is_archived


def test_update_result_trial(db_session: Session):
  """Tests updating trial result."""
  # Setup prerequisites
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)
  run_repo = RunRepository(db_session)
  trial_repo = TrialRepository(db_session)

  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  agent = agent_repo.create(name="Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")
  snapshot = snapshot_service.create_snapshot(suite.id)
  run = run_repo.create(snapshot.id, agent.id)
  trial = trial_repo.create(run.id, snapshot.examples[0].id)

  from prism.server.models.assertion import AssertionResult, AssertionSnapshot, AssertionType

  snap = AssertionSnapshot(
      example_snapshot_id=snapshot.examples[0].id,
      type=AssertionType.TEXT_CONTAINS,
      weight=1.0,
  )
  db_session.add(snap)
  db_session.commit()

  # Add an assertion result to provide a score
  res = AssertionResult(
      trial_id=trial.id,
      assertion_snapshot_id=snap.id,
      passed=True,
      score=1.0,
  )
  db_session.add(res)
  db_session.commit()

  updated = trial_repo.update_result(
      trial.id,
      output_text="Out",
      trace_results=[{"trace": "123"}],
  )

  db_session.refresh(updated)
  assert updated.output_text == "Out"
  assert updated.score == 1.0
  assert updated.trace_results == [{"trace": "123"}]


def test_update_suggestion(db_session: Session):
  """Tests updating a suggestion in a trial."""
  # Setup prerequisites
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)
  run_repo = RunRepository(db_session)
  trial_repo = TrialRepository(db_session)

  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  agent = agent_repo.create(name="Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")
  snapshot = snapshot_service.create_snapshot(suite.id)
  run = run_repo.create(snapshot.id, agent.id)
  trial = trial_repo.create(run.id, snapshot.examples[0].id)

  # Manually set suggestions for test (since create doesn't support it directly yet or we mocked it)
  # But Trial model supports it.
  trial.suggested_asserts = [
      SuggestedAssertion(
          type="text-contains", weight=1.0, params={"value": "foo"}
      )
  ]
  db_session.commit()

  updated_trial = trial_repo.update_suggestion(
      trial.id,
      0,
      {"type": "text-contains", "params": {"value": "bar"}, "weight": 0},
  )

  assert updated_trial.suggested_asserts[0].params["value"] == "bar"
  assert updated_trial.suggested_asserts[0].weight == 0
