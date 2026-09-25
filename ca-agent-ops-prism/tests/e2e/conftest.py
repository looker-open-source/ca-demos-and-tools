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

"""Fixtures for the browser end-to-end suite.

The suite drives a real browser against a real gunicorn server backed by a real
PostgreSQL database. Only the two external APIs are faked, and even those are
replayed from responses recorded from the live services (see
``prism.server.clients.recording``).

Three things make that safe and repeatable:

* The database name must contain ``e2e``. The unit suite calls ``drop_all()``
  between tests, which would pull the schema out from under a running server,
  so the two suites can't share a database.
* The schema is built by ``alembic upgrade head``, not ``create_all()``. This
  is the only place a test runs the migration chain.
* Every browser test fails if the page logged a console error or threw an
  uncaught exception. Dash renders a page while a callback 500s behind it, so
  "rendered" doesn't mean "worked".
"""

from __future__ import annotations

import contextlib
import datetime
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import time
from typing import Any, Iterator
import urllib.error
import urllib.request

import alembic.command
import alembic.config
from prism.common.schemas.agent import AgentBase
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.execution import RunStatus
from prism.common.schemas.trace import AskQuestionResponse
from prism.common.schemas.trace import DurationMetrics
from prism.server.clients import recording
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
from prism.server.models.agent import Agent
from prism.server.models.assertion import Assertion
from prism.server.models.assertion import AssertionResult
from prism.server.models.assertion import AssertionSnapshot
from prism.server.models.assertion import SuggestedAssertion
from prism.server.models.example import Example
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.models.snapshot import ExampleSnapshot
from prism.server.models.snapshot import TestSuiteSnapshot
from prism.server.models.suite import TestSuite
import pytest
import sqlalchemy
from sqlalchemy import orm
from tests import db_guard
from tests.e2e import traces

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
CASSETTE_DIR = PROJECT_ROOT / "tests" / "e2e" / "cassettes"

# The GCP coordinates every seeded agent uses. They are fixed because they are
# part of the cassette key, and PRISM_GDA_PROJECTS is set to the project so the
# "Add agent" form offers exactly one, predictable option.
E2E_PROJECT = "e2e-project"
E2E_LOCATION = "global"
E2E_TABLE = f"{E2E_PROJECT}.demo.orders"

# How long to wait for gunicorn to import prism.prod (which runs migrations and
# starts the worker pool) and answer its first request.
SERVER_BOOT_TIMEOUT_S = 120

# How long to let the previous test's trials finish before truncating the
# tables out from under them. Generous, because the alternative is a flake.
WORKER_DRAIN_TIMEOUT_S = 60

# Console messages that are noise, not defects.
_IGNORED_CONSOLE_ERRORS = (
    "favicon.ico",
    "Download the React DevTools",
)

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="session")
def e2e_database_url() -> str:
  """The E2E database URL, validated to be distinct from the unit test DB."""
  url = db_guard.resolve_test_database_url()
  name = db_guard.database_name(url)
  if "e2e" not in name.lower():
    pytest.fail(
        f"The E2E suite needs its own database; got {name!r}.\n"
        "The unit suite drops every table between tests, which would break a "
        "running server. Use ./scripts/run_e2e.sh, which points "
        "TEST_DATABASE_URL at the E2E database."
    )
  return url


@pytest.fixture(scope="session")
def e2e_engine(e2e_database_url: str) -> Iterator[sqlalchemy.Engine]:
  """Builds the E2E schema from the migration chain and yields an engine."""
  config = alembic.config.Config(str(PROJECT_ROOT / "alembic.ini"))
  config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
  config.set_main_option("sqlalchemy.url", e2e_database_url)
  alembic.command.upgrade(config, "head")

  engine = sqlalchemy.create_engine(e2e_database_url)
  try:
    yield engine
  finally:
    engine.dispose()


def _table_names(engine: sqlalchemy.Engine) -> list[str]:
  """Every table alembic built, excluding its own bookkeeping table."""
  inspector = sqlalchemy.inspect(engine)
  return [
      name for name in inspector.get_table_names() if name != "alembic_version"
  ]


