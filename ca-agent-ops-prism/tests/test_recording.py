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

"""Tests for the record/replay cassette layer."""

import json
from typing import Any

from prism.server.clients import recording
import pydantic
import pytest


class _Reply(pydantic.BaseModel):
  text: str
  score: int = 0


class _FakeClient:
  """Stands in for a real API client, counting the calls that get through."""

  def __init__(self, project: str = "projects/p/locations/l"):
    self.project = project
    self.calls = 0

  def _cassette_identity(self) -> dict[str, Any]:
    return {"project": self.project}

  @recording.cassette(recording.ModelCodec(_Reply))
  def ask(self, question: str, secret: str | None = None) -> _Reply:
    del secret
    self.calls += 1
    return _Reply(text=f"answer to {question}", score=self.calls)

  @recording.cassette(recording.ModelListCodec(_Reply))
  def listing(self) -> list[_Reply]:
    self.calls += 1
    return [_Reply(text="a"), _Reply(text="b")]

  @recording.cassette()
  def raw(self, name: str) -> dict[str, Any]:
    self.calls += 1
    return {"name": name, "ok": True}

  @recording.cassette(recording.ResponseSchemaCodec())
  def structured(self, prompt: str, response_schema: type[_Reply]) -> _Reply:
    self.calls += 1
    return response_schema(text=prompt)

  @recording.cassette(recording.ModelCodec(_Reply), ignore=("secret",))
  def ask_ignoring_secret(self, question: str, secret: str) -> _Reply:
    del secret
    self.calls += 1
    return _Reply(text=f"answer to {question}")


@pytest.fixture(name="cassettes")
def _cassettes(tmp_path, monkeypatch):
  """Points the cassette layer at a scratch directory."""
  monkeypatch.setenv("PRISM_CASSETTE_DIR", str(tmp_path))
  return tmp_path


@pytest.fixture(name="mode")
def _mode(monkeypatch):
  """Returns a setter for PRISM_AGENT_BACKEND."""
  return lambda value: monkeypatch.setenv("PRISM_AGENT_BACKEND", value)


def test_live_mode_does_not_touch_disk(cassettes, mode):
  mode("live")
  client = _FakeClient()

  assert client.ask("hello").text == "answer to hello"

  assert client.calls == 1
  assert not list(cassettes.rglob("*.json"))


def test_record_then_replay_round_trips_a_model(cassettes, mode):
  mode("record")
  recorder = _FakeClient()
  recorded = recorder.ask("hello")

  mode("replay")
  player = _FakeClient()
  replayed = player.ask("hello")

  assert replayed == recorded
  assert player.calls == 0, "replay must not reach the underlying client"
  assert len(list((cassettes / "ask").glob("*.json"))) == 1


def test_replay_round_trips_a_model_list(cassettes, mode):
  mode("record")
  recorded = _FakeClient().listing()

  mode("replay")
  player = _FakeClient()

  assert player.listing() == recorded
  assert player.calls == 0


def test_replay_round_trips_a_raw_value(cassettes, mode):
  mode("record")
  recorded = _FakeClient().raw("thing")

  mode("replay")
  player = _FakeClient()

  assert player.raw("thing") == recorded
  assert player.calls == 0


def test_replay_uses_the_runtime_response_schema(cassettes, mode):
  mode("record")
  recorded = _FakeClient().structured("prompt", _Reply)

  mode("replay")
  replayed = _FakeClient().structured("prompt", _Reply)

  assert isinstance(replayed, _Reply)
  assert replayed == recorded


def test_arguments_select_different_cassettes(cassettes, mode):
  mode("record")
  recorder = _FakeClient()
  first = recorder.ask("one")
  second = recorder.ask("two")

  assert first != second

  mode("replay")
  player = _FakeClient()

  assert player.ask("one") == first
  assert player.ask("two") == second


def test_identity_is_part_of_the_key(cassettes, mode):
  mode("record")
  _FakeClient(project="projects/a/locations/l").ask("hello")

  mode("replay")

  with pytest.raises(recording.CassetteMissError):
    _FakeClient(project="projects/b/locations/l").ask("hello")


def test_ignored_arguments_do_not_affect_the_key(cassettes, mode):
  mode("record")
  _FakeClient().ask_ignoring_secret("hello", secret="first")

  mode("replay")
  player = _FakeClient()
  replayed = player.ask_ignoring_secret("hello", secret="second")

  assert replayed.text == "answer to hello"
  assert player.calls == 0


def test_cassette_miss_names_the_method_and_path(cassettes, mode):
  mode("replay")

  with pytest.raises(recording.CassetteMissError) as excinfo:
    _FakeClient().ask("never recorded")

  message = str(excinfo.value)
  assert "ask" in message
  assert str(cassettes) in message
  assert "PRISM_AGENT_BACKEND=record" in message


def test_secrets_are_scrubbed_from_the_stored_request(cassettes, mode):
  mode("record")
  _FakeClient().ask("hello", secret="hunter2")

  document = json.loads(next((cassettes / "ask").glob("*.json")).read_text())

  assert document["request"]["arguments"]["secret"] == "<redacted>"
  assert "hunter2" not in json.dumps(document)


def test_cassettes_carry_provenance(cassettes, mode):
  mode("record")
  _FakeClient().ask("hello")

  document = json.loads(next((cassettes / "ask").glob("*.json")).read_text())

  assert document["metadata"]["client"] == "_FakeClient"
  assert document["metadata"]["recorded_on"]
  assert "library_versions" in document["metadata"]


def test_unknown_backend_is_rejected(mode):
  mode("nonsense")

  with pytest.raises(recording.CassetteError):
    recording.current_backend()


def test_offline_is_only_true_in_replay(mode):
  mode("live")
  assert not recording.offline()
  mode("record")
  assert not recording.offline()
  mode("replay")
  assert recording.offline()


def test_an_unstable_argument_type_is_rejected_at_record_time(cassettes, mode):
  """A key that isn't reproducible is a cassette that can never be found.

  ``_jsonable`` used to fall through to ``repr()``, which for an ordinary object
  embeds its memory address. Recording succeeded, replay computed a different
  key, and the miss surfaced far from its cause.
  """

  class _Opaque:
    pass

  class _Client:

    @recording.cassette(recording.ModelCodec(_Reply))
    def ask(self, thing: object) -> _Reply:
      del thing
      return _Reply(text="ok")

  mode("record")

  with pytest.raises(recording.CassetteError, match="_Opaque"):
    _Client().ask(_Opaque())


def test_a_failed_write_leaves_no_partial_cassette(
    cassettes, mode, monkeypatch
):
  """Cassettes are written temp-then-rename, so readers never see a partial.

  In ``record`` mode the writers are concurrent trial subprocesses, and a
  half-written cassette fails to parse on every later replay.
  """
  mode("record")

  def _explode(*args, **kwargs):
    del args, kwargs
    raise OSError("disk full")

  monkeypatch.setattr(recording.json, "dump", _explode)

  with pytest.raises(OSError):
    _FakeClient().ask("hello")

  assert not list(cassettes.rglob("*.json"))
  assert not list(cassettes.rglob("*.tmp"))
