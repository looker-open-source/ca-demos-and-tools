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

"""The migration chain against the models it is supposed to produce.

Nothing checked the two agreed. The suite builds its tables with create_all and
never runs a migration, so the only thing exercising alembic was a developer
running setup_postgres.sh. That is how the dev database here ended up stamped
at 87d5db0c5bc2 while that revision was still uncommitted: upgrade head failed
against it, and the schema had drifted from head by the server default
87d5db0c5bc2 puts on agents.location.

These run the chain from empty and compare the result to the models, server
defaults included, because a default is what drifted.
"""

import os
import pathlib
import re
import subprocess

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from prism.server.db import Base
import prism.server.models  # pylint: disable=unused-import
import pytest
import sqlalchemy

_ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(name="alembic_config", scope="session")
def _alembic_config() -> Config:
  return Config(str(_ROOT / "alembic.ini"))


@pytest.fixture(name="migrated_url", scope="session")
def _migrated_url(test_database_url: str):
  """A database built only by running the migrations, from empty.

  Separate from the suite's database, which create_all owns and every test
  drops tables in.
  """
  url = sqlalchemy.engine.make_url(test_database_url)
  scratch = url.set(database=f"{url.database}_migrations")

  admin = sqlalchemy.create_engine(
      url.set(database="postgres"), isolation_level="AUTOCOMMIT"
  )
  with admin.connect() as conn:
    conn.execute(
        sqlalchemy.text(f'DROP DATABASE IF EXISTS "{scratch.database}"')
    )
    conn.execute(sqlalchemy.text(f'CREATE DATABASE "{scratch.database}"'))

  # A subprocess, because alembic/env.py migrates the engine prism.server.db
  # built at import, and that engine is already bound to the test database.
  # This is also how setup_postgres.sh runs it.
  result = subprocess.run(
      ["uv", "run", "alembic", "upgrade", "head"],
      cwd=_ROOT,
      env={
          **os.environ,
          "DATABASE_URL": scratch.render_as_string(hide_password=False),
      },
      capture_output=True,
      text=True,
      check=False,
  )
  assert result.returncode == 0, result.stderr

  yield scratch

  with admin.connect() as conn:
    conn.execute(
        sqlalchemy.text(f'DROP DATABASE IF EXISTS "{scratch.database}"')
    )
  admin.dispose()


def test_the_chain_has_one_head(alembic_config):
  """Two heads means whichever branch a developer merged first wins."""
  assert len(ScriptDirectory.from_config(alembic_config).get_heads()) == 1


def test_every_revision_is_on_the_path_to_head(alembic_config):
  """A file in versions/ that nothing points at never runs."""
  script = ScriptDirectory.from_config(alembic_config)
  on_path = {rev.revision for rev in script.walk_revisions()}

  files = {
      p.name.split("_")[0]
      for p in (_ROOT / "alembic" / "versions").glob("*.py")
  }

  assert files - on_path == set()


def test_the_prod_fallback_finds_alembic_ini():
  """prism.prod runs the chain at import, off a path it computes itself.

  Gunicorn starts in the project root, so the relative path wins there and the
  fallback never runs. It had one level too many, which resolved to the parent
  of the checkout, so importing prism.prod from any other cwd raised. Reading
  the literal out of the source because importing the module migrates a
  database.
  """
  source = (_ROOT / "src" / "prism" / "prod.py").read_text()
  relative = re.search(
      r'os\.path\.join\(\s*os\.path\.dirname\(__file__\),\s*"([^"]+)"', source
  )
  assert relative, "prod.py no longer builds the fallback path this way."

  resolved = (_ROOT / "src" / "prism" / relative.group(1)).resolve()
  assert (
      resolved == (_ROOT / "alembic.ini").resolve()
  ), f"The fallback resolves to {resolved}, not the project's alembic.ini."


def test_migrating_from_empty_produces_the_models(migrated_url):
  """Head has to build what the ORM expects, or production runs on a guess."""
  engine = sqlalchemy.create_engine(migrated_url)
  with engine.connect() as conn:
    diff = compare_metadata(
        MigrationContext.configure(conn, opts={"compare_server_default": True}),
        Base.metadata,
    )
  engine.dispose()

  assert diff == []
