"""Unit tests for SuiteService."""

# pylint: disable=redefined-outer-name

from prism.common.schemas.assertion import TextContains
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.suite_service import SuiteService
import pytest
from sqlalchemy.orm import Session


@pytest.fixture
def suite_svc(db_session: Session):
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  return SuiteService(db_session, suite_repo, example_repo)


def test_create_suite_service(suite_svc: SuiteService):
  """Tests creating a suite via service."""
  suite = suite_svc.create_suite(name="Service Suite")
  assert suite.name == "Service Suite"


def test_get_suite(suite_svc: SuiteService):
  """Tests getting a suite."""
  created = suite_svc.create_suite(name="Get Me")
  fetched = suite_svc.get_suite(created.id)
  assert fetched is not None
  assert fetched.name == "Get Me"


def test_list_suites(suite_svc: SuiteService):
  """Tests listing suites."""
  suite_svc.create_suite("S1")
  suite_svc.create_suite("S2")
  suites = suite_svc.list_suites()
  assert len(suites) == 2


def test_update_suite(suite_svc: SuiteService):
  """Tests updating a suite."""
  suite = suite_svc.create_suite("Old Name")
  updated = suite_svc.update_suite(
      suite.id, name="New Name", description="Desc"
  )
  assert updated.name == "New Name"
  assert updated.description == "Desc"


def test_archive_suite(suite_svc: SuiteService):
  """Tests archiving a suite."""
  suite = suite_svc.create_suite("To Archive")
  suite_svc.archive_suite(suite.id)
  active = suite_svc.list_suites()
  assert not active


def test_add_example_service(suite_svc: SuiteService):
  """Tests adding an example via service."""
  suite = suite_svc.create_suite(name="Suite")
  example = suite_svc.add_example(suite.id, "Q1")

  assert example.test_suite_id == suite.id
  assert example.question == "Q1"


def test_get_example_service(suite_svc: SuiteService):
  """Tests getting an example via service."""
  suite = suite_svc.create_suite(name="Suite")
  created = suite_svc.add_example(suite.id, "Q1")

  fetched = suite_svc.get_example(created.id)
  assert fetched is not None
  assert fetched.question == "Q1"


def test_list_examples(suite_svc: SuiteService):
  """Tests listing examples."""
  suite = suite_svc.create_suite(name="Suite")
  suite_svc.add_example(suite.id, "Q1")
  suite_svc.add_example(suite.id, "Q2")
  examples = suite_svc.list_examples(suite.id)
  assert len(examples) == 2


def test_update_example(suite_svc: SuiteService):
  """Tests updating an example."""
  suite = suite_svc.create_suite(name="Suite")
  example = suite_svc.add_example(suite.id, "Q1")
  updated = suite_svc.update_example(example.id, question="Q1 Updated")
  assert updated.question == "Q1 Updated"


def test_delete_example(suite_svc: SuiteService):
  """Tests deleting (archiving) an example."""
  suite = suite_svc.create_suite(name="Suite")
  example = suite_svc.add_example(suite.id, "Q1")
  suite_svc.delete_example(example.id)
  examples = suite_svc.list_examples(suite.id)
  assert not examples


def test_add_assertion(suite_svc: SuiteService):
  """Tests adding an assertion to an example."""
  suite = suite_svc.create_suite(name="Suite")
  example = suite_svc.add_example(suite.id, "Q1")

  assertion = TextContains(value="foo")
  updated = suite_svc.add_assertion(example.id, assertion)

  assert len(updated.asserts) == 1
  assert updated.asserts[0].type == "text-contains"
  assert updated.asserts[0].params["value"] == "foo"
