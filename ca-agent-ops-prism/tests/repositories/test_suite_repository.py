"""Unit tests for SuiteRepository."""

from prism.server.repositories.suite_repository import SuiteRepository
from sqlalchemy.orm import Session


def test_create_suite(db_session: Session):
  """Tests creating a new suite."""
  repo = SuiteRepository(db_session)
  suite = repo.create(name="My Suite", description="Desc")

  assert suite.id is not None
  assert suite.name == "My Suite"
  assert suite.description == "Desc"
  assert not suite.is_archived


def test_update_suite(db_session: Session):
  """Tests updating a suite."""
  repo = SuiteRepository(db_session)
  suite = repo.create(name="Suite 1")

  updated = repo.update(suite.id, name="Suite 2", tags={"a": "b"})
  assert updated.name == "Suite 2"
  assert updated.tags == {"a": "b"}


def test_archive_suite(db_session: Session):
  """Tests archiving a suite."""
  repo = SuiteRepository(db_session)
  suite = repo.create(name="To Archive")

  repo.archive(suite.id)
  assert suite.is_archived
