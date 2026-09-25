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

"""Session fixtures, and the guards that run before the imports below them.

``db_guard.enforce()`` has to settle the database URL before anything imports
``prism.server.db``, so it sits between two blocks of imports instead of after
all of them. The rest is the session and engine fixtures, and the banner that
fires when the browser tier could not be collected.
"""

import ast
import pathlib
from typing import Generator
from typing import Sequence

import pytest
import sqlalchemy
from sqlalchemy import orm
from tests import db_guard

# Resolve and enforce the test database before anything imports
# prism.server.db and builds an engine from the developer's .env.
_TEST_DATABASE_URL = db_guard.enforce()

from prism.server.db import Base  # pylint: disable=g-import-not-at-top

# Importing models package registers all models with Base.metadata
import prism.server.models  # pylint: disable=unused-import,g-import-not-at-top

_E2E_DIR = pathlib.Path(__file__).parent / "e2e"

# The browser tier imports playwright at module scope, and pytest imports every
# test module before -m deselects anything. playwright is in the e2e dependency
# group rather than dev, so ./scripts/run_tests.sh does not have it and would
# fail collecting a directory it is not going to run. ./scripts/run_e2e.sh
# installs the group, and then this does nothing.
#
# Dropping the directory quietly was the worse failure. The run stayed green
# with the entire browser tier gone and nothing on screen said so. The banner
# below names the import that failed and counts what went with it, in the
# header and again in the summary where the pass count is read.
collect_ignore = []
_browser_tier_error: str | None = None
try:
  import playwright  # pylint: disable=g-import-not-at-top,unused-import
except ImportError as error:
  collect_ignore.append("e2e")
  _browser_tier_error = f"{type(error).__name__}: {error}"


def _count_browser_tests() -> int:
  """Counts test functions under tests/e2e without importing them.

  Importing is the thing that is not available. Parametrized cases count once,
  so this is a floor on what was skipped, not the collected total.
  """
  total = 0
  for path in sorted(_E2E_DIR.glob("test_*.py")):
    for node in ast.walk(ast.parse(path.read_text())):
      if isinstance(
          node, (ast.FunctionDef, ast.AsyncFunctionDef)
      ) and node.name.startswith("test_"):
        total += 1
  return total


def _browser_tier_banner(error: str) -> str:
  """The line that has to be impossible to read as a covered browser tier."""
  return (
      f"BROWSER TIER NOT RUN: at least {_count_browser_tests()} tests under"
      f" tests/e2e were not collected, because {error}. Run"
      " ./scripts/run_e2e.sh, which installs the e2e dependency group."
  )


def pytest_report_header(config) -> list[str]:
  """Shows which database the suite is pointed at, and what it is missing."""
  del config
  lines = [f"prism test database: {_TEST_DATABASE_URL}"]
  if _browser_tier_error:
    lines.append(_browser_tier_banner(_browser_tier_error))
  return lines


def pytest_terminal_summary(terminalreporter) -> None:
  """Repeats the banner next to the pass count, which is what gets read."""
  if _browser_tier_error:
    terminalreporter.write_sep("=", "browser tier skipped", red=True)
    terminalreporter.write_line(
        _browser_tier_banner(_browser_tier_error), red=True, bold=True
    )


@pytest.fixture(scope="session")
def test_database_url() -> str:
  """The validated test database URL."""
  return _TEST_DATABASE_URL


@pytest.fixture(autouse=True)
def _reset_bigquery_export_state():
  """Keeps the exporter's module-level bookkeeping out of other tests.

  The exporter has two module globals, ``_active_exports`` for the exports in
  flight and ``_exported_runs`` for the ones it has confirmed. A failure is not
  among them; that lives on ``run.bigquery_export_error``. Both globals have to
  be module scope: the worker thread and the UI render path are the same
  process and must agree. Nothing else resets them between tests, so a run id
  confirmed as exported in one test is still confirmed in the next and test
  order starts deciding outcomes. Autouse, because the tests that need this are
  the ones not thinking about it.
  """
  # Imported inside the fixture so collecting a suite that never touches
  # BigQuery doesn't pay to import the BigQuery SDK.
  from prism.server.services import bigquery_exporter  # pylint: disable=g-import-not-at-top

  bigquery_exporter.reset_export_state()
  yield
  bigquery_exporter.reset_export_state()


