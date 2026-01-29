"""Alembic environment configuration."""

import logging.config

from alembic import context
from prism.server.config import settings
from prism.server.db import Base
from prism.server.models import agent  # noqa: F401
from prism.server.models import assertion  # noqa: F401
from prism.server.models import example  # noqa: F401
from prism.server.models import run  # noqa: F401
from prism.server.models import snapshot  # noqa: F401
from prism.server.models import suite  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
  logging.config.fileConfig(config.config_file_name)

# Set the sqlalchemy.url from our settings
config.set_main_option("sqlalchemy.url", settings.final_database_url)

# add your model's MetaData object here
# for 'autogenerate' support
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
  # Import the engine already configured with the Cloud SQL Connector if needed
  from prism.server.db import engine

  with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
      context.run_migrations()


if context.is_offline_mode():
  run_migrations_offline()
else:
  run_migrations_online()
