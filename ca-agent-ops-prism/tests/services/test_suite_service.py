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

"""Unit tests for SuiteService."""

# pylint: disable=redefined-outer-name

from prism.common.schemas.assertion import TextContains
from prism.common.schemas.assertion import TextContainsSchema
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
  suite = suite_svc.create_suite(name="Service Suite")
  assert suite.name == "Service Suite"


def test_get_suite(suite_svc: SuiteService):
  created = suite_svc.create_suite(name="Get Me")
  fetched = suite_svc.get_suite(created.id)
  assert fetched is not None
  assert fetched.name == "Get Me"


def test_list_suites(suite_svc: SuiteService):
  suite_svc.create_suite("S1")
  suite_svc.create_suite("S2")
  suites = suite_svc.list_suites()
  assert len(suites) == 2


def test_update_suite(suite_svc: SuiteService):
  suite = suite_svc.create_suite("Old Name")
  updated = suite_svc.update_suite(
      suite.id, name="New Name", description="Desc"
  )
  assert updated.name == "New Name"
  assert updated.description == "Desc"


def test_archive_suite(suite_svc: SuiteService):
  """Archiving removes the suite from the default listing."""
  suite = suite_svc.create_suite("To Archive")
  suite_svc.archive_suite(suite.id)
  active = suite_svc.list_suites()
  assert not active


def test_add_example_service(suite_svc: SuiteService):
  suite = suite_svc.create_suite(name="Suite")
  example = suite_svc.add_example(suite.id, "Q1")

  assert example.test_suite_id == suite.id
  assert example.question == "Q1"


def test_get_example_service(suite_svc: SuiteService):
  suite = suite_svc.create_suite(name="Suite")
  created = suite_svc.add_example(suite.id, "Q1")

  fetched = suite_svc.get_example(created.id)
  assert fetched is not None
  assert fetched.question == "Q1"


def test_list_examples(suite_svc: SuiteService):
  suite = suite_svc.create_suite(name="Suite")
  suite_svc.add_example(suite.id, "Q1")
  suite_svc.add_example(suite.id, "Q2")
  examples = suite_svc.list_examples(suite.id)
  assert len(examples) == 2


def test_update_example(suite_svc: SuiteService):
  suite = suite_svc.create_suite(name="Suite")
  example = suite_svc.add_example(suite.id, "Q1")
  updated = suite_svc.update_example(example.id, question="Q1 Updated")
  assert updated.question == "Q1 Updated"


def test_delete_example(suite_svc: SuiteService):
  """Deleting an example archives it."""
  suite = suite_svc.create_suite(name="Suite")
  example = suite_svc.add_example(suite.id, "Q1")
  suite_svc.delete_example(example.id)
  examples = suite_svc.list_examples(suite.id)
  assert not examples


def test_add_assertion(suite_svc: SuiteService):
  suite = suite_svc.create_suite(name="Suite")
  example = suite_svc.add_example(suite.id, "Q1")

  assertion = TextContains(value="foo")
  updated = suite_svc.add_assertion(example.id, assertion)

  assert len(updated.asserts) == 1
  assert updated.asserts[0].type == "text-contains"
  assert updated.asserts[0].params["value"] == "foo"


def test_coverage_ignores_weight_zero_assertions(suite_svc: SuiteService):
  """A suite that can never score must not read as fully covered.

  Trial.score averages the weight > 0 assertions only. Coverage counted any
  assertion, so a suite whose every question carried one diagnostic
  (weight 0) assertion showed 1.0 and a green Full Coverage badge, and then
  every trial in its run scored None.
  """
  suite = suite_svc.create_suite(name="All Diagnostic")
  suite_svc.add_example(
      suite.id, "Q1", asserts=[TextContainsSchema(value="a", weight=0.0)]
  )
  suite_svc.add_example(
      suite.id, "Q2", asserts=[TextContainsSchema(value="b", weight=0.0)]
  )

  stats = {s.suite.id: s for s in suite_svc.get_suites_with_stats()}

  assert stats[suite.id].assertion_coverage == 0.0


def test_coverage_counts_a_question_with_one_scoring_assertion(
    suite_svc: SuiteService,
):
  """A diagnostic assertion alongside a scoring one still leaves it covered."""
  suite = suite_svc.create_suite(name="Mixed")
  suite_svc.add_example(
      suite.id,
      "Q1",
      asserts=[
          TextContainsSchema(value="a", weight=0.0),
          TextContainsSchema(value="b", weight=1.0),
      ],
  )
  suite_svc.add_example(
      suite.id, "Q2", asserts=[TextContainsSchema(value="c", weight=0.0)]
  )

  stats = {s.suite.id: s for s in suite_svc.get_suites_with_stats()}

  assert stats[suite.id].assertion_coverage == 0.5


def test_the_coverage_filter_uses_the_same_population(suite_svc: SuiteService):
  """FULL returned the all-diagnostic suite, which cannot score at all."""
  diagnostic = suite_svc.create_suite(name="All Diagnostic")
  suite_svc.add_example(
      diagnostic.id, "Q1", asserts=[TextContainsSchema(value="a", weight=0.0)]
  )
  scoring = suite_svc.create_suite(name="Scoring")
  suite_svc.add_example(
      scoring.id, "Q1", asserts=[TextContainsSchema(value="b", weight=1.0)]
  )

  full = {s.suite.id for s in suite_svc.get_suites_with_stats(coverage="FULL")}
  none = {s.suite.id for s in suite_svc.get_suites_with_stats(coverage="NONE")}

  assert full == {scoring.id}
  assert none == {diagnostic.id}
