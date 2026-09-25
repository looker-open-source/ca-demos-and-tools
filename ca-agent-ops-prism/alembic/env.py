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

"""Alembic environment configuration."""

import logging.config

from alembic import context
from prism.server.config import settings
from prism.server.db import Base
from prism.server.db import engine

# Imported for the side effect: every model has to be registered on Base before
# target_metadata is read, or autogenerate proposes dropping its table. The
# package __init__ pulls all of them in, including playground, which the
# per-module list this replaced had missed.
from prism.server import models  # noqa: F401  pylint: disable=unused-import

config = context.config

if config.config_file_name is not None:
  # disable_existing_loggers=False, against fileConfig's default. prod.py runs
  # migrations at import time, after importing the app, so every prism.* logger
  # already exists and the default sets .disabled on all of them for the life of
  # the process. That threw away every application log line in production,
  # including handle_errors' "Error in callback".
  logging.config.fileConfig(
      config.config_file_name, disable_existing_loggers=False
  )


# Escaped, because set_main_option runs the value through ConfigParser
# interpolation and a password holding a % raises ValueError there. prod.py
# migrates at import time, so that would take the server down at boot.
config.set_main_option(
    "sqlalchemy.url", settings.final_database_url.replace("%", "%%")
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
  """Run migrations in 'offline' mode."""
  url = config.get_main_option("sqlalchemy.url")
  context.configure(
      url=url,
      target_metadata=target_metadata,
      literal_binds=True,
      dialect_opts={"paramstyle": "named"},
  )

  with context.begin_transaction():
    context.run_migrations()


def run_migrations_online() -> None:
  """Run migrations in 'online' mode."""
  # engine comes from prism.server.db, already wired for the Cloud SQL
  # Connector when settings.instance_connection_name is set.

  with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # One transaction per revision, not one for the whole upgrade. Three
        # of the enum revisions used to issue a bare COMMIT to get out of the
        # surrounding transaction, which ended it for every revision after
        # them too: a failure partway then left half a revision committed with
        # alembic_version still on its parent, and the retry died on the work
        # that had already landed. This gives those revisions the committed
        # boundary they wanted without taking it away from the rest.
        transaction_per_migration=True,
    )

    with context.begin_transaction():
      context.run_migrations()


if context.is_offline_mode():
  run_migrations_offline()
else:
  run_migrations_online()