@pytest.fixture(scope="session")
def engine(test_database_url: str) -> Generator[sqlalchemy.Engine, None, None]:
  """Creates a database engine for the test session."""
  test_engine = sqlalchemy.create_engine(test_database_url)
  yield test_engine
  test_engine.dispose()


@pytest.fixture
def session_factory(
    engine: sqlalchemy.Engine,
) -> Generator[orm.sessionmaker, None, None]:
  """Creates a session factory connected to the test database."""
  Base.metadata.create_all(bind=engine)

  yield orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)

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


class _StatementCounter:
  """Counts the statements a block of work sends to the database."""

  def __init__(self, session: orm.Session):
    self.connection = session.connection()
    self.count = 0

  def __enter__(self):
    sqlalchemy.event.listen(
        self.connection, "after_cursor_execute", self._record
    )
    return self

  def __exit__(self, *exc_info):
    sqlalchemy.event.remove(
        self.connection, "after_cursor_execute", self._record
    )

  def _record(self, *args, **kwargs):
    del args, kwargs
    self.count += 1


@pytest.fixture
def statement_counter(db_session: orm.Session):
  """A context manager counting the queries the block inside it runs.

  ``with statement_counter() as counted:`` and then ``counted.count``. An N+1
  is a count that grows with the rows, so the callers seed twice at different
  sizes and compare, rather than pinning a number that any added join breaks.
  """
  return lambda: _StatementCounter(db_session)


_SRC_ROOT = pathlib.Path(__file__).parent.parent / "src"


def _resolve_relative(module: str | None, level: int, package: str) -> str:
  """Turns ``from ..server import x`` into the module it actually names.

  Args:
    module: The dotted name after the leading dots, if there is one.
    level: How many leading dots the statement carries. Zero is absolute.
    package: The package holding the file, e.g. "prism.ui.pages".
  """
  if not level:
    return module or ""
  parts = package.split(".")
  if level > len(parts):
    return ""
  parts = parts[: len(parts) - level + 1]
  return ".".join(parts + ([module] if module else []))


def _import_module_target(call: ast.Call) -> str:
  """Returns the literal name an ``import_module`` call asks for."""
  func = call.func
  called = (
      func.attr
      if isinstance(func, ast.Attribute)
      else getattr(func, "id", None)
  )
  if called != "import_module" or not call.args:
    return ""
  first = call.args[0]
  if isinstance(first, ast.Constant) and isinstance(first.value, str):
    return first.value
  return ""


def _imported_modules(path: pathlib.Path, package: str) -> set[str]:
  """Returns the absolute module names one file imports."""
  try:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
  except SyntaxError:
    return set()

  modules = set()
  for node in ast.walk(tree):
    if isinstance(node, ast.Import):
      modules.update(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom):
      base = _resolve_relative(node.module, node.level, package)
      if base:
        modules.add(base)
        # "from prism.client import dependencies" names prism.client in the
        # statement and pulls in prism.client.dependencies.
        modules.update(f"{base}.{alias.name}" for alias in node.names)
    elif isinstance(node, ast.Call):
      target = _import_module_target(node)
      if target:
        modules.add(target)
  return modules


def layering_violations(package: str, forbidden: Sequence[str]) -> list[str]:
  """Returns every import in ``package`` that names a forbidden module.

  Shared by the three isolation tests, which differ only in who may not import
  whom. Relative imports are resolved against the package holding the file,
  and a literal ``importlib.import_module("prism.server.x")`` is read out of
  the call. Both used to pass unseen.

  What this cannot see is a module reached through another module. The rule is
  checked one import statement at a time, so any package that re-exports a
  forbidden symbol hands it to everyone allowed to import that package.

  Args:
    package: The dotted package to walk, e.g. "prism.ui".
    forbidden: Dotted prefixes that package may not import.

  Returns:
    One line per offending import, naming the file and the module.
  """
  root = _SRC_ROOT.joinpath(*package.split("."))
  if not root.is_dir():
    pytest.fail(f"Could not find {package} at {root}")

  violations = []
  for path in sorted(root.rglob("*.py")):
    owner = ".".join(path.relative_to(_SRC_ROOT).parent.parts)
    for imported in sorted(_imported_modules(path, owner)):
      for prefix in forbidden:
        if imported == prefix or imported.startswith(prefix + "."):
          where = path.relative_to(_SRC_ROOT.parent)
          violations.append(f"{where}: imports '{imported}'")
  return violations
