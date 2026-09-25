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

"""Repository for managing Example entities."""

import uuid

from prism.common.schemas.assertion import Assertion
from prism.common.schemas.assertion import AssertionRequest
from prism.server.models.assertion import Assertion as AssertionModel
from prism.server.models.example import Example
from sqlalchemy.orm import Session


class ExampleRepository:
  """Repository for Example operations."""

  def __init__(self, session: Session):
    self.session = session

  def create(
      self,
      test_suite_id: int,
      question: str,
      logical_id: str | None = None,
  ) -> Example:
    """Inserts an example, generating a logical_id if the caller has none.

    Flushes rather than commits, so the caller owns the transaction.
    """
    if not logical_id:
      logical_id = str(uuid.uuid4())

    example = Example(
        test_suite_id=test_suite_id,
        logical_id=logical_id,
        question=question,
    )
    self.session.add(example)
    self.session.flush()
    self.session.refresh(example)
    return example

  def get_by_id(self, example_id: int) -> Example | None:
    """Reads one example, archived or not. None if there is no such row."""
    return self.session.get(Example, example_id)

  def list_by_suite_id(
      self, test_suite_id: int, include_archived: bool = False
  ) -> list[Example]:
    """Lists a suite's examples oldest first, archived ones only when asked."""
    query = self.session.query(Example).filter(
        Example.test_suite_id == test_suite_id
    )
    if not include_archived:
      query = query.filter(
          Example.is_archived == False  # pylint: disable=singleton-comparison
      )
    return query.order_by(Example.created_at.asc(), Example.id.asc()).all()

  def update(
      self,
      example_id: int,
      question: str | None = None,
  ) -> Example:
    """Rewrites the question. Raises ValueError if there is no such row."""
    example = self.get_by_id(example_id)
    if not example:
      raise ValueError(f"Example with id {example_id} not found")

    if question is not None:
      example.question = question

    self.session.flush()
    self.session.refresh(example)
    return example

  def archive(self, example_id: int) -> Example:
    """Hides an example from the suite. Raises ValueError if there is no row."""
    example = self.get_by_id(example_id)
    if not example:
      raise ValueError(f"Example with id {example_id} not found")

    example.is_archived = True
    self.session.flush()
    self.session.refresh(example)
    return example

  def add_assertion(
      self, example_id: int, assertion: Assertion | AssertionRequest
  ) -> AssertionModel:
    """Adds an assertion to an example.

    Both unions arrive here. sync_suite parses into Assertion, which carries
    the id of a row that already exists, and the client passes the request
    schemas, which have no id at all.
    """
    atype = assertion.type
    weight = assertion.weight

    # Everything the table has no column for goes in the JSON params blob.
    # id is dropped because this is a new row.
    params = assertion.model_dump(exclude={"id", "type", "weight"})

    orm_assertion = AssertionModel(
        example_id=example_id,
        type=atype,
        weight=weight,
        params=params,
    )
    self.session.add(orm_assertion)
    self.session.flush()
    self.session.refresh(orm_assertion)
    return orm_assertion

  def update_assertion(
      self, assertion_id: int, assertion: Assertion | AssertionRequest
  ) -> Example:
    """Rewrites an assertion and returns the example it hangs off.

    Raises:
      ValueError: If there is no assertion with that id.
    """
    orm_assertion = self.session.get(AssertionModel, assertion_id)
    if not orm_assertion:
      raise ValueError(f"Assertion {assertion_id} not found")

    orm_assertion.type = assertion.type
    orm_assertion.weight = assertion.weight

    orm_assertion.params = assertion.model_dump(
        exclude={"id", "type", "weight"}
    )

    self.session.flush()
    # No refresh here. Lazy loading and the identity map should cover access
    # through the relationship.
    return orm_assertion.example

  def delete_assertion(self, assertion_id: int) -> None:
    """Deletes an assertion. A missing one is not an error."""
    orm_assertion = self.session.get(AssertionModel, assertion_id)
    if orm_assertion:
      self.session.delete(orm_assertion)
      self.session.flush()
