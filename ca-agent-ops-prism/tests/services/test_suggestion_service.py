"""Unit tests for SuggestionService."""

from unittest import mock
from prism.common.schemas import assertion as assertion_schemas
from prism.server.clients import gen_ai_client
from prism.server.models import assertion as assertion_models
from prism.server.repositories import example_repository
from prism.server.repositories import trial_repository
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
    # Allow attribute access for heuristics
    return MockObj(self.data.get("system_message", {}))


class MockObj(dict):
  """Dictionary wrapper that enables attribute access."""

  def __init__(self, d):
    super().__init__(d)
    self._d = d
    for k, v in d.items():
      if isinstance(v, dict):
        # Recursively wrap dicts
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
    """Provides a SuggestionService instance with mocked dependencies."""
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
    """Tests full flow including LLM suggestion and conversion."""
    trial = mock.MagicMock()
    trial.trace_results = [MockTraceItem({"foo": "bar"})]
    mock_trial_repo.get_trial.return_value = trial

    # Mock LLM response with objects
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
    """Tests deduplication against existing assertions."""
    trial = mock.MagicMock()
    trial.trace_results = [MockTraceItem()]
    mock_trial_repo.get_trial.return_value = trial

    # LLM suggests one new and one duplicate
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

  def test_looker_heuristics(
      self, service, mock_trial_repo, mock_gen_ai_client
  ):
    """Tests deterministic Looker assertion extraction."""
    trial = mock.MagicMock()
    # Construct a trace item that matches the heuristic path:
    # system_message.data.query.looker
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
    # Check specific fields instead of full dict match to avoid None-field noise
    params = result[0].params
    assert params.model == "the_model"
    assert params.explore == "the_explore"

  def test_suggest_assertions_bad_json(
      self, service, mock_trial_repo, mock_gen_ai_client
  ):
    """Tests handling of invalid JSON from LLM (returns None)."""
    trial = mock.MagicMock()
    trial.trace_results = [MockTraceItem()]
    mock_trial_repo.get_trial.return_value = trial

    # generate_structured returns None on failure in the client
    mock_gen_ai_client.generate_structured.return_value = None

    result = service.suggest_assertions(1)

    # Should safely return empty list
    assert not result

  def test_suggest_assertions_api_error(
      self, service, mock_trial_repo, mock_gen_ai_client
  ):
    """Tests handling of API error."""
    trial = mock.MagicMock()
    trial.trace_results = [MockTraceItem()]
    mock_trial_repo.get_trial.return_value = trial

    mock_gen_ai_client.generate_structured.side_effect = Exception(
        "Vertex Error"
    )

    result = service.suggest_assertions(1)
    assert not result

  def test_curate_suggestion_accept(
      self, service, mock_trial_repo, mock_example_repo
  ):
    """Tests accepting a suggested assertion."""
    suggestion = mock.MagicMock(spec=assertion_models.SuggestedAssertion)
    suggestion.type = "text-contains"
    suggestion.weight = 1.0
    suggestion.params = {"value": "test"}
    suggestion.trial.example_snapshot.original_example_id = 123

    mock_trial_repo.session.get.return_value = suggestion

    service.curate_suggestion(1, "accept")

    mock_example_repo.add_assertion.assert_called_once()
    args, _ = mock_example_repo.add_assertion.call_args
    assert args[0] == 123
    assert args[1].type == "text-contains"

    mock_trial_repo.delete_suggestion.assert_called_once_with(1)

  def test_curate_suggestion_reject(
      self, service, mock_trial_repo, mock_example_repo
  ):
    """Tests rejecting a suggested assertion."""
    suggestion = mock.MagicMock(spec=assertion_models.SuggestedAssertion)
    mock_trial_repo.session.get.return_value = suggestion

    service.curate_suggestion(1, "reject")

    mock_example_repo.add_assertion.assert_not_called()
    mock_trial_repo.delete_suggestion.assert_called_once_with(1)
