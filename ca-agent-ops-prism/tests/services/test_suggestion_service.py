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

"""Unit tests for SuggestionService."""

from unittest import mock
from prism.common.schemas import assertion as assertion_schemas
from prism.server.clients import gen_ai_client
from prism.server.models import assertion as assertion_models
from prism.server.repositories import example_repository
from prism.server.repositories import trial_repository
from prism.server.services import assert_engine
from prism.server.services import suggestion_service
import pytest


class MockTraceItem:
  """Mock item for trace results."""

  def __init__(self, data=None):
    self.data = data or {}

  def to_dict(self):
    return self.data

  @property
  def system_message(self):
    # The heuristics reach into the trace by attribute, so a plain dict will
    # not do.
    return MockObj(self.data.get("system_message", {}))


class MockObj(dict):
  """Dictionary wrapper that enables attribute access."""

  def __init__(self, d):
    super().__init__(d)
    self._d = d
    for k, v in d.items():
      if isinstance(v, dict):
        wrapper = MockObj(v)
        setattr(self, k, wrapper)
        self[k] = wrapper
      else:
        setattr(self, k, v)
        self[k] = v

  def __getattr__(self, item):
    return self.get(item)

  def to_dict(self):
    return self._d


class TestSuggestionService:
  """Unit tests for the SuggestionService."""

  @pytest.fixture
  def mock_gen_ai_client(self):
    return mock.MagicMock(spec=gen_ai_client.GenAIClient)

  @pytest.fixture
  def mock_trial_repo(self):
    repo = mock.MagicMock(spec=trial_repository.TrialRepository)
    repo.session = mock.MagicMock()
    return repo

  @pytest.fixture
  def mock_example_repo(self):
    return mock.MagicMock(spec=example_repository.ExampleRepository)

  @pytest.fixture
  def service(self, mock_gen_ai_client, mock_trial_repo, mock_example_repo):
    """A SuggestionService whose prompt file is patched out."""
    with mock.patch(
        "prism.server.services.suggestion_service.PROMPT_TEMPLATE_PATH",
        "fake_path",
    ):
      with mock.patch(
          "builtins.open", new_callable=mock.MagicMock
      ) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = (
            "Prompt {{response_payload}} {{existing_assertions}}"
        )
        return suggestion_service.SuggestionService(
            mock_gen_ai_client, mock_trial_repo, mock_example_repo
        )

  def test_suggest_assertions_llm_flow(
      self, service, mock_trial_repo, mock_gen_ai_client
  ):
    """The LLM's dicts come back as typed assertion schemas."""
    trial = mock.MagicMock()
    trial.trace_results = [MockTraceItem({"foo": "bar"})]
    mock_trial_repo.get_trial.return_value = trial

    mock_gen_ai_client.generate_structured.return_value = (
        suggestion_service.SuggestionResponse(
            assertions=[
                {"type": "text-contains", "value": "some text"},
                {"type": "data-check-row-count", "value": 5},
            ]
        )
    )

    result = service.suggest_assertions(1)

    assert len(result) == 2
    assert isinstance(result[0], assertion_schemas.TextContains)
    assert result[0].value == "some text"
    assert result[1].value == 5

  def test_suggest_assertions_dedup(
      self, service, mock_trial_repo, mock_gen_ai_client
  ):
    trial = mock.MagicMock()
    trial.trace_results = [MockTraceItem()]
    mock_trial_repo.get_trial.return_value = trial

    # One new and one the user already has.
    mock_gen_ai_client.generate_structured.return_value = (
        suggestion_service.SuggestionResponse(
            assertions=[
                {"type": "text-contains", "value": "new"},
                {"type": "text-contains", "value": "existing"},
            ]
        )
    )

    existing = [assertion_schemas.TextContains(value="existing")]
    result = service.suggest_assertions(1, existing_assertions=existing)

    assert len(result) == 1
    assert result[0].value == "new"

  def test_a_snapshot_assertion_dedups_the_looker_candidate(
      self, service, mock_trial_repo, mock_gen_ai_client
  ):
    """The existing assertions of a run arrive with their ids filled in.

    They come from snapshot_model_to_schema, which sets original_assertion_id
    to the live row it was copied from, while a candidate built off the trace
    has None. Hashing that field meant no seed hash ever matched, so the panel
    offered a Looker assertion the question already had on every run. The LLM
    branch hid it, because the prompt lists the existing assertions too, but
    the Looker branch is deterministic.
    """
    looker = {"model": "the_model", "explore": "the_explore"}
    trial = mock.MagicMock()
    trial.trace_results = [
        MockTraceItem(
            {"system_message": {"data": {"query": {"looker": looker}}}}
        )
    ]
    mock_trial_repo.get_trial.return_value = trial

    mock_gen_ai_client.generate_structured.return_value = (
        suggestion_service.SuggestionResponse(assertions=[])
    )

    existing = [
        assertion_schemas.LookerQueryMatch(
            id=12, original_assertion_id=7, params=looker
        )
    ]
    result = service.suggest_assertions(1, existing_assertions=existing)

    assert not result

  def test_an_existing_assertion_dedups_whatever_its_reasoning_and_weight(
      self, service, mock_trial_repo, mock_gen_ai_client
  ):
    """Neither field changes what the assertion checks.

    An assertion accepted from a suggestion keeps the reasoning it was accepted
    with, and the weight is the user's to tune. Both used to be in the hash, so
    the same check came back as a suggestion for as long as the question held
    it.
    """
    trial = mock.MagicMock()
    trial.trace_results = [MockTraceItem()]
    mock_trial_repo.get_trial.return_value = trial

    mock_gen_ai_client.generate_structured.return_value = (
        suggestion_service.SuggestionResponse(
            assertions=[{"type": "text-contains", "value": "existing"}]
        )
    )

    existing = [
        assertion_schemas.TextContains(
            value="existing",
            reasoning="Quoted in the final answer.",
            weight=3.0,
        )
    ]
    result = service.suggest_assertions(1, existing_assertions=existing)

    assert not result

  def test_looker_heuristics(
      self, service, mock_trial_repo, mock_gen_ai_client
  ):
    """The Looker assertion comes from the trace, not the LLM."""
    trial = mock.MagicMock()
    # The path the heuristic looks down, system_message.data.query.looker.
    trace_data = {
        "system_message": {
            "data": {
                "query": {
                    "looker": {"model": "the_model", "explore": "the_explore"}
                }
            }
        }
    }
    trial.trace_results = [MockTraceItem(trace_data)]
    mock_trial_repo.get_trial.return_value = trial

    mock_gen_ai_client.generate_structured.return_value = (
        suggestion_service.SuggestionResponse(assertions=[])
    )

    result = service.suggest_assertions(1)

    assert len(result) == 1
    assert isinstance(result[0], assertion_schemas.LookerQueryMatch)
    # Field by field, because the schema fills every other key with None and
    # a whole-dict comparison would be mostly Nones.
    params = result[0].params
    assert params.model == "the_model"
    assert params.explore == "the_explore"

  def test_suggest_assertions_bad_json(
      self, service, mock_trial_repo, mock_gen_ai_client
  ):
    """Bad JSON reaches the service as None, and yields no suggestions."""
    trial = mock.MagicMock()
    trial.trace_results = [MockTraceItem()]
    mock_trial_repo.get_trial.return_value = trial

    # The client swallows a parse failure and returns None.
    mock_gen_ai_client.generate_structured.return_value = None

    result = service.suggest_assertions(1)

    assert not result

  def test_suggest_assertions_api_error(
      self, service, mock_trial_repo, mock_gen_ai_client
  ):
    """An API error yields no suggestions, not an exception."""
    trial = mock.MagicMock()
    trial.trace_results = [MockTraceItem()]
    mock_trial_repo.get_trial.return_value = trial

    mock_gen_ai_client.generate_structured.side_effect = Exception(
        "Vertex Error"
    )

    result = service.suggest_assertions(1)
    assert not result

  def test_a_large_trace_is_cut_to_the_judges_budget(
      self, service, mock_gen_ai_client
  ):
    """A trial that answered with a big table cannot be sent whole.

    The trace went into the prompt unbounded. A table of a few thousand rows
    built a request the model refused, the broad except logged it, and the
    playground showed no suggestions at all.
    """
    mock_gen_ai_client.generate_structured.return_value = (
        suggestion_service.SuggestionResponse(assertions=[])
    )
    huge = [{"system_message": {"text": {"parts": ["x" * 500000]}}}]

    service.suggest_assertions_from_trace(huge)

    prompt = mock_gen_ai_client.generate_structured.call_args[0][0]
    # The template and the empty existing-assertions list are the only other
    # things in there, so the budget is what bounds this.
    assert len(prompt) < assert_engine.AI_JUDGE_TRACE_CHAR_BUDGET + 500
    assert "truncated" in prompt

  def test_an_agent_location_still_goes_to_the_configured_client(
      self, service, mock_gen_ai_client
  ):
    """A GDA location is not a Vertex GenAI region.

    "global", "us" and "eu" are all valid agent locations and none of them
    resolve as a region here. The suggester used to build a client of its own
    on the agent's location, that client raised, the broad except logged it,
    and the playground showed no suggestions. The configured client is the only
    one that resolves, so it is the one that has to be asked.

    Asserting that no GenAIClient was constructed proves nothing here, because
    nothing in the service names the constructor any more. Asserting on the
    call production makes does: a suggester that routed by location would leave
    the configured client untouched and come back empty.
    """
    mock_gen_ai_client.generate_structured.return_value = (
        suggestion_service.SuggestionResponse(
            assertions=[{"type": "text-contains", "value": "some text"}]
        )
    )

    result = service.suggest_assertions_from_trace(
        [{"foo": "bar"}], location="global"
    )

    mock_gen_ai_client.generate_structured.assert_called_once()
    assert [a.value for a in result] == ["some text"]

  def test_curate_suggestion_accept(
      self, service, mock_trial_repo, mock_example_repo
  ):
    suggestion = mock.MagicMock(spec=assertion_models.SuggestedAssertion)
    suggestion.type = "text-contains"
    suggestion.weight = 1.0
    suggestion.params = {"value": "test"}
    suggestion.reasoning = None
    suggestion.trial.example_snapshot.original_example_id = 123

    mock_trial_repo.session.get.return_value = suggestion

    service.curate_suggestion(1, "accept")

    mock_example_repo.add_assertion.assert_called_once()
    args, _ = mock_example_repo.add_assertion.call_args
    assert args[0] == 123
    assert args[1].type == "text-contains"

    mock_trial_repo.delete_suggestion.assert_called_once_with(1)

  def test_accepting_a_suggestion_carries_its_reasoning_over(
      self, service, mock_trial_repo, mock_example_repo
  ):
    """The caption the user read is the only record of why the check exists.

    schema_to_suggested_model lifts reasoning out of the dump and onto its own
    column, so an accept that rebuilt the assertion from params alone wrote it
    with no reasoning. The suggestion row is deleted in the same call, so there
    was nothing left to recover it from.
    """
    reasoning = "The trace quotes this figure in the final answer."
    suggestion = mock.MagicMock(spec=assertion_models.SuggestedAssertion)
    suggestion.type = "text-contains"
    suggestion.weight = 1.0
    suggestion.params = {"value": "test"}
    suggestion.reasoning = reasoning
    suggestion.trial.example_snapshot.original_example_id = 123

    mock_trial_repo.session.get.return_value = suggestion

    service.curate_suggestion(1, "accept")

    args, _ = mock_example_repo.add_assertion.call_args
    assert args[1].reasoning == reasoning

  def test_curate_suggestion_reject(
      self, service, mock_trial_repo, mock_example_repo
  ):
    """Rejecting drops the suggestion and adds no assertion."""
    suggestion = mock.MagicMock(spec=assertion_models.SuggestedAssertion)
    mock_trial_repo.session.get.return_value = suggestion

    service.curate_suggestion(1, "reject")

    mock_example_repo.add_assertion.assert_not_called()
    mock_trial_repo.delete_suggestion.assert_called_once_with(1)

  def test_suggest_assertions_data_check_row_column_matches(
      self, service, mock_trial_repo, mock_gen_ai_client
  ):
    """List of ColumnMatch entries converts to DataCheckRow with dict columns."""
    trial = mock.MagicMock()
    trial.trace_results = [MockTraceItem({"data": "sample"})]
    mock_trial_repo.get_trial.return_value = trial

    mock_gen_ai_client.generate_structured.return_value = (
        suggestion_service.SuggestionResponse(
            assertions=[{
                "type": "data-check-row",
                "columns": [
                    {"column": "user_id", "value": 42},
                    {"column": "status", "value": "active"},
                ],
            }]
        )
    )

    result = service.suggest_assertions(1)
    assert len(result) == 1
    assert isinstance(result[0], assertion_schemas.DataCheckRow)
    assert result[0].columns == {"user_id": 42, "status": "active"}

  def test_suggest_assertions_data_check_row_dict_columns(
      self, service, mock_trial_repo, mock_gen_ai_client
  ):
    """Dict columns are also accepted by DataCheckRowSuggestionSchema validator."""
    trial = mock.MagicMock()
    trial.trace_results = [MockTraceItem({"data": "sample"})]
    mock_trial_repo.get_trial.return_value = trial

    mock_gen_ai_client.generate_structured.return_value = (
        suggestion_service.SuggestionResponse(
            assertions=[{
                "type": "data-check-row",
                "columns": {"score": 95},
            }]
        )
    )

    result = service.suggest_assertions(1)
    assert len(result) == 1
    assert isinstance(result[0], assertion_schemas.DataCheckRow)
    assert result[0].columns == {"score": 95}

  def test_suggest_assertions_skips_invalid_assertion(
      self, service, mock_trial_repo, mock_gen_ai_client
  ):
    """Invalid suggestion items are skipped without failing the entire batch."""
    trial = mock.MagicMock()
    trial.trace_results = [MockTraceItem({"data": "sample"})]
    mock_trial_repo.get_trial.return_value = trial

    mock_gen_ai_client.generate_structured.return_value = (
        suggestion_service.SuggestionResponse(
            assertions=[
                {"type": "text-contains", "value": "valid text"},
                {
                    "type": "data-check-row",
                    "columns": [{"column": "", "value": "empty_key"}],
                },
            ]
        )
    )

    result = service.suggest_assertions(1)
    assert len(result) == 1
    assert result[0].value == "valid text"
