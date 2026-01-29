from prism.common.schemas.assertion import TextContains
from prism.server.models.assertion import Assertion as AssertionModel
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.suite_service import SuiteService
import pytest


@pytest.fixture
def suite_service(db_session):
  return SuiteService(
      db_session, SuiteRepository(db_session), ExampleRepository(db_session)
  )


def test_sync_suite_preserves_ids(db_session, suite_service, suite_svc=None):
  # 1. Create a suite
  suite = suite_service.create_suite(name="Test Suite for IDs")

  # 2. Add an example with an assertion
  assert1 = TextContains(type="text-contains", value="foo")
  example = suite_service.add_example(
      suite_id=suite.id, question="Q1", asserts=[assert1]
  )

  # Reload to get IDs
  db_session.refresh(example)
  original_example_id = example.id
  original_assert_id = example.asserts[0].id

  assert original_example_id is not None
  assert original_assert_id is not None

  # 3. Prepare sync data with SAME IDs
  questions = [{
      "id": original_example_id,
      "question": "Q1 Updated",
      "asserts": [{
          "id": original_assert_id,
          "type": "text-contains",
          "value": "bar",
      }],
  }]

  # 4. Sync
  suite_service.sync_suite(suite.id, questions)

  # 5. Verify IDs are preserved
  # Use session to get fresh state, ensure commit happened in sync_suite
  db_session.expire_all()
  updated_example = suite_service.get_example(original_example_id)
  assert updated_example is not None
  assert updated_example.question == "Q1 Updated"

  assert len(updated_example.asserts) == 1
  updated_assert = updated_example.asserts[0]

  assert updated_assert.id == original_assert_id
  assert updated_assert.params["value"] == "bar"


def test_sync_suite_adds_new_assertion(db_session, suite_service):
  suite = suite_service.create_suite(name="Test Suite Add")
  example = suite_service.add_example(suite.id, "Q1")
  original_id = example.id

  questions = [{
      "id": original_id,
      "question": "Q1",
      "asserts": [{"type": "text-contains", "value": "new"}],
  }]

  suite_service.sync_suite(suite.id, questions)

  db_session.expire_all()
  updated = suite_service.get_example(original_id)
  assert len(updated.asserts) == 1
  assert updated.asserts[0].params["value"] == "new"


def test_sync_suite_removes_assertion(db_session, suite_service):
  suite = suite_service.create_suite(name="Test Suite Remove")
  assert1 = TextContains(type="text-contains", value="foo")
  example = suite_service.add_example(suite.id, "Q1", asserts=[assert1])
  original_id = example.id

  questions = [{"id": original_id, "question": "Q1", "asserts": []}]

  suite_service.sync_suite(suite.id, questions)

  db_session.expire_all()
  updated = suite_service.get_example(original_id)
  assert len(updated.asserts) == 0
