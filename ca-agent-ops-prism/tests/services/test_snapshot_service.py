"""Unit tests for SnapshotService."""

from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.snapshot_service import SnapshotService
from sqlalchemy.orm import Session


def test_create_snapshot(db_session: Session):
  """Tests creating a snapshot from a suite."""
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  service = SnapshotService(db_session, suite_repo, example_repo)

  # Create Live Data
  suite = suite_repo.create(name="Live Suite", tags={"env": "prod"})
  example_repo.create(suite.id, "Q1")

  # Create Snapshot
  snapshot = service.create_snapshot(suite.id)

  assert snapshot.original_suite_id == suite.id
  assert snapshot.name == "Live Suite"
  assert snapshot.tags == {"env": "prod"}
  assert len(snapshot.examples) == 1
  assert snapshot.examples[0].question == "Q1"
