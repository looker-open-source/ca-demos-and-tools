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

"""What AgentRepository.update does with the Looker client secret.

Blank means unchanged in the edit form, and the form sends None for it. The
repository is where that rule lives: it writes the secret only when it is not
None, so None keeps the stored one. tests/ui/test_agent_edit_secret.py covers
the callback half, but its assertions are against a MagicMock standing in for
the client, so the repository never ran and the rule it names was untested.
"""

from prism.common.schemas.agent import AgentConfig
from prism.server.repositories.agent_repository import AgentRepository
from sqlalchemy.orm import Session

_STORED_SECRET = "a-stored-secret"


def _agent_with_a_secret(repo: AgentRepository):
  return repo.create(
      name="Looker Bot",
      config=AgentConfig(
          project_id="p",
          location="l",
          agent_resource_id="r",
          looker_client_id="a-client-id",
          looker_client_secret=_STORED_SECRET,
      ),
  )


def test_a_none_secret_leaves_the_stored_one_alone(db_session: Session):
  """A blank field in the edit form must not wipe a working credential."""
  repo = AgentRepository(db_session)
  agent = _agent_with_a_secret(repo)

  repo.update(
      agent.id,
      config=AgentConfig(
          project_id="p",
          location="l",
          agent_resource_id="r",
          looker_client_id="a-client-id",
          looker_client_secret=None,
      ),
  )

  db_session.expire_all()
  assert repo.get_by_id(agent.id).looker_client_secret == _STORED_SECRET


def test_a_typed_secret_is_written_over_the_stored_one(db_session: Session):
  """The converse, or "keep on None" could be "never write it at all"."""
  repo = AgentRepository(db_session)
  agent = _agent_with_a_secret(repo)

  repo.update(
      agent.id,
      config=AgentConfig(
          project_id="p",
          location="l",
          agent_resource_id="r",
          looker_client_id="a-client-id",
          looker_client_secret="a-new-secret",
      ),
  )

  db_session.expire_all()
  assert repo.get_by_id(agent.id).looker_client_secret == "a-new-secret"
