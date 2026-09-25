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

"""Service for suggesting assertions for a given trial."""

import json
import logging
import os
from typing import Annotated, Any, Literal, Union

from prism.common.schemas import assertion as assertion_schemas
from prism.server.clients import gen_ai_client
from prism.server.models import assertion as assertion_models
from prism.server.repositories import example_repository
from prism.server.repositories import trial_repository
from prism.server.services import assert_engine
import pydantic

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "prompts", "suggestion_prompt.txt"
)

# What the dedup hash ignores, so two assertions compare by what they check.
# id and original_assertion_id are row identity. The existing assertions handed
# in during a run come from snapshot_model_to_schema and carry a real
# original_assertion_id, while a fresh candidate carries None, so hashing them
# meant no seed hash ever matched: the Looker heuristic offered an assertion
# the question already had on every run. reasoning is the prose that came with
# one suggestion, and an accepted assertion keeps the reasoning it was accepted
# with. weight is a scoring knob, so a re-weighted assertion is still one the
# question already has.
HASH_EXCLUDED_FIELDS = {"id", "original_assertion_id", "reasoning", "weight"}


class ColumnMatch(pydantic.BaseModel):
  """Single column-value match for row data assertion."""

  column: str
  value: Any


class DataCheckRowSuggestionSchema(assertion_schemas.AssertionSchema):
  """Schema for LLM-suggested row check assertions.

  Uses an explicit list of ColumnMatch items so constrained decoding on
  models like gemini-3.8-flash enforces key-value emission instead of
  collapsing to an empty object.
  """

  type: Literal[assertion_schemas.AssertionType.DATA_CHECK_ROW] = (
      assertion_schemas.AssertionType.DATA_CHECK_ROW
  )
  columns: list[ColumnMatch] = pydantic.Field(min_length=1)

  @pydantic.field_validator("columns", mode="before")
  @classmethod
  def parse_columns(cls, v: Any) -> list[Any]:
    if isinstance(v, dict):
      return [{"column": k, "value": val} for k, val in v.items()]
    return v


SuggestionAssertionRequest = Annotated[
    Union[
        assertion_schemas.TextContainsSchema,
        assertion_schemas.QueryContainsSchema,
        assertion_schemas.ChartCheckTypeSchema,
        assertion_schemas.DurationMaxMsSchema,
        assertion_schemas.LatencyMaxMsSchema,
        assertion_schemas.DataCheckRowCountSchema,
        DataCheckRowSuggestionSchema,
        assertion_schemas.AIJudgeSchema,
    ],
    pydantic.Discriminator("type"),
]


class SuggestionResponse(pydantic.BaseModel):
  """Schema for the LLM response containing a list of assertions."""

  assertions: list[SuggestionAssertionRequest] = pydantic.Field(
      default_factory=list, max_length=10
  )


