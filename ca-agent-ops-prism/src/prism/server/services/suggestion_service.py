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
from typing import Any

from prism.common.schemas import assertion as assertion_schemas
from prism.server.clients import gen_ai_client
from prism.server.config import settings
from prism.server.models import assertion as assertion_models
from prism.server.repositories import example_repository
from prism.server.repositories import trial_repository
import pydantic

# Path to the prompt template
PROMPT_TEMPLATE_PATH = "src/prism/server/services/prompts/suggestion_prompt.txt"


class SuggestionResponse(pydantic.BaseModel):
  """Schema for the LLM response containing a list of assertions."""

  assertions: list[assertion_schemas.AssertionRequest]


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
      logging.warning(
          "Suggestion %s not found, might have been already curated.",
          suggestion_id,
      )
      return

    if action == "accept":
      # Convert to permanent assertion
      trial = suggestion.trial
      if not trial or not trial.example_snapshot:
        raise ValueError("Suggestion not linked to a valid trial/question")

      q_id = trial.example_snapshot.original_example_id
      if not q_id:
        raise ValueError("Trial not linked to an original question")

      # Prepare data for schema
      a_data = {
          "type": suggestion.type,
          "weight": suggestion.weight,
          **suggestion.params,
      }

      # Validate into schema
      assertion_schema = pydantic.TypeAdapter(
          assertion_schemas.Assertion
      ).validate_python(a_data)

      self.example_repository.add_assertion(q_id, assertion_schema)

    # Delete the suggestion Regardless of accept or reject
    self.trial_repository.delete_suggestion(suggestion_id)

  def _load_prompt_template(self) -> str:
    """Loads the prompt template from the file system."""
    try:
      with open(PROMPT_TEMPLATE_PATH, "r") as f:
        return f.read()
    except FileNotFoundError:
      logging.error("Prompt template not found at %s", PROMPT_TEMPLATE_PATH)
      return ""

  def suggest_assertions(
      self,
      trial_id: int,
      existing_assertions: list[assertion_schemas.Assertion] | None = None,
  ) -> list[assertion_schemas.Assertion]:
    """Suggests assertions for a trial (Legacy Wrapper)."""
    trial = self.trial_repository.get_trial(trial_id)
    if not trial:
      return []

    # Convert trace_results to dicts if needed
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
    """Suggests assertions for a given trace."""
    existing_assertions = existing_assertions or []

    # Use call-specific client if location provided
    client = self.gen_ai_client
    if location and location != client.location:
      client = gen_ai_client.GenAIClient(
          project=settings.gcp_genai_project, location=location
      )

    # 1. LLM Generation
    llm_assertions = self._generate_llm_assertions(
        trace, existing_assertions, client=client
    )

    # 2. Looker Heuristics
    looker_assertions = self._generate_looker_assertions(trace)

    # 3. Combine and Deduplicate
    combined = llm_assertions + looker_assertions
    return self._deduplicate(combined, existing_assertions)

  def _generate_llm_assertions(
      self,
      trace: list[dict[str, Any]],
      existing_assertions: list[assertion_schemas.Assertion],
      client: gen_ai_client.GenAIClient | None = None,
  ) -> list[assertion_schemas.Assertion]:
    """Generates assertions using Gemini via Gen AI."""
    if not trace:
      return []

    # Use provided client or default
    v_client = client or self.gen_ai_client

    # Prepare context
    trace_json = json.dumps(trace, indent=2)
    existing_asserts_json = json.dumps(
        [a.model_dump(exclude={"id"}) for a in existing_assertions], indent=2
    )

    prompt = self._prompt_template.replace(
        "{{response_payload}}", trace_json
    ).replace("{{existing_assertions}}", existing_asserts_json)

    # Call LLM with structured decoding
    try:
      parsed_response = v_client.generate_structured(prompt, SuggestionResponse)

      if not parsed_response:
        return []

      return [self._convert_to_assertion(a) for a in parsed_response.assertions]

    except Exception as e:  # pylint: disable=broad-except
      logging.error("Error generating assertions: %s", e)
      return []

  def _convert_to_assertion(
      self, request_obj: Any
  ) -> assertion_schemas.Assertion:
    """Converts a request object (no ID) to a full assertion object (with ID)."""
    return pydantic.TypeAdapter(assertion_schemas.Assertion).validate_python(
        request_obj.model_dump()
    )

  def _generate_looker_assertions(
      self, trace_results: list[Any]
  ) -> list[assertion_schemas.Assertion]:
    """Generates deterministic assertions for Looker queries."""
    asserts = []
    if not trace_results:
      return asserts

    for item in trace_results:
      # Heuristic: navigate system_message.data.query.looker
      try:
        # Handle dict access (primary) or object access (fallback)
        if isinstance(item, dict):
          sys_msg = item.get("system_message", {})
          # nested dicts?
          if isinstance(sys_msg, dict):
            data = sys_msg.get("data", {})
          else:
            data = getattr(sys_msg, "data", {})

          if isinstance(data, dict):
            query = data.get("query", {})
          else:
            query = getattr(data, "query", {})

          if isinstance(query, dict):
            looker = query.get("looker")
          else:
            looker = getattr(query, "looker", None)
        else:
          # Object access
          looker = None
          if hasattr(item, "system_message"):
            sys_msg = item.system_message
            if hasattr(sys_msg, "data"):
              data = sys_msg.data
              if hasattr(data, "query"):
                query = data.query
                if hasattr(query, "looker"):
                  looker = query.looker

        if looker:
          # Convert to dict if proto/object
          looker_dict = dict(looker) if hasattr(looker, "keys") else looker
          if not isinstance(looker_dict, dict):
            # Try __dict__ or custom to_dict if needed
            try:
              looker_dict = dict(looker)
            except (ValueError, TypeError):
              looker_dict = {}

          if looker_dict:
            # 1. Normalize fields to match LookerQuerySchema
            looker_params = {}
            for k in [
                "model",
                "explore",
                "fields",
                "filters",
                "sorts",
                "limit",
            ]:
              if k in looker_dict:
                val = looker_dict[k]
                # 2. Normalize filters from dict to list[dict]
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

    # Pre-fill seen with existing
    for a in existing:
      seen_hashes.add(self._hash_assertion(a))

    for a in candidates:
      h = self._hash_assertion(a)
      if h not in seen_hashes:
        unique_asserts.append(a)
        seen_hashes.add(h)

    return unique_asserts

  def _hash_assertion(self, assertion: assertion_schemas.Assertion) -> str:
    """Creates a hashable string for an assertion."""
    # Dump config, sort keys
    return json.dumps(assertion.model_dump(exclude={"id"}), sort_keys=True)
