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

"""Service for managing Test Suites and Examples."""

from typing import Any
from typing import Sequence

from prism.common.schemas import example as example_schemas
from prism.common.schemas.assertion import Assertion
from prism.common.schemas.suite import Suite
from prism.common.schemas.suite import SuiteWithStats
from prism.server.models.example import Example
from prism.server.models.run import Run
from prism.server.models.snapshot import TestSuiteSnapshot
from prism.server.models.suite import TestSuite
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
import pydantic
from sqlalchemy.orm import Session


class SuiteService:
  """Service for Test Suite operations."""

  def __init__(
      self,
      session: Session,
      suite_repository: SuiteRepository,
      example_repository: ExampleRepository,
  ):
    """Initializes the SuiteService."""
    self.session = session
    self.suite_repository = suite_repository
    self.example_repository = example_repository

  def create_suite(
      self,
      name: str,
      description: str | None = None,
      tags: dict[str, str] | None = None,
  ) -> TestSuite:
    """Creates a new test suite."""
    return self.suite_repository.create(
        name=name,
        description=description,
        tags=tags,
    )

  def get_suite(self, suite_id: int) -> TestSuite | None:
    """Retrieves a suite by ID."""
    return self.suite_repository.get_by_id(suite_id)

  def list_suites(self, include_archived: bool = False) -> Sequence[TestSuite]:
    """Lists all suites."""
    return self.suite_repository.list_all(include_archived=include_archived)

  def get_suites_with_stats(
      self,
      include_archived: bool = False,
      coverage: str | None = None,
  ) -> list[SuiteWithStats]:
    """Lists all suites with question and run counts.

    Args:
        include_archived: Whether to include archived suites.
        coverage: Filter by coverage status ('FULL', 'PARTIAL', 'NONE').

    Returns:
        List of SuiteWithStats.
    """
    suites = self.list_suites(include_archived=include_archived)
    stats = []
    for suite in suites:
      # Question Count
      examples = self.example_repository.list_by_suite_id(suite.id)
      question_count = len(examples)

      # Run Count
      # Join Runs with TestSuiteSnapshots that point to this suite id
      run_count = (
          self.session.query(Run)
          .join(TestSuiteSnapshot)
          .filter(TestSuiteSnapshot.original_suite_id == suite.id)
          .filter(Run.is_archived == False)  # pylint: disable=singleton-comparison
          .count()
      )

      # Assertion Coverage
      questions_with_asserts = sum(1 for e in examples if e.asserts)
      assertion_coverage = 0.0
      if question_count > 0:
        assertion_coverage = questions_with_asserts / question_count

      # Filter by coverage
      if coverage:
        if coverage == "FULL" and assertion_coverage < 1.0:
          continue
        if coverage == "PARTIAL" and (
            assertion_coverage <= 0.0 or assertion_coverage >= 1.0
        ):
          continue
        if coverage == "NONE" and assertion_coverage > 0.0:
          continue

      stats.append(
          SuiteWithStats(
              suite=Suite.model_validate(suite),
              question_count=question_count,
              run_count=run_count,
              assertion_coverage=assertion_coverage,
          )
      )
    return stats

  def update_suite(
      self,
      suite_id: int,
      name: str | None = None,
      description: str | None = None,
      tags: dict[str, str] | None = None,
  ) -> TestSuite:
    """Updates a test suite."""
    return self.suite_repository.update(
        suite_id=suite_id,
        name=name,
        description=description,
        tags=tags,
    )

  def archive_suite(self, suite_id: int) -> TestSuite:
    """Archives a test suite."""
    return self.suite_repository.archive(suite_id=suite_id)

  def unarchive_suite(self, suite_id: int) -> TestSuite:
    """Unarchives a test suite."""
    return self.suite_repository.unarchive(suite_id=suite_id)

  def sync_suite(
      self,
      suite_id: int,
      questions: list[dict[str, Any]],
  ) -> list[dict[str, Any]]:
    """Synchronizes a suite's examples with the provided questions."""
    # 1. Get existing examples
    existing_examples = {e.id: e for e in self.list_examples(suite_id)}
    processed_example_ids = set()
    result_questions = []

    for q in questions:
      question_text = q["question"]
      question_id = q.get("id")

      # Prepare assertions
      asserts_parsed = []
      for a in q.get("asserts", []):
        asserts_parsed.append(
            pydantic.TypeAdapter(Assertion).validate_python(a)
        )

      if question_id and question_id in existing_examples:
        # Update existing
        processed_example_ids.add(question_id)
        updated_example = self.update_example(
            example_id=question_id,
            question=question_text,
            asserts=asserts_parsed,
        )
        result_questions.append(
            example_schemas.Example.model_validate(updated_example).model_dump()
        )
      else:
        # Create new
        new_example = self.add_example(
            suite_id=suite_id,
            question=question_text,
            asserts=asserts_parsed,
        )
        result_questions.append(
            example_schemas.Example.model_validate(new_example).model_dump()
        )

    # 2. Delete removed examples
    for e_id in existing_examples:
      if e_id not in processed_example_ids:
        self.delete_example(e_id)

    return result_questions

  # Example Operations

  def add_example(
      self,
      suite_id: int,
      question: str,
      asserts: list[Assertion] | None = None,
  ) -> Example:
    """Adds a new example to a suite."""
    # Validate suite exists
    if not self.suite_repository.get_by_id(suite_id):
      raise ValueError(f"TestSuite with id {suite_id} not found")

    example = self.example_repository.create(
        test_suite_id=suite_id,
        question=question,
    )

    if asserts:
      for a in asserts:
        self.example_repository.add_assertion(example.id, a)

    # Refresh to return full object with assertions
    self.session.refresh(example)
    return example

  def get_example(self, example_id: int) -> Example | None:
    """Retrieves an example by ID."""
    return self.example_repository.get_by_id(example_id)

  def list_examples(
      self, suite_id: int, include_archived: bool = False
  ) -> Sequence[Example]:
    """Lists examples for a suite."""
    return self.example_repository.list_by_suite_id(
        test_suite_id=suite_id, include_archived=include_archived
    )

  def update_example(
      self,
      example_id: int,
      question: str | None = None,
      asserts: list[Assertion] | None = None,
  ) -> Example:
    """Updates an example."""
    # First update basic fields
    example = self.example_repository.update(
        example_id=example_id, question=question
    )

    # Then handle assertions reconciliation if provided
    if asserts is not None:
      existing_asserts = {a.id: a for a in example.asserts}
      processed_assert_ids = set()

      for a in asserts:
        # Assertion schema (from Pydantic) might have 'id' if it exists
        aid = getattr(a, "id", None)

        if aid and aid in existing_asserts:
          # Update existing
          processed_assert_ids.add(aid)
          self.example_repository.update_assertion(aid, a)
        else:
          # Create new
          new_a = self.example_repository.add_assertion(example.id, a)
          processed_assert_ids.add(new_a.id)

      # Delete removed assertions
      for aid in existing_asserts:
        if aid not in processed_assert_ids:
          self.example_repository.delete_assertion(aid)

    # Refresh to return full object
    self.session.refresh(example)
    return example

  def delete_example(self, example_id: int) -> Example:
    """Archives (deletes) an example."""
    return self.example_repository.archive(example_id=example_id)

  def add_assertion(self, example_id: int, assertion: Assertion) -> Example:
    """Adds a single assertion to an example."""
    self.example_repository.add_assertion(example_id, assertion)
    return self.example_repository.get_by_id(example_id)

  def update_assertion(
      self,
      assertion_id: int,
      assertion_data: Assertion,
  ) -> Example:
    """Updates an assertion."""
    return self.example_repository.update_assertion(
        assertion_id, assertion_data
    )

  def delete_assertion(self, assertion_id: int) -> None:
    """Deletes an assertion by ID."""
    self.example_repository.delete_assertion(assertion_id)
