"""Tests for sync_suite in SuiteService."""

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


def test_sync_suite(suite_svc: SuiteService):
  """Tests synchronizing a suite's examples."""
  # 1. Create a suite
  suite = suite_svc.create_suite(name="Sync Test")
  suite_id = suite.id

  # 2. Add some existing examples
  suite_svc.add_example(suite_id, "Old question")
  assert len(suite_svc.list_examples(suite_id)) == 1

  # 3. Sync with new questions
  new_questions = [
      {
          "question": "New question 1",
          "asserts": [{"type": "text-contains", "value": "42"}],
      },
      {"question": "New question 2", "asserts": []},
  ]
  suite_svc.sync_suite(suite_id, new_questions)

  # 4. Verify results
  examples = suite_svc.list_examples(suite_id)
  assert len(examples) == 2
  assert examples[0].question == "New question 1"
  assert len(examples[0].asserts) == 1
  assert examples[0].asserts[0].type == "text-contains"
  assert examples[1].question == "New question 2"

  # Ensure old one is gone (or archived)
  all_examples = suite_svc.list_examples(suite_id, include_archived=False)
  assert len(all_examples) == 2