def _drain_worker_pool(engine: sqlalchemy.Engine, left_by: str | None) -> None:
  """Waits for in-flight trials to settle before the tables go away.

  The worker pool belongs to the session-scoped server, so a run left
  executing by one test is still dispatching when the next one truncates.
  TRUNCATE also does RESTART IDENTITY, so the stale dispatch looks up trial 1
  in an empty database, logs "Trial 1 not found in child process", and its
  in-flight requests show up in the browser as "the server did not respond".
  Draining first keeps the suite from depending on timing.

  Args:
    engine: The E2E engine.
    left_by: The test that ran last, or None on the first drain of the session.
      The trials being waited on are that test's, and a drain that times out
      reports it. The failure lands in whatever test runs next, so without the
      name the warning points at the wrong spec.
  """
  deadline = time.monotonic() + WORKER_DRAIN_TIMEOUT_S
  statement = sqlalchemy.text(
      "SELECT count(*) FROM trials WHERE status IN ('PENDING', 'RUNNING')"
  )
  while time.monotonic() < deadline:
    with engine.begin() as connection:
      if not connection.execute(statement).scalar():
        return
    time.sleep(0.25)
  sys.stderr.write(
      f"\n[e2e] warning: {left_by or 'an earlier test'} left trials pending "
      f"after {WORKER_DRAIN_TIMEOUT_S}s; truncating anyway. Anything that "
      "fails next may be its dispatches hitting an empty database.\n"
  )


# The test the previous drain ran for. Module state because the fixture cannot
# see the node that ran before it.
_previous_test: str | None = None


@pytest.fixture(autouse=True)
def clean_database(request, e2e_engine: sqlalchemy.Engine) -> Iterator[None]:
  """Empties every table before each test, keeping the migrated schema."""
  global _previous_test
  tables = _table_names(e2e_engine)
  if "trials" in tables:
    _drain_worker_pool(e2e_engine, _previous_test)
  _previous_test = request.node.nodeid
  if tables:
    quoted = ", ".join(f'"{name}"' for name in tables)
    with e2e_engine.begin() as connection:
      connection.execute(
          sqlalchemy.text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")
      )
  yield


@pytest.fixture
def db(e2e_engine: sqlalchemy.Engine) -> Iterator[orm.Session]:
  """A session on the E2E database, for seeding and for assertions."""
  session_factory = orm.sessionmaker(bind=e2e_engine, expire_on_commit=False)
  with session_factory() as session:
    yield session


@pytest.fixture(scope="session")
def cassette_dir(tmp_path_factory) -> Iterator[pathlib.Path]:
  """Where the replay backend looks for cassettes this session.

  Recording writes to the checked-in directory, since the point of recording
  is to keep the result. Replaying works in a copy under /tmp so cassettes a
  spec installs for itself never land in the source tree.
  """
  if os.getenv("PRISM_AGENT_BACKEND") == recording.RECORD:
    directory = CASSETTE_DIR
    directory.mkdir(parents=True, exist_ok=True)
  else:
    directory = tmp_path_factory.mktemp("cassettes")
    if CASSETTE_DIR.is_dir():
      shutil.copytree(CASSETTE_DIR, directory, dirs_exist_ok=True)

  previous = os.environ.get("PRISM_CASSETTE_DIR")
  os.environ["PRISM_CASSETTE_DIR"] = str(directory)
  try:
    yield directory
  finally:
    if previous is None:
      del os.environ["PRISM_CASSETTE_DIR"]
    else:
      os.environ["PRISM_CASSETTE_DIR"] = previous


def _agent_name(agent: Agent) -> str:
  """The full GDA resource name the services build for an agent."""
  return (
      f"projects/{agent.project_id}/locations/{agent.location}/"
      f"dataAgents/{agent.agent_resource_id}"
  )


