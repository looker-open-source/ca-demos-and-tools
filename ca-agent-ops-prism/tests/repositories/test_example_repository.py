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

"""Tests for ExampleRepository."""

from prism.common.schemas import assertion as assertion_schemas
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository


def test_create_example_no_asserts(db_session):
  suite_repo = SuiteRepository(db_session)
  suite = suite_repo.create(name="Test Suite")

  repo = ExampleRepository(db_session)
  example = repo.create(test_suite_id=suite.id, question="What is 2+2?")

  assert example.id is not None
  assert example.question == "What is 2+2?"
  assert example.test_suite_id == suite.id
  assert example.asserts == []


def test_add_assertion(db_session):
  suite_repo = SuiteRepository(db_session)
  suite = suite_repo.create(name="Test Suite")
  repo = ExampleRepository(db_session)
  example = repo.create(test_suite_id=suite.id, question="Q1")

  assert_schema = assertion_schemas.TextContainsSchema(value="4")

  repo.add_assertion(example.id, assert_schema)

  db_session.refresh(example)
  assert len(example.asserts) == 1
  assert (
      example.asserts[0].type == assertion_schemas.AssertionType.TEXT_CONTAINS
  )
  assert example.asserts[0].params["value"] == "4"


def test_update_assertion(db_session):
  suite_repo = SuiteRepository(db_session)
  suite = suite_repo.create(name="Test Suite")
  repo = ExampleRepository(db_session)
  example = repo.create(test_suite_id=suite.id, question="Q1")

  assert_schema = assertion_schemas.TextContainsSchema(value="4")
  assertion = repo.add_assertion(example.id, assert_schema)

  update_schema = assertion_schemas.TextContainsSchema(value="5")
  updated_example = repo.update_assertion(assertion.id, update_schema)

  assert len(updated_example.asserts) == 1
  assert updated_example.asserts[0].params["value"] == "5"


def test_delete_assertion(db_session):
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
  suite_repo = SuiteRepository(db_session)
  suite = suite_repo.create(name="Suite")

  example_repo = ExampleRepository(db_session)
  example_repo.create(suite.id, "Q1")
  example_repo.create(suite.id, "Q2")

  examples = example_repo.list_by_suite_id(suite.id)
  assert len(examples) == 2


def test_archive_example(db_session):
  suite_repo = SuiteRepository(db_session)
  suite = suite_repo.create(name="Suite")
  example_repo = ExampleRepository(db_session)
  example = example_repo.create(suite.id, "Q1")

  example_repo.archive(example.id)
  assert example.is_archived