class SuggestionService:
  """Service for suggesting assertions using generative AI and heuristics."""

  def __init__(
      self,
      gen_ai_client_inst: gen_ai_client.GenAIClient,
      trial_repo: trial_repository.TrialRepository,
      example_repo: example_repository.ExampleRepository,
  ):
    self.gen_ai_client = gen_ai_client_inst
    self.trial_repository = trial_repo
    self.example_repository = example_repo
    self._prompt_template = self._load_prompt_template()

  def curate_suggestion(self, suggestion_id: int, action: str) -> None:
    """Accepts or rejects a suggested assertion."""
    suggestion = self.trial_repository.session.get(
        assertion_models.SuggestedAssertion, suggestion_id
    )
    if not suggestion:
      logger.warning(
          "Suggestion %s not found, might have been already curated.",
          suggestion_id,
      )
      return

    if action == "accept":
      # The suggestion hangs off the trial, so accepting it means writing a
      # real assertion onto the question the trial's snapshot came from.
      trial = suggestion.trial
      if not trial or not trial.example_snapshot:
        raise ValueError("Suggestion not linked to a valid trial/question")

      q_id = trial.example_snapshot.original_example_id
      if not q_id:
        raise ValueError("Trial not linked to an original question")

      # Columns last, so a params copy of one cannot override the row.
      # reasoning is a column too: schema_to_suggested_model lifts it out of
      # the dump, so rebuilding from params alone wrote the assertion with no
      # reasoning, and the suggestion row is deleted below, so the
      # justification the card was captioned with was gone.
      a_data = {
          **suggestion.params,
          "type": suggestion.type,
          "weight": suggestion.weight,
          "reasoning": suggestion.reasoning,
      }

      assertion_schema = pydantic.TypeAdapter(
          assertion_schemas.Assertion
      ).validate_python(a_data)

      self.example_repository.add_assertion(q_id, assertion_schema)

    # Both accept and reject consume the suggestion.
    self.trial_repository.delete_suggestion(suggestion_id)

  def _load_prompt_template(self) -> str:
    """Loads the prompt template from the file system.

    A missing template is a packaging fault, not a runtime condition. Swallowing
    it would send the model an empty prompt and report whatever came back as a
    result, so let it raise.
    """
    with open(PROMPT_TEMPLATE_PATH, "r") as f:
      return f.read()

  def suggest_assertions(
      self,
      trial_id: int,
      existing_assertions: list[assertion_schemas.Assertion] | None = None,
  ) -> list[assertion_schemas.Assertion]:
    """Reads the trace off a stored trial and suggests against it.

    Returns an empty list when there is no such trial.
    """
    trial = self.trial_repository.get_trial(trial_id)
    if not trial:
      return []

    # trace_results comes back as dicts from the JSON column, but a caller
    # that has just built the trial in memory may still be holding protos.
    trace = [
        t.to_dict() if hasattr(t, "to_dict") else t
        for t in trial.trace_results or []
    ]
    return self.suggest_assertions_from_trace(trace, existing_assertions)

  def suggest_assertions_from_trace(
      self,
      trace: list[dict[str, Any]],
      existing_assertions: list[assertion_schemas.Assertion] | None = None,
      location: str | None = None,
  ) -> list[assertion_schemas.Assertion]:
    """Suggests assertions for a given trace.

    location is the agent's GDA location, and it is not used. It used to build
    a GenAIClient of its own so the suggester ran near the agent, but a GDA
    location is not a Vertex GenAI region: "global", "us" and "eu" are all
    valid there and none of them resolve here. That client failed, the broad
    except in _generate_llm_assertions swallowed it, and the playground showed
    no suggestions. The configured Vertex location is the only one that works,
    and self.gen_ai_client is already on it.
    """
    del location

    existing_assertions = existing_assertions or []

    llm_assertions = self._generate_llm_assertions(trace, existing_assertions)

    looker_assertions = self._generate_looker_assertions(trace)

    combined = llm_assertions + looker_assertions
    return self._deduplicate(combined, existing_assertions)

  def _generate_llm_assertions(
      self,
      trace: list[dict[str, Any]],
      existing_assertions: list[assertion_schemas.Assertion],
  ) -> list[assertion_schemas.Assertion]:
    """Generates assertions using Gemini via Gen AI."""
    if not trace:
      return []

    # Under the judge's budget, for the judge's reason: a trial that answered
    # with a large table dumped millions of tokens into the prompt, the model
    # rejected it, and the except below turned that into no suggestions at all.
    trace_json = assert_engine.trace_for_prompt(trace)
    existing_asserts_json = json.dumps(
        [a.model_dump(exclude={"id"}) for a in existing_assertions], indent=2
    )

    prompt = self._prompt_template.replace(
        "{{response_payload}}", trace_json
    ).replace("{{existing_assertions}}", existing_asserts_json)

    try:
      parsed_response = self.gen_ai_client.generate_structured(
          prompt, SuggestionResponse
      )

      if not parsed_response:
        return []

      assertions = []
      for a in parsed_response.assertions:
        try:
          converted = self._convert_to_assertion(a)
          if converted:
            assertions.append(converted)
        except Exception as e:
          logger.warning("Skipping invalid suggested assertion %s: %s", a, e)

      return assertions

    except Exception as e:  # pylint: disable=broad-except
      logger.error("Error generating assertions: %s", e)
      return []

  def _convert_to_assertion(
      self, request_obj: Any
  ) -> assertion_schemas.Assertion:
    """Revalidates a request schema as the persisted Assertion union."""
    dump = (
        request_obj.model_dump()
        if hasattr(request_obj, "model_dump")
        else dict(request_obj)
    )
    if dump.get("type") == assertion_schemas.AssertionType.DATA_CHECK_ROW:
      cols = dump.get("columns", [])
      if isinstance(cols, list):
        dump["columns"] = {
            item["column"]: item["value"]
            for item in cols
            if isinstance(item, dict) and "column" in item and item["column"]
        }
    return pydantic.TypeAdapter(assertion_schemas.Assertion).validate_python(
        dump
    )

  def _generate_looker_assertions(
      self, trace_results: list[Any]
  ) -> list[assertion_schemas.Assertion]:
    """Generates deterministic assertions for Looker queries."""
    asserts = []
    if not trace_results:
      return asserts

    for item in trace_results:
      # A Looker query shows up at system_message.data.query.looker. Every
      # caller hands this dicts: either straight off the trace_results JSON
      # column, or converted before the call.
      try:
        if not isinstance(item, dict):
          continue

        sys_msg = item.get("system_message") or {}
        data = sys_msg.get("data") or {}
        query = data.get("query") or {}
        looker = query.get("looker")

        if isinstance(looker, dict) and looker:
          # Only the fields LookerQuerySchema has, in its shapes.
          looker_params = {}
          for k in ["model", "explore", "fields", "filters", "sorts", "limit"]:
            if k in looker:
              val = looker[k]
              if k == "filters" and isinstance(val, dict):
                val = [
                    {"field": str(fk), "value": fv} for fk, fv in val.items()
                ]
              looker_params[k] = val

          asserts.append(
              assertion_schemas.LookerQueryMatch(params=looker_params)
          )

      except Exception:  # pylint: disable=broad-except
        continue

    return asserts

  def _deduplicate(
      self,
      candidates: list[assertion_schemas.Assertion],
      existing: list[assertion_schemas.Assertion],
  ) -> list[assertion_schemas.Assertion]:
    """Deduplicates candidates against themselves and existing assertions."""
    unique_asserts = []
    seen_hashes = set()

    # Seed with what the question already has, so a candidate that matches an
    # existing assertion is not suggested again.
    for a in existing:
      seen_hashes.add(self._hash_assertion(a))

    for a in candidates:
      h = self._hash_assertion(a)
      if h not in seen_hashes:
        unique_asserts.append(a)
        seen_hashes.add(h)

    return unique_asserts

  def _hash_assertion(self, assertion: assertion_schemas.Assertion) -> str:
    """Creates a hashable string for what an assertion checks."""
    return json.dumps(
        assertion.model_dump(exclude=HASH_EXCLUDED_FIELDS), sort_keys=True
    )