class Cassettes:
  """Installs cassettes so a spec's agent can answer with no network.

  Keys come from ``recording.plan_call``, the same code path the ``@cassette``
  decorator uses at call time, so a cassette installed here is the one the
  running server finds. A mismatch fails the test rather than silently
  diverging.
  """

  _METADATA = {
      "source": "installed by the E2E suite; see tests/e2e/traces.py",
      "recorded_on": (
          "not recorded; re-record with ./scripts/run_e2e.sh --record"
      ),
  }

  def __init__(self, directory: pathlib.Path):
    self.directory = directory
    self.written: list[pathlib.Path] = []

  def ask_question(
      self,
      agent: Agent,
      question: str = traces.QUESTION,
      *,
      response: list[dict[str, Any]] | None = None,
      duration_ms: int = 1234,
      error_message: str | None = None,
  ) -> pathlib.Path:
    """Installs the answer the worker will get for one question."""
    call = recording.plan_call(
        GeminiDataAnalyticsClient.ask_question,
        # The worker builds its client with the agent's parent; see
        # prism.server.services.worker.execute_trial.
        {"project": f"projects/{agent.project_id}/locations/{agent.location}"},
        agent_id=_agent_name(agent),
        question=question,
    )
    payload = AskQuestionResponse(
        response=traces.success() if response is None else response,
        duration=DurationMetrics(
            total_duration=duration_ms,
            time_to_first_response=min(duration_ms, 200),
        ),
        error_message=error_message,
    ).model_dump(mode="json")
    return self._write(call, payload)

  def agent_context(
      self, agent: Agent, context: dict[str, Any] | None = None
  ) -> pathlib.Path:
    """Installs the published context, for both callers that fetch it.

    Two code paths ask for the same thing with differently-built clients, and
    the client's project is part of the cassette key:

      * ``create_run`` snapshots it through the DI provider, which builds the
        client with an empty project (see prism.client.dependencies);
      * ``AgentService.get_published_context``, behind the run-detail page's
        "Compare to Live Context", builds its own with the agent's parent.

    Writing both means a spec can just ask for "this agent's context" without
    knowing which caller it is about to trigger.

    Returns:
      The cassette for the DI-provider form; both are in ``written``.
    """
    payload = (
        context
        if context is not None
        else {"system_instruction": "Answer questions about orders."}
    )
    paths = [
        self._write(
            recording.plan_call(
                GeminiDataAnalyticsClient.get_agent_context,
                {"project": project},
                agent_name=_agent_name(agent),
                context_target="published",
            ),
            payload,
        )
        for project in (
            "",
            f"projects/{agent.project_id}/locations/{agent.location}",
        )
    ]
    return paths[0]

  def datasource_kind(self, agent: Agent, kind: str = "bq") -> pathlib.Path:
    """Installs the answer to the preflight every run start makes.

    ``ExecutionService._validate_agent_can_run`` asks the service what kind of
    datasource the agent really has, and refuses the run if it cannot tell.
    The DI provider builds that client with an empty project.
    """
    call = recording.plan_call(
        GeminiDataAnalyticsClient.get_datasource_kind,
        {"project": ""},
        agent_name=_agent_name(agent),
    )
    return self._write(call, kind)

  def create_agent(
      self,
      display_name: str,
      config: AgentConfig,
      *,
      agent_resource_id: str,
  ) -> pathlib.Path:
    """Installs the agent GDA returns when the Add Agent form is submitted.

    Args:
      display_name: The name typed into the form.
      config: The config the form builds. It is part of the cassette key, so it
        has to match field for field.
      agent_resource_id: The id GCP assigns. The real service generates it and
        the local row is built from the config that comes back, so replay has to
        supply it.

    Returns:
      The path written.
    """
    call = recording.plan_call(
        GeminiDataAnalyticsClient.create_agent,
        {
            "project": (
                f"projects/{config.project_id}/locations/{config.location}"
            )
        },
        display_name=display_name,
        config=config,
    )
    returned = config.model_copy(
        update={
            "agent_resource_id": agent_resource_id,
            # GCP never echoes secrets back.
            "looker_client_id": None,
            "looker_client_secret": None,
        }
    )
    payload = AgentBase(name=display_name, config=returned).model_dump(
        mode="json"
    )
    return self._write(call, payload)

  def list_agents(self, agents: list[AgentBase]) -> pathlib.Path:
    """Installs what the Monitor page finds when it discovers a project.

    ``discover_gcp_agents`` builds one client per configured location, and the
    server environment pins that to ``E2E_LOCATION``, so this is the whole
    answer.

    Args:
      agents: The agents GDA should report as living in the project.

    Returns:
      The path written.
    """
    call = recording.plan_call(
        GeminiDataAnalyticsClient.list_agents,
        {"project": f"projects/{E2E_PROJECT}/locations/{E2E_LOCATION}"},
    )
    return self._write(
        call, [agent.model_dump(mode="json") for agent in agents]
    )

  def get_agent(
      self, agent: Agent, config: AgentConfig | None = None
  ) -> pathlib.Path:
    """Installs the remote config the agent detail page fetches.

    ``fetch_remote_config`` renders the system instruction and datasource from
    GCP, not from the local row, so the detail page cannot load at all without
    this.

    Args:
      agent: The local row. Its project, location and resource id give both the
        cassette identity and the resource name looked up.
      config: What GCP should report. Defaults to a config echoing the local
        datasource, which is what a freshly created agent looks like.

    Returns:
      The path written.
    """
    call = recording.plan_call(
        GeminiDataAnalyticsClient.get_agent,
        {"project": f"projects/{agent.project_id}/locations/{agent.location}"},
        agent_name=_agent_name(agent),
    )
    if config is None:
      config = AgentConfig(
          project_id=agent.project_id,
          location=agent.location,
          agent_resource_id=agent.agent_resource_id,
          datasource=BigQueryConfig(
              tables=(agent.datasource_config or {}).get("tables", [])
          ),
          system_instruction=traces.SYSTEM_INSTRUCTION,
      )
    payload = AgentBase(name=agent.name, config=config).model_dump(mode="json")
    return self._write(call, payload)

  def update_agent(
      self,
      agent: Agent,
      *,
      system_instruction: str,
      config: AgentConfig,
  ) -> pathlib.Path:
    """Installs the response to the write the Edit Agent modal performs.

    The whole ``config`` is part of the cassette key, so a spec has to hand
    over exactly what the modal will send. That makes this a contract check as
    much as a fixture: change what ``submit_edit`` sends and this cassette
    stops matching.

    Args:
      agent: The local row being edited.
      system_instruction: The new instruction typed into the modal.
      config: The config ``submit_edit`` builds and passes down.

    Returns:
      The path written.
    """
    call = recording.plan_call(
        GeminiDataAnalyticsClient.update_agent,
        {"project": f"projects/{agent.project_id}/locations/{agent.location}"},
        agent_name=_agent_name(agent),
        system_instruction=system_instruction,
        config=config,
    )
    payload = AgentBase(name=agent.name, config=config).model_dump(mode="json")
    return self._write(call, payload)

  def _write(self, call: recording.Call, payload: Any) -> pathlib.Path:
    path = recording.write_cassette(call, payload, metadata=self._METADATA)
    self.written.append(path)
    return path


