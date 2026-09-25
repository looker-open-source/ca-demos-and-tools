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

"""What the suites list costs to build.

get_suites_with_stats was a two-level N+1: one query per suite for its
examples, one per suite for its run count, then one more per example because
``e.asserts`` lazy loaded. A page of 30 suites at 40 questions each ran over
1200 queries.

It is a fixed set now: the suites with their examples and assertions eagerly
loaded, and one grouped count for every suite's runs at once.
"""

import datetime

from prism.common.schemas.assertion import TextContainsSchema
from prism.common.schemas.execution import RunStatus
from prism.server.models.agent import Agent
from prism.server.models.run import Run
from prism.server.models.snapshot import TestSuiteSnapshot
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.suite_service import SuiteService
import pytest
from sqlalchemy import orm

NOW = datetime.datetime.now(datetime.timezone.utc)


@pytest.fixture(name="service")
def _service(db_session: orm.Session) -> SuiteService:
  return SuiteService(
      db_session, SuiteRepository(db_session), ExampleRepository(db_session)
  )


def _agent(session: orm.Session) -> Agent:
  agent = Agent(
      name="Suites Agent", project_id="p", location="l", agent_resource_id="r"
  )
  session.add(agent)
  session.flush()
  return agent


def _seed(
    service: SuiteService,
    session: orm.Session,
    agent: Agent,
    suite_count: int,
    questions: int,
    runs: int,
) -> None:
  """``suite_count`` suites, each with questions, assertions and runs."""
  for suite_index in range(suite_count):
    suite = service.create_suite(name=f"Suite {suite_index}")
    for question_index in range(questions):
      service.add_example(
          suite.id,
          f"Q{question_index}",
          asserts=[TextContainsSchema(value="ok")],
      )
    for _ in range(runs):
      snapshot = TestSuiteSnapshot(name=suite.name, original_suite_id=suite.id)
      session.add(snapshot)
      session.flush()
      session.add(
          Run(
              agent_id=agent.id,
              test_suite_snapshot_id=snapshot.id,
              status=RunStatus.COMPLETED,
              created_at=NOW,
              is_archived=False,
          )
      )
  session.commit()


def test_the_suites_list_costs_the_same_however_many_suites_there_are(
    db_session: orm.Session, service: SuiteService, statement_counter
):
  agent = _agent(db_session)
  _seed(service, db_session, agent, suite_count=1, questions=2, runs=1)

  db_session.expire_all()
  with statement_counter() as one_suite:
    assert len(service.get_suites_with_stats()) == 1

  _seed(service, db_session, agent, suite_count=6, questions=2, runs=1)

  db_session.expire_all()
  with statement_counter() as seven_suites:
    assert len(service.get_suites_with_stats()) == 7

  assert seven_suites.count == one_suite.count


def test_the_suites_list_costs_the_same_however_many_questions_they_have(
    db_session: orm.Session, service: SuiteService, statement_counter
):
  """The second level of the N+1: one lazy load per example for its asserts."""
  agent = _agent(db_session)
  _seed(service, db_session, agent, suite_count=1, questions=1, runs=1)

  db_session.expire_all()
  with statement_counter() as few:
    service.get_suites_with_stats()

  _seed(service, db_session, agent, suite_count=1, questions=12, runs=1)

  db_session.expire_all()
  with statement_counter() as many:
    service.get_suites_with_stats()

  assert many.count == few.count


def test_the_counts_are_what_they_were_before(
    db_session: orm.Session, service: SuiteService
):
  """Loading it differently must not change the numbers on the page.

  A deleted question is archived rather than removed, and the per-suite query
  this replaces filtered those out. The relationship does not, so the count
  has to.
  """
  agent = _agent(db_session)
  _seed(service, db_session, agent, suite_count=1, questions=3, runs=2)
  suite = service.list_suites()[0]
  service.delete_example(service.list_examples(suite.id)[0].id)

  # A suite nothing has ever run, to pin the missing key on the grouped count.
  empty = service.create_suite(name="Never Run")
  db_session.commit()
  db_session.expire_all()

  stats = {s.suite.id: s for s in service.get_suites_with_stats()}

  assert stats[suite.id].question_count == 2
  assert stats[suite.id].run_count == 2
  assert stats[suite.id].assertion_coverage == 1.0
  assert stats[empty.id].question_count == 0
  assert stats[empty.id].run_count == 0
