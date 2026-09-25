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

from prism.common.schemas.assertion import TextContains
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.suite_service import SuiteService
import pytest


@pytest.fixture
def suite_service(db_session):
  return SuiteService(
      db_session, SuiteRepository(db_session), ExampleRepository(db_session)
  )


def test_sync_suite_preserves_ids(db_session, suite_service):
  suite = suite_service.create_suite(name="Test Suite for IDs")

  assert1 = TextContains(type="text-contains", value="foo")
  example = suite_service.add_example(
      suite_id=suite.id, question="Q1", asserts=[assert1]
  )

  # The ids are server-assigned, so they are only readable after a refresh.
  db_session.refresh(example)
  original_example_id = example.id
  original_assert_id = example.asserts[0].id

  assert original_example_id is not None
  assert original_assert_id is not None

  # Carrying the ids back means an update. Without them sync_suite would
  # delete these rows and insert new ones, and the ids are what the trial
  # history is keyed on.
  questions = [{
      "id": original_example_id,
      "question": "Q1 Updated",
      "asserts": [{
          "id": original_assert_id,
          "type": "text-contains",
          "value": "bar",
      }],
  }]

  suite_service.sync_suite(suite.id, questions)

  # Expired, so the reads below come off the database and not out of the
  # identity map, which would pass whether sync_suite committed or not.
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