@pytest.fixture(autouse=True)
def _isolate_cassettes(cassette_dir: pathlib.Path) -> Iterator[None]:
  """Empties the cassette directory before each test.

  The key ``recording.plan_call`` builds is the method, the client's project
  and the arguments. Nothing in it is per-test, and the seeder gives every
  agent the same project, location and resource id, so two specs asking the
  same agent the same question want the same file. Whichever ran first
  answered for both. A spec could then drop its own install, or install the
  wrong payload, and still pass on its neighbour's cassette.

  Clearing between tests means a spec replays only what it installed itself.
  Recording is left alone: it writes to the checked-in directory on purpose.
  """
  if os.getenv("PRISM_AGENT_BACKEND") != recording.RECORD:
    for path in cassette_dir.iterdir():
      if path.is_dir():
        shutil.rmtree(path)
      else:
        path.unlink()
  yield


@pytest.fixture
def cassettes(cassette_dir: pathlib.Path, _isolate_cassettes) -> Cassettes:
  """Installs cassettes for the current spec."""
  del _isolate_cassettes  # Ordering only: the clear happens before the install.
  return Cassettes(cassette_dir)


def _free_port() -> int:
  """Returns a port that is free right now."""
  with contextlib.closing(socket.socket()) as sock:
    sock.bind(("127.0.0.1", 0))
    return sock.getsockname()[1]


