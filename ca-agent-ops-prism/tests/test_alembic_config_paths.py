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

"""alembic.ini has to resolve its own paths, whatever the working directory.

script_location and prepend_sys_path were plain relative strings.
ScriptDirectory.from_config hands script_location through untouched and checks
it against the process cwd, so prism.prod passed its database canary, logged
the absolute path of the config it had found, then raised
CommandError: Path doesn't exist: alembic at import time. Production never saw
it because the Dockerfile sets WORKDIR to the project root.

test_migrations.py::test_the_prod_fallback_finds_alembic_ini cannot catch this.
It regex-extracts the path literal out of prod.py's source and never leaves the
root. These chdir somewhere else and run the real alembic code.
"""

import pathlib

from alembic.config import Config
from alembic.script import ScriptDirectory

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_the_script_directory_loads_from_a_cwd_that_is_not_the_project_root(
    tmp_path, monkeypatch
):
  """This is the call that raised, and the cwd is the whole of the input."""
  monkeypatch.chdir(tmp_path)

  script = ScriptDirectory.from_config(Config(str(_ROOT / "alembic.ini")))

  assert pathlib.Path(script.dir).resolve() == (_ROOT / "alembic").resolve()


def test_the_configured_paths_are_absolute_from_a_cwd_that_is_not_the_root(
    tmp_path, monkeypatch
):
  """Both paths are read against the cwd, so both have to be anchored.

  prepend_sys_path is the quieter one. A relative "src" that resolves to
  nothing puts no directory on sys.path and env.py then fails importing
  prism.server.config, several frames from the cause.
  """
  monkeypatch.chdir(tmp_path)
  config = Config(str(_ROOT / "alembic.ini"))

  script_location = pathlib.Path(config.get_main_option("script_location"))
  prepend_sys_path = pathlib.Path(config.get_main_option("prepend_sys_path"))

  assert script_location.is_absolute()
  assert prepend_sys_path.is_absolute()
  assert script_location.resolve() == (_ROOT / "alembic").resolve()
  assert prepend_sys_path.resolve() == (_ROOT / "src").resolve()
