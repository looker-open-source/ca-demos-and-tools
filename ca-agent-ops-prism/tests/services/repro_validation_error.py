"""Reproduction test for LookerQueryMatch validation issue."""

from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.suite_service import SuiteService
import pytest
from sqlalchemy.orm import Session


@pytest.fixture
def suite_svc(db_session: Session):
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  return SuiteService(db_session, suite_repo, example_repo)


def test_sync_looker_query_match(suite_svc: SuiteService):
  """Tests that looker-query-match assertions can be synced without validation errors."""
  suite = suite_svc.create_suite(name="Looker Test")
  suite_id = suite.id

  questions = [{
      "question": "Show me orders in the last 30 days",
      "asserts": [{
          "type": "looker-query-match",
          "weight": 1.0,
          "params": {
              "model": "advanced_ecomm",
              "explore": "intermediate_example_ecommerce",
              "fields": ["order_items.created_at_date", "order_items.count"],
              "filters": [
                  {"field": "order_items.created_at_date", "value": "30 days"}
              ],
              "sorts": ["order_items.created_at_date asc"],
              "limit": "5000",
          },
      }],
  }]

  # This should NOT raise a ValidationError
  suite_svc.sync_suite(suite_id, questions)

  examples = suite_svc.list_examples(suite_id)
  assert len(examples) == 1
  assert examples[0].asserts[0].type == "looker-query-match"
  assert examples[0].asserts[0].params["params"]["model"] == "advanced_ecomm"