def _server_environment(
    database_url: str, cassettes_at: pathlib.Path
) -> dict[str, str]:
  """The environment gunicorn (and its spawned trial workers) will see."""
  environment = dict(os.environ)
  environment["DATABASE_URL"] = database_url
  environment["TEST_DATABASE_URL"] = database_url
  # Replay unless the environment names something else. run_e2e.sh resolves
  # --record and --live into this variable and warns, but it also sources .env
  # with allexport, and a bare pytest run skips the script altogether. Either
  # way the value can arrive without anyone having asked for it on this run, so
  # say so rather than quietly calling the real APIs.
  backend = os.environ.get("PRISM_AGENT_BACKEND") or recording.REPLAY
  if backend != recording.REPLAY:
    print(
        f"WARNING: PRISM_AGENT_BACKEND={backend}. This run will call the real"
        " Gemini Data Analytics and Gen AI APIs and cost money.",
        file=sys.stderr,
    )
  environment["PRISM_AGENT_BACKEND"] = backend
  environment["PRISM_CASSETTE_DIR"] = str(cassettes_at)
  # The Add Agent form offers whatever is configured here, so pinning it keeps
  # the project id in a cassette key predictable.
  environment["PRISM_GDA_PROJECTS"] = E2E_PROJECT
  # Discovery builds one client per configured location and the project is part
  # of the cassette key, so the default "global,us,eu" would make a spec install
  # three cassettes to answer one question.
  environment["PRISM_GDA_LOCATIONS"] = E2E_LOCATION
  environment["PYTHONPATH"] = os.pathsep.join(
      filter(None, [str(PROJECT_ROOT / "src"), environment.get("PYTHONPATH")])
  )
  return environment


@pytest.fixture(scope="session")
def server_log(tmp_path_factory) -> pathlib.Path:
  """Where the server's stdout and stderr are captured."""
  return tmp_path_factory.mktemp("e2e") / "server.log"


