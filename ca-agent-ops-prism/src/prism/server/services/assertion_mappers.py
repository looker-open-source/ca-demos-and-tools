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

"""Conversions between the Assertion Pydantic schemas and SQLAlchemy models."""

from prism.common.schemas.assertion import Assertion as AssertionSchema
from prism.server.models.assertion import Assertion as AssertionModel
from prism.server.models.assertion import (
    AssertionSnapshot as AssertionSnapshotModel,
)
from prism.server.models.assertion import (
    SuggestedAssertion as SuggestedAssertionModel,
)
from pydantic import TypeAdapter


def model_to_schema(model: AssertionModel) -> AssertionSchema:
  """Converts a SQLAlchemy Assertion model to a Pydantic Assertion schema."""
  data = model.params.copy()
  data["type"] = model.type
  data["weight"] = model.weight
  data["id"] = model.id
  return TypeAdapter(AssertionSchema).validate_python(data)


def snapshot_model_to_schema(
    model: AssertionSnapshotModel,
) -> AssertionSchema:
  """Converts a SQLAlchemy AssertionSnapshot model to a Pydantic schema."""
  data = model.params.copy()
  data["type"] = model.type
  data["weight"] = model.weight
  data["id"] = model.id
  data["original_assertion_id"] = model.original_assertion_id
  return TypeAdapter(AssertionSchema).validate_python(data)


def schema_to_suggested_model(
    schema: AssertionSchema, trial_id: int
) -> SuggestedAssertionModel:
  """Converts a Pydantic Assertion schema to a SuggestedAssertion model."""
  data = schema.model_dump()
  assertion_type = data.pop("type")
  weight = data.pop("weight", 1.0)
  reasoning = data.pop("reasoning", None)
  # id belongs to the schema's own row, not to the suggestion. What is left
  # after the columns have been taken out is the JSON params blob.
  data.pop("id", None)
  params = data

  return SuggestedAssertionModel(
      trial_id=trial_id,
      type=assertion_type,
      weight=weight,
      params=params,
      reasoning=reasoning,
  )
