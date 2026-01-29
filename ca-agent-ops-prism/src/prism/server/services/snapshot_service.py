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

"""Service for creating and managing snapshots."""

import datetime

from prism.server.models.assertion import AssertionSnapshot
from prism.server.models.snapshot import ExampleSnapshot
from prism.server.models.snapshot import TestSuiteSnapshot
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from sqlalchemy import orm


class SnapshotService:
  """Service for managing Test Suite snapshots."""

  def __init__(
      self,
      session: orm.Session,
      suite_repository: SuiteRepository,
      example_repository: ExampleRepository,
  ):
    """Initializes the SnapshotService."""
    self.session = session
    self.suite_repository = suite_repository
    self.example_repository = example_repository

  def create_snapshot(self, suite_id: int) -> TestSuiteSnapshot:
    """Creates a full snapshot of the given Test Suite.

    Args:
      suite_id: ID of the live Test Suite to snapshot.

    Returns:
      The newly created TestSuiteSnapshot.

    Raises:
      ValueError: If the suite_id does not exist.
    """
    suite = self.suite_repository.get_by_id(suite_id)
    if not suite:
      raise ValueError(f"TestSuite with id {suite_id} not found")

    # 1. Create Suite Snapshot
    # We use explicit field copying rather than __dict__ to be safe and explicit
    # about what is being snapshotted.
    suite_snapshot = TestSuiteSnapshot(
        original_suite_id=suite.id,
        name=suite.name,
        description=suite.description,
        tags=suite.tags.copy(),  # Deep copy tags
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    self.session.add(suite_snapshot)
    self.session.flush()  # Flush to get snapshot ID

    # 2. Fetch all live examples
    # We could likely optimize this with a bulk insert if needed, but for now
    # explicit object creation is safer and clearer.
    examples = self.example_repository.list_by_suite_id(test_suite_id=suite.id)

    # 3. Create Example Snapshots
    example_snapshots = []
    for example in examples:
      # Pydantic models (assertions) are converted to ORM via repository usually,
      # but here we are snapshotting existing models.
      # We rely on the DB value being correct.
      # We just copy the fields directly.
      # (No mapper needed here actually since we are Model -> ModelSnapshot, not Schema -> Model)
      asserts_snapshot = []
      for a in example.asserts:
        asserts_snapshot.append(
            AssertionSnapshot(
                original_assertion_id=a.id,
                type=a.type,
                weight=a.weight,
                params=a.params.copy(),
            )
        )

      example_snapshot = ExampleSnapshot(
          snapshot_suite_id=suite_snapshot.id,
          original_example_id=example.id,
          logical_id=example.logical_id,
          question=example.question,
          asserts=asserts_snapshot,
          created_at=datetime.datetime.now(datetime.timezone.utc),
      )
      example_snapshots.append(example_snapshot)

    self.session.add_all(example_snapshots)
    self.session.commit()

    return suite_snapshot
