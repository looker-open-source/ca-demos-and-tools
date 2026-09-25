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

"""Unit tests for Golden Queries persistence and mapping."""

from unittest import mock

from prism.client import agent_client
from prism.common.schemas import agent as schemas
from prism.server.repositories import agent_repository
from prism.server.services import agent_service
from sqlalchemy.orm import Session


def test_create_agent_with_golden_queries(db_session: Session):
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)

  gq = schemas.LookerGoldenQuery(
      natural_language_questions=["How many sales?"],
      looker_query=schemas.LookerQuery(
          model="the_model",
          explore="the_view",
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

  # create_agent only writes locally, so no GDA client is needed here.
  agent = service.create_agent(name="GQ Bot", config=config)

  assert agent.datasource_config is not None
  assert "golden_queries" in agent.datasource_config
  assert len(agent.datasource_config["golden_queries"]) == 1
  saved_gq = agent.datasource_config["golden_queries"][0]
  assert saved_gq["natural_language_questions"] == ["How many sales?"]

  # The real mapper, private to agent_client but called here rather than
  # copied. A copy drifts, and the copy this replaced had already lost the
  # BigQuery branch, the Looker credentials and is_archived.
  # pylint: disable-next=protected-access
  mapped_agent = agent_client._map_agent(agent)
  assert mapped_agent.config.golden_queries is not None
  assert len(mapped_agent.config.golden_queries) == 1
  assert mapped_agent.config.golden_queries[0].looker_query.model == "the_model"


def test_update_agent_golden_queries(db_session: Session):
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)

  config = schemas.AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      datasource=schemas.LookerConfig(
          instance_uri="https://looker.com", explores=["model.explore"]
      ),
      # No golden queries yet, which is what the update has to add.
  )
  agent = service.create_agent(name="Update GQ Bot", config=config)
  assert agent.datasource_config is not None
  assert "golden_queries" not in agent.datasource_config

  gq = schemas.LookerGoldenQuery(
      natural_language_questions=["Update?"],
      looker_query=schemas.LookerQuery(explore="view2", fields=["f1"]),
  )
  new_config = config.model_copy()
  new_config.golden_queries = [gq]

  # Patch the GDA client so update_agent cannot reach GCP.
  with mock.patch(
      "prism.server.services.agent_service.GeminiDataAnalyticsClient"
  ) as mock_gda_cls:
    mock_gda = mock_gda_cls.return_value
    # Nothing here reads what GDA returns; the assertions are on the row.
    mock_gda.update_agent.return_value = None

    service.update_agent(agent.id, config=new_config)

  updated_agent = service.get_agent(agent.id)
  assert updated_agent.datasource_config is not None
  assert "golden_queries" in updated_agent.datasource_config
  assert len(updated_agent.datasource_config["golden_queries"]) == 1
  assert (
      updated_agent.datasource_config["golden_queries"][0]["looker_query"][
          "explore"
      ]
      == "view2"
  )
