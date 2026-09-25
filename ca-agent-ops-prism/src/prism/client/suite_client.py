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

"""Suites Client implementation."""

from typing import Any
from typing import Sequence

from fast_depends import Depends
from fast_depends import inject
from prism.client import dependencies
from prism.common.schemas import example as example_schemas
from prism.common.schemas import suite as suite_schemas
from prism.common.schemas.assertion import AssertionRequest
from prism.common.schemas.suite import SuiteDetail
from prism.server.services import validation_service
from prism.server.services.bulk_import_service import BulkImportService
from prism.server.services.suite_service import SuiteService


def _map_suite(model: Any) -> suite_schemas.Suite:
  return suite_schemas.Suite.model_validate(model)


def _map_suite_detail(model: Any) -> SuiteDetail:
  return SuiteDetail.model_validate(model)


class SuitesClient:
  """Suites, the examples in them, and bulk import of both."""

  @inject
  def list_suites(
      self,
      include_archived: bool = False,
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> Sequence[suite_schemas.Suite]:
    """Lists test suites, archived ones only when asked for."""

    models = service.list_suites(include_archived=include_archived)
    return [_map_suite(m) for m in models]

  @inject
  def get_suite(
      self,
      suite_id: int,
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> SuiteDetail | None:
    """Gets a suite and its live examples, or None if there is no such suite."""

    model = service.get_suite(suite_id)
    if not model:
      return None

    detail = _map_suite_detail(model)
    # The backref the validation above reads is unfiltered, and a delete here
    # is an archive. A suite three of whose ten questions were deleted counted
    # ten in the Run Evaluation modal and then ran seven trials. Every other
    # read path goes through list_examples.
    detail.examples = [
        example_schemas.Example.model_validate(e)
        for e in service.list_examples(suite_id, include_archived=False)
    ]
    return detail

  @inject
  def get_suites_with_stats(
      self,
      include_archived: bool = False,
      coverage: str | None = None,
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> list[suite_schemas.SuiteWithStats]:
    """Gets all test suites with their coverage stats."""
    return service.get_suites_with_stats(
        include_archived=include_archived, coverage=coverage
    )

  @inject
  def create_suite(
      self,
      name: str,
      description: str | None = None,
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> suite_schemas.Suite:
    """Creates a suite and returns it with the id the database assigned."""

    model = service.create_suite(name=name, description=description)
    return _map_suite(model)

  @inject
  def update_suite(
      self,
      suite_id: int,
      name: str | None = None,
      description: str | None = None,
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> suite_schemas.Suite:
    """Updates a suite. A field left as None keeps its current value."""

    model = service.update_suite(
        suite_id=suite_id, name=name, description=description
    )
    return _map_suite(model)

  @inject
  def archive_suite(
      self,
      suite_id: int,
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> suite_schemas.Suite:
    """Hides a suite from the default listing. Nothing is deleted."""
    model = service.archive_suite(suite_id=suite_id)
    return _map_suite(model)

  @inject
  def unarchive_suite(
      self,
      suite_id: int,
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> suite_schemas.Suite:
    """Puts an archived suite back in the default listing."""
    model = service.unarchive_suite(suite_id=suite_id)
    return _map_suite(model)

  @inject
  def list_examples(
      self,
      suite_id: int,
      include_archived: bool = False,
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> Sequence[example_schemas.Example]:
    """Lists a suite's examples, archived ones only when asked for."""
    models = service.list_examples(
        suite_id=suite_id, include_archived=include_archived
    )
    return [example_schemas.Example.model_validate(m) for m in models]

  @inject
  def sync_suite(
      self,
      suite_id: int,
      questions: list[dict[str, Any]],
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> list[dict[str, Any]]:
    """Makes a suite's examples match the questions given.

    Questions carrying an id are updated, the rest are added, and any example
    not in the list is archived. Returns the saved questions, which is how the
    builder learns the ids of the ones it just added.
    """
    return service.sync_suite(suite_id=suite_id, questions=questions)

  @inject
  def add_example(
      self,
      suite_id: int,
      question: str,
      asserts: list[AssertionRequest] | None = None,
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> example_schemas.Example:
    """Adds a question, with any assertions it already has, to a suite."""
    example = service.add_example(suite_id, question, asserts or [])
    return example_schemas.Example.model_validate(example)

  @inject
  def delete_example(
      self,
      example_id: int,
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> None:
    """Archives an example. The row is kept, the default listings hide it."""
    service.delete_example(example_id)

  def validate_assertion(
      self,
      assertion_data: dict[str, Any],
  ) -> str | None:
    """Returns why an assertion is invalid, or None if it validates."""
    return validation_service.validate_assertion(assertion_data)

  def parse_yaml_safely(
      self,
      yaml_str: str,
  ) -> tuple[dict[str, Any] | None, str | None]:
    """Parses YAML into a mapping, returning (data, error_message).

    Never raises. An empty string gives ({}, None). Anything that is not YAML,
    or is YAML but not a mapping, gives (None, message) for the form to show.
    """
    return validation_service.parse_yaml_safely(yaml_str)

  @inject
  def format_bulk_import_with_ai(
      self,
      text: str,
      service: BulkImportService = Depends(
          dependencies.get_bulk_import_service
      ),
  ) -> str:
    """Asks Gemini to rewrite pasted text as bulk import YAML."""
    return service.format_with_ai(text)

  @inject
  def parse_bulk_import_yaml(
      self,
      yaml_str: str,
      service: BulkImportService = Depends(
          dependencies.get_bulk_import_service
      ),
  ) -> list[example_schemas.TestCaseInput]:
    """Parses bulk import YAML into TestCaseInput models."""
    return service.parse_yaml(yaml_str)
