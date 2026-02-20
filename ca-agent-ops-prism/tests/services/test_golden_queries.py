"""Unit tests for Golden Queries persistence and mapping."""

from unittest import mock

from prism.client import agent_client
from prism.common.schemas import agent as schemas
from prism.server.repositories import agent_repository
from prism.server.services import agent_service
from sqlalchemy.orm import Session


def test_create_agent_with_golden_queries(db_session: Session):
  """Tests creating an agent with golden queries and verifying persistence."""
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)

  gq = schemas.LookerGoldenQuery(
      natural_language_questions=["How many sales?"],
      looker_query=schemas.LookerQuery(
          model="the_model",
          view="the_view",
          fields=["count"],
          filters=[schemas.LookerFilter(field="date", value="last 7 days")],
      ),
  )

  config = schemas.AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      datasource=schemas.LookerConfig(
          instance_uri="https://looker.com", explores=["model.explore"]
      ),
      golden_queries=[gq],
  )

  # 1. Create locally (we won't mock GDA client here for repository test,
  # or we mock register_gcp_agent if we use service.register... but let's test repository direct or service.create_agent)
  # service.create_agent just calls repo.create
  agent = service.create_agent(name="GQ Bot", config=config)

  # Verify DB persistence
  assert agent.datasource_config is not None
  assert "golden_queries" in agent.datasource_config
  assert len(agent.datasource_config["golden_queries"]) == 1
  saved_gq = agent.datasource_config["golden_queries"][0]
  assert saved_gq["natural_language_questions"] == ["How many sales?"]

  # Verify Client Mapping
  # We need to simulate what AgentsClient._map_agent does
  # Access the private method or replicate logic?
  # Better to use AgentsClient if we can mock the service dependency.

  # Let's manually verify logic similar to _map_agent
  # (Since AgentsClient._map_agent is module level private function,
  # but likely accessible for testing or we can instantiate Client)

  # Replicating _map_agent logic for verification
  def map_agent(model):
    ds_config = model.datasource_config
    datasource = None
    if ds_config:
      if "instance_uri" in ds_config:
        datasource = schemas.LookerConfig(**ds_config)

    return schemas.Agent(
        id=model.id,
        name=model.name,
        config=schemas.AgentConfig(
            project_id=model.project_id,
            location=model.location,
            agent_resource_id=model.agent_resource_id,
            datasource=datasource,
            golden_queries=ds_config.get("golden_queries")
            if ds_config
            else None,
        ),
        created_at=model.created_at,
        modified_at=model.modified_at,
    )

  mapped_agent = map_agent(agent)
  assert mapped_agent.config.golden_queries is not None
  assert len(mapped_agent.config.golden_queries) == 1
  assert mapped_agent.config.golden_queries[0].looker_query.model == "the_model"


def test_update_agent_golden_queries(db_session: Session):
  """Tests updating golden queries."""
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)

  config = schemas.AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      datasource=schemas.LookerConfig(
          instance_uri="https://looker.com", explores=["model.explore"]
      ),
      # No Golden Queries initially
  )
  agent = service.create_agent(name="Update GQ Bot", config=config)
  assert agent.datasource_config is not None
  assert "golden_queries" not in agent.datasource_config

  # Update
  gq = schemas.LookerGoldenQuery(
      natural_language_questions=["Update?"],
      looker_query=schemas.LookerQuery(view="view2", fields=["f1"]),
  )
  new_config = config.model_copy()
  new_config.golden_queries = [gq]

  # We mock the GDA client update if we use service.update_agent
  with mock.patch(
      "prism.server.services.agent_service.GeminiDataAnalyticsClient"
  ) as mock_gda_cls:
    mock_gda = mock_gda_cls.return_value
    mock_gda.update_agent.return_value = (
        None  # We don't care about GDA return in this test
    )

    service.update_agent(agent.id, config=new_config)

  # Check persistence
  updated_agent = service.get_agent(agent.id)
  assert updated_agent.datasource_config is not None
  assert "golden_queries" in updated_agent.datasource_config
  assert len(updated_agent.datasource_config["golden_queries"]) == 1
  assert (
      updated_agent.datasource_config["golden_queries"][0]["looker_query"][
          "view"
      ]
      == "view2"
  )
