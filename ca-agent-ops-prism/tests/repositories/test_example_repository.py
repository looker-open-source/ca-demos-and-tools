"""Tests for ExampleRepository."""

from prism.common.schemas import assertion as assertion_schemas
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository


def test_create_example_no_asserts(db_session):
  """Tests creating a new example without assertions."""
  suite_repo = SuiteRepository(db_session)
  suite = suite_repo.create(name="Test Suite")

  repo = ExampleRepository(db_session)
  example = repo.create(test_suite_id=suite.id, question="What is 2+2?")

  assert example.id is not None
  assert example.question == "What is 2+2?"
  assert example.test_suite_id == suite.id
  assert example.asserts == []


def test_add_assertion(db_session):
  """Tests adding an assertion to an example."""
  suite_repo = SuiteRepository(db_session)
  suite = suite_repo.create(name="Test Suite")
  repo = ExampleRepository(db_session)
  example = repo.create(test_suite_id=suite.id, question="Q1")

  assert_schema = assertion_schemas.TextContainsSchema(value="4")

  assertion = repo.add_assertion(example.id, assert_schema)

  # Refresh example
  db_session.refresh(example)
  assert len(example.asserts) == 1
  assert (
      example.asserts[0].type == assertion_schemas.AssertionType.TEXT_CONTAINS
  )
  assert example.asserts[0].params["value"] == "4"


def test_update_assertion(db_session):
  """Tests updating an assertion."""
  suite_repo = SuiteRepository(db_session)
  suite = suite_repo.create(name="Test Suite")
  repo = ExampleRepository(db_session)
  example = repo.create(test_suite_id=suite.id, question="Q1")

  # Add initial
  assert_schema = assertion_schemas.TextContainsSchema(value="4")
  assertion = repo.add_assertion(example.id, assert_schema)

  # Update
  update_schema = assertion_schemas.TextContainsSchema(value="5")
  updated_example = repo.update_assertion(assertion.id, update_schema)

  assert len(updated_example.asserts) == 1
  assert updated_example.asserts[0].params["value"] == "5"


def test_delete_assertion(db_session):
  """Tests deleting an assertion."""
  suite_repo = SuiteRepository(db_session)
  suite = suite_repo.create(name="Test Suite")
  repo = ExampleRepository(db_session)
  example = repo.create(test_suite_id=suite.id, question="Q1")

  assert_schema = assertion_schemas.TextContainsSchema(value="4")
  assertion = repo.add_assertion(example.id, assert_schema)

  repo.delete_assertion(assertion.id)

  db_session.refresh(example)
  assert len(example.asserts) == 0


def test_list_examples(db_session):
  """Tests listing examples."""
  suite_repo = SuiteRepository(db_session)
  suite = suite_repo.create(name="Suite")

  example_repo = ExampleRepository(db_session)
  example_repo.create(suite.id, "Q1")
  example_repo.create(suite.id, "Q2")

  examples = example_repo.list_by_suite_id(suite.id)
  assert len(examples) == 2


def test_archive_example(db_session):
  """Tests archiving an example."""
  suite_repo = SuiteRepository(db_session)
  suite = suite_repo.create(name="Suite")
  example_repo = ExampleRepository(db_session)
  example = example_repo.create(suite.id, "Q1")

  example_repo.archive(example.id)
  assert example.is_archived
