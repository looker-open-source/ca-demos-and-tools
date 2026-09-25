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

"""Every timestamp column in the schema carries a timezone.

playground_traces.created_at overrode BaseMixin with a plain DateTime and was
the only naive column left. Postgres gives that column back as a naive value,
so a playground trace could not be differenced against anything else in the
schema, modified_at on its own row included: Python raises on subtracting an
aware datetime from a naive one.

The sweep below is the invariant. The round trip is the column that broke it.
"""

import datetime

from prism.server.db import Base
import prism.server.models  # pylint: disable=unused-import
from prism.server.models.agent import Agent
from prism.server.models.playground import PlaygroundTrace
import sqlalchemy
from sqlalchemy import orm


def test_no_timestamp_column_in_the_schema_is_naive():
  naive = [
      f"{table.name}.{column.name}"
      for table in Base.metadata.sorted_tables
      for column in table.columns
      if isinstance(column.type, sqlalchemy.DateTime)
      and not column.type.timezone
  ]

  assert naive == []


def test_a_playground_trace_reads_back_with_a_timezone(db_session: orm.Session):
  agent = Agent(
      name="Playground Agent",
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  db_session.add(agent)
  db_session.flush()

  trace = PlaygroundTrace(
      question="Q", agent_id=agent.id, trace_results=[], passed=True
  )
  db_session.add(trace)
  db_session.commit()
  # Expired, so the value comes back off the column rather than out of the
  # default the insert ran through.
  db_session.expire_all()

  stored = db_session.get(PlaygroundTrace, trace.id)

  assert stored.created_at.tzinfo is not None
  # The comparison is the thing that used to raise TypeError.
  assert stored.modified_at - stored.created_at < datetime.timedelta(minutes=1)
