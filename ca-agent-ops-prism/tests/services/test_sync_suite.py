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
  suite = suite_svc.create_suite(name="Sync Test")
  suite_id = suite.id

  suite_svc.add_example(suite_id, "Old question")
  assert len(suite_svc.list_examples(suite_id)) == 1

  new_questions = [
      {
          "question": "New question 1",
          "asserts": [{"type": "text-contains", "value": "42"}],
      },
      {"question": "New question 2", "asserts": []},
  ]
  suite_svc.sync_suite(suite_id, new_questions)

  examples = suite_svc.list_examples(suite_id)
  assert len(examples) == 2
  assert examples[0].question == "New question 1"
  assert len(examples[0].asserts) == 1
  assert examples[0].asserts[0].type == "text-contains"
  assert examples[1].question == "New question 2"

  # The question the sync dropped is archived, not deleted. Its row has to
  # survive, because every ExampleSnapshot of a historical run points back at
  # it and deleting it orphans them.
  all_examples = suite_svc.list_examples(suite_id, include_archived=True)
  assert len(all_examples) == 3
  archived = [e for e in all_examples if e.is_archived]
  assert [e.question for e in archived] == ["Old question"]
