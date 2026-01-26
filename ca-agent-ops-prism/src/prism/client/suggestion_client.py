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

"""Suggestion Client implementation."""

from typing import Any

from fast_depends import Depends
from fast_depends import inject
from prism.client import dependencies
from prism.common.schemas import assertion as assertion_schemas
from prism.server.services.suggestion_service import SuggestionService


class SuggestionClient:
  """Suggestion Client implementation."""

  @inject
  def suggest_assertions(
      self,
      trial_id: int,
      existing_assertions: list[assertion_schemas.Assertion] | None = None,
      service: SuggestionService = Depends(dependencies.get_suggestion_service),
  ) -> list[assertion_schemas.Assertion]:
    """Suggests assertions for a trial."""
    return service.suggest_assertions(
        trial_id=trial_id, existing_assertions=existing_assertions
    )

  @inject
  def curate_suggestion(
      self,
      suggestion_id: int,
      action: str,
      service: SuggestionService = Depends(dependencies.get_suggestion_service),
  ) -> None:
    """Accepts or rejects a suggested assertion."""
    service.curate_suggestion(suggestion_id=suggestion_id, action=action)

  @inject
  def suggest_assertions_from_trace(
      self,
      trace: list[dict[str, Any]],
      existing_assertions: list[assertion_schemas.Assertion] | None = None,
      location: str | None = None,
      service: SuggestionService = Depends(dependencies.get_suggestion_service),
  ) -> list[assertion_schemas.Assertion]:
    """Suggests assertions for a given trace."""
    return service.suggest_assertions_from_trace(
        trace=trace,
        existing_assertions=existing_assertions,
        location=location,
    )
