"""Pytest configuration."""

import os
from typing import Generator

# Import Base and models to ensure metadata is populated
from prism.server.db import Base
# Importing models package registers all models with Base.metadata
import prism.server.models  # pylint: disable=unused-import
import pytest
import sqlalchemy
from sqlalchemy import orm


@pytest.fixture(scope="session")
def engine() -> Generator[sqlalchemy.Engine, None, None]:
  """Creates a database engine for the test session."""
  test_db_url = os.getenv(
      "TEST_DATABASE_URL",
      "postgresql:///prism_test?host=/var/run/postgresql",
  )
  test_engine = sqlalchemy.create_engine(test_db_url)
  yield test_engine
  test_engine.dispose()


@pytest.fixture
def session_factory(
    engine: sqlalchemy.Engine,
) -> Generator[orm.sessionmaker, None, None]:
  """Creates a session factory connected to the test database."""
  # Create all tables
  Base.metadata.create_all(bind=engine)

  yield orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)

  # Clean up
  Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(
    session_factory: orm.sessionmaker,
) -> Generator[orm.Session, None, None]:
  """Creates a fresh database session for each test."""
  session = session_factory()
  try:
    yield session
  finally:
    session.close()
