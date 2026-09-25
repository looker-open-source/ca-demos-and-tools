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

"""Editing an agent's datasource must not delete its golden queries.

Golden queries have no column. They live inside datasource_config, and update()
replaced that dict wholesale from config.datasource. The restore below it was
gated on `config.golden_queries is not None`, while AgentConfig defaults the
field to None, so an edit form that changed the explore and said nothing about
golden queries wiped every one of them. The next run then evaluated an agent
Prism believed had none, and its check_looker_query_match assertions all
failed.

The fix is the keep-if-absent distinction the location field two lines up
already uses: model_fields_set, not a None check.
"""

from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import LookerConfig
from prism.common.schemas.agent import LookerGoldenQuery
from prism.common.schemas.agent import LookerQuery
from prism.server.repositories.agent_repository import AgentRepository
from sqlalchemy.orm import Session

_INSTANCE = "https://looker.example.com"


def _golden_query(question: str, explore: str) -> LookerGoldenQuery:
  return LookerGoldenQuery(
      natural_language_questions=[question],
      looker_query=LookerQuery(model="thelook", explore=explore),
  )


def _agent_with_golden_queries(session: Session):
  """A Looker agent on the orders explore with two golden queries."""
  repo = AgentRepository(session)
  config = AgentConfig(
      project_id="p",
      location="us-central1",
      agent_resource_id="r",
      datasource=LookerConfig(instance_uri=_INSTANCE, explores=["orders"]),
      golden_queries=[
          _golden_query("How many orders?", "orders"),
          _golden_query("Revenue last week?", "orders"),
      ],
  )
  return repo, repo.create(name="Looker Bot", config=config)


def test_changing_the_explore_keeps_the_stored_golden_queries(
    db_session: Session,
):
  """The concrete report: orders to order_items, and the queries vanished."""
  repo, agent = _agent_with_golden_queries(db_session)

  repo.update(
      agent.id,
      config=AgentConfig(
          project_id="p",
          agent_resource_id="r",
          datasource=LookerConfig(
              instance_uri=_INSTANCE, explores=["order_items"]
          ),
      ),
  )

  db_session.expire_all()
  stored = repo.get_by_id(agent.id).datasource_config
  assert stored["explores"] == ["order_items"]
  assert len(stored["golden_queries"]) == 2
  assert stored["golden_queries"][0]["natural_language_questions"] == [
      "How many orders?"
  ]


def test_passing_golden_queries_replaces_the_stored_ones(db_session: Session):
  """Keep-if-absent is only useful if present still means replace."""
  repo, agent = _agent_with_golden_queries(db_session)

  repo.update(
      agent.id,
      config=AgentConfig(
          project_id="p",
          agent_resource_id="r",
          datasource=LookerConfig(instance_uri=_INSTANCE, explores=["orders"]),
          golden_queries=[_golden_query("Top brands?", "products")],
      ),
  )

  db_session.expire_all()
  stored = repo.get_by_id(agent.id).datasource_config
  assert len(stored["golden_queries"]) == 1
  assert stored["golden_queries"][0]["natural_language_questions"] == [
      "Top brands?"
  ]


def test_passing_an_empty_list_of_golden_queries_clears_them(
    db_session: Session,
):
  """The delete-all case. An empty list is a caller saying so."""
  repo, agent = _agent_with_golden_queries(db_session)

  repo.update(
      agent.id,
      config=AgentConfig(
          project_id="p",
          agent_resource_id="r",
          datasource=LookerConfig(instance_uri=_INSTANCE, explores=["orders"]),
          golden_queries=[],
      ),
  )

  db_session.expire_all()
  assert repo.get_by_id(agent.id).datasource_config["golden_queries"] == []


def test_clearing_the_datasource_takes_the_golden_queries_with_it(
    db_session: Session,
):
  """The documented exception. They are kept inside the datasource config."""
  repo, agent = _agent_with_golden_queries(db_session)

  repo.update(
      agent.id,
      config=AgentConfig(project_id="p", agent_resource_id="r"),
  )

  db_session.expire_all()
  assert repo.get_by_id(agent.id).datasource_config is None


def test_renaming_an_agent_alone_keeps_the_golden_queries(
    db_session: Session,
):
  """An update with no config at all must not reach the datasource."""
  repo, agent = _agent_with_golden_queries(db_session)

  repo.update(agent.id, name="Renamed Bot")

  db_session.expire_all()
  stored = repo.get_by_id(agent.id)
  assert stored.name == "Renamed Bot"
  assert len(stored.datasource_config["golden_queries"]) == 2