@pytest.fixture(scope="session")
def live_server(
    e2e_database_url: str,
    e2e_engine: sqlalchemy.Engine,
    server_log: pathlib.Path,
    cassette_dir: pathlib.Path,
) -> Iterator[str]:
  """Boots the production entry point and yields its base URL.

  Uses ``prism.prod:app`` rather than the development server so the migration
  flow and the worker pool start the way they do in production. The run
  execution specs need a real worker pool.
  """
  del e2e_engine  # Ordering only: the schema must exist before boot.

  port = _free_port()
  base_url = f"http://127.0.0.1:{port}"
  command = [
      "uv",
      "run",
      "gunicorn",
      "--bind",
      f"127.0.0.1:{port}",
      "--workers",
      "1",
      "--threads",
      "8",
      "--timeout",
      "300",
      "prism.prod:app",
  ]

  with server_log.open("wb") as log:
    process = subprocess.Popen(
        command,
        cwd=str(PROJECT_ROOT),
        env=_server_environment(e2e_database_url, cassette_dir),
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    try:
      _wait_for_server(process, base_url, server_log)
      yield base_url
    finally:
      _terminate(process)
      sys.stderr.write(f"\n[e2e] server log: {server_log}\n")


def _wait_for_server(
    process: subprocess.Popen[bytes],
    base_url: str,
    server_log: pathlib.Path,
) -> None:
  """Polls until the server answers, or fails with the server's own log."""
  deadline = time.monotonic() + SERVER_BOOT_TIMEOUT_S
  last_error: Exception | None = None

  while time.monotonic() < deadline:
    if process.poll() is not None:
      pytest.fail(
          f"Server exited with code {process.returncode} during boot.\n"
          f"{_tail(server_log)}"
      )
    try:
      with urllib.request.urlopen(base_url, timeout=5) as response:
        if response.status < 500:
          return
    except urllib.error.HTTPError as error:
      # urlopen raises on any 4xx, and a 404 off a running server still means
      # the server is up, which is all this is waiting for.
      if error.code < 500:
        return
      last_error = error
    except OSError as error:
      # URLError when the connection is refused, bare TimeoutError when the
      # read stalls. urlopen only wraps the errors it sees on the way out, so
      # catching URLError alone lets a half-booted server abort the poll.
      last_error = error
    time.sleep(0.25)

  pytest.fail(
      f"Server did not answer {base_url} within {SERVER_BOOT_TIMEOUT_S}s "
      f"(last error: {last_error}).\n{_tail(server_log)}"
  )


def _tail(path: pathlib.Path, lines: int = 60) -> str:
  """The end of the server log, for failure messages."""
  if not path.is_file():
    return "(no server log)"
  content = path.read_text(encoding="utf-8", errors="replace").splitlines()
  return "--- server log (tail) ---\n" + "\n".join(content[-lines:])


def _terminate(process: subprocess.Popen[bytes]) -> None:
  """Stops gunicorn and its worker children."""
  if process.poll() is not None:
    return
  with contextlib.suppress(ProcessLookupError):
    os.killpg(os.getpgid(process.pid), 15)
  try:
    process.wait(timeout=20)
  except subprocess.TimeoutExpired:
    with contextlib.suppress(ProcessLookupError):
      os.killpg(os.getpgid(process.pid), 9)
    process.wait(timeout=10)


@pytest.fixture(scope="session")
def base_url(live_server: str) -> str:
  """Overrides pytest-base-url so specs can call ``page.goto("/agents")``.

  Session-scoped because pytest-base-url's own autouse ``_verify_url`` fixture
  is session-scoped and would otherwise raise ScopeMismatch.
  """
  return live_server


@pytest.fixture(scope="session")
def browser_context_args(
    browser_context_args: dict[str, Any],
) -> dict[str, Any]:
  """Gives the browser a viewport tall enough for Prism's tables.

  ``accept_downloads`` because the context-diff spec asserts on the file the
  Download diff button produces; without it Playwright cancels the transfer.
  """
  return {
      **browser_context_args,
      "viewport": {"width": 1440, "height": 1000},
      "accept_downloads": True,
  }


def _is_noise(text: str) -> bool:
  return any(marker in text for marker in _IGNORED_CONSOLE_ERRORS)


# Server-side lines that mean a callback blew up. The browser sees none of
# them: handle_errors turns the exception into a logged line and a no_update,
# so the XHR returns a clean 200 and the page just doesn't change. The log is
# the only way to tell "nothing needed updating" from "the update raised".
#
# The prefix marker is the general case. About twenty-five callbacks catch
# Exception themselves, log at ERROR, and return a toast, so they never reach
# handle_errors and never produce either of the other two lines. A spec that
# expects one of those, like test_regression_error_toast, carries the
# allow_errors marker. prism.prod's format puts the level and the logger name
# in every line, which is what makes the prefix match work.
_SERVER_ERROR_MARKERS = (
    # Any UI-side logger at ERROR, including the handlers that swallow.
    "[ERROR] prism.ui.",
    # ui.utils.handle_errors
    "Error in callback ",
    # Flask, when a callback raises outside handle_errors
    "Exception on /_dash-update-component",
)


def _server_errors(log: pathlib.Path, offset: int) -> tuple[list[str], int]:
  """Returns error lines written to the log since ``offset``, and the new end.

  Reading by offset rather than re-scanning keeps one test's failure from
  being reported against every test that follows it.
  """
  if not log.exists():
    return [], offset
  with log.open("r", encoding="utf-8", errors="replace") as handle:
    handle.seek(offset)
    fresh = handle.read()
    end = handle.tell()
  found = [
      line
      for line in fresh.splitlines()
      if any(marker in line for marker in _SERVER_ERROR_MARKERS)
  ]
  return found, end


@pytest.fixture(autouse=True)
def browser_error_gate(request) -> Iterator[None]:
  """Fails any test that produced a browser error or a server callback error.

  Dash runs with ``suppress_callback_exceptions=True``, so a callback that
  raises gives you a 500 on the ``_dash-update-component`` XHR, a console
  error, and an otherwise normal-looking page.

  Both sides are watched. ``handle_errors`` used to sit above the registration
  decorator and catch nothing. Fixing it turned those 500s into logged lines
  and clean 200s, so the console alone no longer sees every failure.
  """
  page = (
      request.getfixturevalue("page")
      if "page" in request.fixturenames
      else None
  )
  log = (
      request.getfixturevalue("server_log")
      if "live_server" in request.fixturenames
      else None
  )
  if page is None and log is None:
    yield
    return

  errors: list[str] = []
  # Established before the test body runs, so boot-time noise and any earlier
  # test's output are already behind us.
  _, offset = _server_errors(log, 0) if log else ([], 0)

  if page is not None:

    def on_console(message) -> None:
      if message.type == "error" and not _is_noise(message.text):
        location = message.location or {}
        where = location.get("url") or "unknown"
        line = location.get("lineNumber")
        errors.append(f"console.error at {where}:{line}: {message.text}")

    def on_page_error(error) -> None:
      stack = getattr(error, "stack", None)
      errors.append(f"uncaught: {error}" + (f"\n    {stack}" if stack else ""))

    page.on("console", on_console)
    page.on("pageerror", on_page_error)

  yield

  if log is not None:
    server, _ = _server_errors(log, offset)
    errors.extend(f"server: {line.strip()}" for line in server)

  if errors and request.node.get_closest_marker("allow_errors") is None:
    joined = "\n  ".join(errors)
    pytest.fail(
        f"{len(errors)} error(s) during this test:\n  {joined}\n"
        f"Full server log: {log}"
    )


class added_latency:  # pylint: disable=invalid-name
  """Adds a fixed round-trip latency to the page, via CDP.

  Specs about what the page does while a request is in flight need that flight
  to last long enough to look at. Against a local server the round trip is
  under 60ms.

  Playwright has no latency knob, and delaying inside a ``page.route`` handler
  would block the sync driver thread the test itself runs on. Chromium's
  ``Network.emulateNetworkConditions`` does it in the browser instead, so the
  test stays responsive while the request is slow.
  """

  def __init__(self, page, latency_ms: int):
    self._page = page
    self._latency_ms = latency_ms
    self._session = None

  def __enter__(self):
    self._session = self._page.context.new_cdp_session(self._page)
    self._session.send("Network.enable")
    self._emulate(self._latency_ms)
    return self

  def __exit__(self, *unused_exc):
    self._emulate(0)
    self._session.detach()
    return False

  def _emulate(self, latency_ms: int) -> None:
    self._session.send(
        "Network.emulateNetworkConditions",
        {
            "offline": False,
            "latency": latency_ms,
            "downloadThroughput": -1,
            "uploadThroughput": -1,
        },
    )


def select_option(page, select_id: str, option_label: str) -> None:
  """Picks an option from a ``dmc.Select``, which is not a native <select>.

  Playwright's ``select_option`` only drives a real ``<select>``. dmc renders
  an input plus a portalled listbox, so choosing a value is two clicks.
  """
  page.locator(f"#{select_id}").click()
  page.get_by_role("option", name=option_label, exact=True).click()


class Seeder:
  """Creates database rows directly, so specs test one thing at a time.

  A spec about the run-detail page shouldn't spend thirty seconds clicking
  through agent and suite creation to get there.
  """

  def __init__(self, session: orm.Session):
    self.session = session

  def agent(
      self,
      name: str = "E2E Agent",
      project_id: str = E2E_PROJECT,
      location: str = E2E_LOCATION,
      agent_resource_id: str = "e2e-agent",
      datasource_config: dict[str, Any] | None = None,
  ) -> Agent:
    """Creates an agent."""
    agent = Agent(
        name=name,
        project_id=project_id,
        location=location,
        agent_resource_id=agent_resource_id,
        datasource_config=datasource_config
        or {"type": "bigquery", "tables": [E2E_TABLE]},
    )
    self.session.add(agent)
    self.session.commit()
    return agent

  def suite(
      self,
      name: str = "E2E Suite",
      description: str = "Seeded by the E2E suite.",
  ) -> TestSuite:
    """Creates a test suite."""
    suite = TestSuite(name=name, description=description, tags={})
    self.session.add(suite)
    self.session.commit()
    return suite

  def example(
      self,
      suite: TestSuite,
      question: str = traces.QUESTION,
      logical_id: str | None = None,
      assertions: list[tuple[AssertionType, dict[str, Any]]] | None = None,
  ) -> Example:
    """Creates an example, optionally with assertions."""
    example = Example(
        test_suite_id=suite.id,
        question=question,
        logical_id=logical_id or f"e2e-{question[:24]}",
    )
    self.session.add(example)
    self.session.flush()

    for assertion_type, params in assertions or []:
      self.session.add(
          Assertion(
              example_id=example.id,
              type=assertion_type,
              weight=1.0,
              params=params,
          )
      )
    self.session.commit()
    return example

  def snapshot(self, suite: TestSuite) -> TestSuiteSnapshot:
    """Freezes a suite and its examples, the way starting a run does."""
    snapshot = TestSuiteSnapshot(
        name=suite.name,
        description=suite.description,
        tags=dict(suite.tags or {}),
        original_suite_id=suite.id,
    )
    self.session.add(snapshot)
    self.session.flush()

    for example in suite.examples:
      example_snapshot = ExampleSnapshot(
          snapshot_suite_id=snapshot.id,
          original_example_id=example.id,
          question=example.question,
          logical_id=example.logical_id,
      )
      self.session.add(example_snapshot)
      self.session.flush()
      for assertion in example.asserts:
        self.session.add(
            AssertionSnapshot(
                example_snapshot_id=example_snapshot.id,
                original_assertion_id=assertion.id,
                type=assertion.type,
                weight=assertion.weight,
                params=dict(assertion.params or {}),
            )
        )
    self.session.commit()
    return snapshot

  def run(
      self,
      agent: Agent,
      snapshot: TestSuiteSnapshot,
      status: RunStatus = RunStatus.PENDING,
      concurrency: int = 2,
      trial_status: RunStatus | None = None,
      agent_context_snapshot: dict[str, Any] | None = None,
  ) -> Run:
    """Creates a run with one trial per example snapshot.

    Args:
      agent: The agent the run is against.
      snapshot: The frozen suite the run executes.
      status: The run's status.
      concurrency: How many trials the worker may run at once.
      trial_status: The status to give each trial; defaults to the run's.
      agent_context_snapshot: The context captured when the run started. The
        run-detail page renders "Compare to Live Context" only when this is set,
        so a spec about the context diff has to supply one.
    """
    run = Run(
        agent_id=agent.id,
        test_suite_snapshot_id=snapshot.id,
        status=status,
        concurrency=concurrency,
        agent_context_snapshot=agent_context_snapshot,
    )
    self.session.add(run)
    self.session.flush()

    for example_snapshot in snapshot.examples:
      self.session.add(
          Trial(
              run_id=run.id,
              example_snapshot_id=example_snapshot.id,
              status=trial_status or RunStatus.PENDING,
          )
      )
    self.session.commit()
    return run

  def finish_trial(
      self,
      trial: Trial,
      *,
      status: RunStatus = RunStatus.COMPLETED,
      output_text: str = traces.ANSWER,
      trace: list[dict[str, Any]] | None = None,
      passed: bool = True,
      error_message: str | None = None,
      duration_ms: int = 1500,
  ) -> Trial:
    """Fills in a trial as though the worker had run it.

    Lets a spec about the trial-detail page start from a finished trial
    without executing a run first. ``test_run_execution`` covers the real
    path.

    Args:
      trial: The trial to complete.
      status: COMPLETED or FAILED.
      output_text: The final answer text the detail page renders.
      trace: The raw trace, in ``trial.trace_results`` shape. Defaults to a
        successful trace.
      passed: Whether the assertion results say the trial passed.
      error_message: Set on a FAILED trial.
      duration_ms: How long the trial claims to have taken.

    Returns:
      The same trial, refreshed.
    """
    started = datetime.datetime.now(datetime.timezone.utc)
    trial.status = status
    trial.started_at = started
    trial.completed_at = started + datetime.timedelta(milliseconds=duration_ms)
    trial.error_message = error_message

    if status == RunStatus.FAILED:
      # A failed trial has neither output nor assertion results. That
      # asymmetry is what the accuracy regression spec is about.
      trial.output_text = None
      trial.trace_results = None
      self.session.commit()
      return trial

    trial.output_text = output_text
    trial.trace_results = traces.success() if trace is None else trace
    for assertion_snapshot in trial.example_snapshot.asserts:
      self.session.add(
          AssertionResult(
              trial_id=trial.id,
              assertion_snapshot_id=assertion_snapshot.id,
              passed=passed,
              score=1.0 if passed else 0.0,
              reasoning="Seeded by the E2E suite.",
          )
      )
    self.session.commit()
    return trial

  def suggest_assertion(
      self,
      trial: Trial,
      *,
      assertion_type: AssertionType = AssertionType.TEXT_CONTAINS,
      params: dict[str, Any] | None = None,
      weight: float = 1.0,
      reasoning: str = "The answer always states the row count.",
  ) -> SuggestedAssertion:
    """Attaches a suggested assertion to a finished trial.

    These are what the "Suggestions from recent runs" modal on the suite
    editor lists. In production they are written by the suggestion service
    from a real trace; a spec about the modal has no reason to pay for that.
    """
    suggestion = SuggestedAssertion(
        trial_id=trial.id,
        type=assertion_type,
        weight=weight,
        params=params if params is not None else {"value": "128"},
        reasoning=reasoning,
    )
    self.session.add(suggestion)
    self.session.commit()
    return suggestion


@pytest.fixture
def seed(db: orm.Session) -> Seeder:
  """Row-level seeding helpers for the E2E database."""
  return Seeder(db)
