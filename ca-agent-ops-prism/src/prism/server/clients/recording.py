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

"""Record / replay support for the external agent clients.

Prism talks to two external services: the Gemini Data Analytics API and the
Gen AI (Vertex) API. Tests need those calls to be deterministic, offline and
free, while still exercising real response shapes instead of hand-written
stubs.

This module is the cassette layer for that. ``PRISM_AGENT_BACKEND`` picks the
mode, read by ``current_backend()`` on each call rather than mirrored into
``config.Settings``, which is evaluated once at import:

- ``live``: the default. Calls go straight to the real API; this module does
  nothing.
- ``record``: calls go to the real API and the response is written to a
  cassette file.
- ``replay``: calls never leave the process. The cassette recorded earlier is
  loaded and deserialized back into the type the real call would have
  returned. A miss raises ``CassetteMissError`` instead of falling back to the
  network, so a new code path can't silently pass.

An environment variable rather than monkeypatching, because trial execution
happens in a ``spawn``ed subprocess (``prism.server.services.worker``) that
re-imports everything and so doesn't inherit patched module state.

The client methods are decorated individually (``@cassette``) rather than
the client objects wrapped, because the clients are constructed directly at
eleven call sites across the services layer, and only two of the fourteen
call sites in the tree go through dependency injection.
"""

from __future__ import annotations

import collections.abc
import dataclasses
import datetime
import enum
import functools
import hashlib
import importlib.metadata
import inspect
import json
import logging
import os
import pathlib
import tempfile
from typing import Any, Callable, Type

import pydantic

LIVE = "live"
RECORD = "record"
REPLAY = "replay"
_MODES = (LIVE, RECORD, REPLAY)

_DEFAULT_CASSETTE_DIR = (
    pathlib.Path(__file__).resolve().parents[4] / "tests" / "cassettes"
)

# Request fields scrubbed before a cassette is written. The real values still
# feed the key, which is a one-way hash, so this doesn't weaken matching.
_SECRET_MARKERS = ("secret", "password", "token", "credential", "api_key")

logger = logging.getLogger(__name__)


class CassetteError(RuntimeError):
  """Base class for cassette problems."""


class CassetteMissError(CassetteError):
  """Raised in replay mode when no cassette exists for a call."""


def current_backend() -> str:
  """Returns the active backend, validating it."""
  # Read the environment directly, not through ``settings``, so a test can
  # flip the mode after import.
  backend = os.getenv("PRISM_AGENT_BACKEND", LIVE).strip().lower() or LIVE
  if backend not in _MODES:
    raise CassetteError(
        f"PRISM_AGENT_BACKEND={backend!r} is not one of {_MODES}."
    )
  return backend


def cassette_dir() -> pathlib.Path:
  """Returns the directory cassettes are read from and written to."""
  override = os.getenv("PRISM_CASSETTE_DIR")
  return pathlib.Path(override) if override else _DEFAULT_CASSETTE_DIR


class Codec:
  """Turns a method's return value into JSON and back."""

  def encode(self, value: Any) -> Any:
    raise NotImplementedError

  def decode(self, payload: Any, call: "Call") -> Any:
    raise NotImplementedError


class RawCodec(Codec):
  """For methods that already return JSON-native values (str, dict, None)."""

  def encode(self, value: Any) -> Any:
    return value

  def decode(self, payload: Any, call: "Call") -> Any:
    del call
    return payload


@dataclasses.dataclass(frozen=True)
class ModelCodec(Codec):
  """For methods returning an optional pydantic model."""

  model: Type[pydantic.BaseModel]

  def encode(self, value: Any) -> Any:
    return None if value is None else value.model_dump(mode="json")

  def decode(self, payload: Any, call: "Call") -> Any:
    del call
    return None if payload is None else self.model.model_validate(payload)


@dataclasses.dataclass(frozen=True)
class ModelListCodec(Codec):
  """For methods returning a list of pydantic models."""

  model: Type[pydantic.BaseModel]

  def encode(self, value: Any) -> Any:
    return [item.model_dump(mode="json") for item in value]

  def decode(self, payload: Any, call: "Call") -> Any:
    del call
    return [self.model.model_validate(item) for item in payload]


class ResponseSchemaCodec(Codec):
  """For ``generate_structured``, whose type comes from a call argument."""

  def __init__(self, argument: str = "response_schema"):
    self.argument = argument

  def encode(self, value: Any) -> Any:
    return None if value is None else value.model_dump(mode="json")

  def decode(self, payload: Any, call: "Call") -> Any:
    if payload is None:
      return None
    schema = call.arguments[self.argument]
    return schema.model_validate(payload)


@dataclasses.dataclass(frozen=True)
class Call:
  """A normalized description of one outbound call."""

  method: str
  identity: dict[str, Any]
  arguments: dict[str, Any]
  key_payload: dict[str, Any]

  @functools.cached_property
  def key(self) -> str:
    # No ``default=`` fallback: _jsonable has already reduced everything to a
    # JSON-native value, and a fallback would silently accept one whose
    # serialization isn't stable across processes.
    canonical = json.dumps(self.key_payload, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]

  def path(self) -> pathlib.Path:
    return cassette_dir() / self.method / f"{self.key}.json"


def _jsonable(value: Any) -> Any:
  """Converts an argument to a stable, JSON-serializable form.

  The result feeds a hash that a ``record`` run writes and a later ``replay``
  run recomputes, so it has to be stable across processes. Unrecognized types
  used to fall through to ``repr()``, which for an ordinary object includes
  its memory address, so the key changed every process and no cassette ever
  matched. Now it raises; add a case here for new argument types.

  Raises:
    CassetteError: If the value has no stable JSON form.
  """
  if value is None or isinstance(value, (bool, int, float, str)):
    return value
  if isinstance(value, enum.Enum):
    return _jsonable(value.value)
  if isinstance(value, pydantic.BaseModel):
    return value.model_dump(mode="json")
  if isinstance(value, type):
    # e.g. the ``response_schema`` argument of generate_structured.
    return f"{value.__module__}.{value.__qualname__}"
  if isinstance(value, (datetime.date, datetime.datetime, datetime.time)):
    return value.isoformat()
  if isinstance(value, collections.abc.Mapping):
    return {str(k): _jsonable(v) for k, v in value.items()}
  if isinstance(value, (list, tuple)):
    return [_jsonable(v) for v in value]
  if isinstance(value, (set, frozenset)):
    # Sorted, otherwise the key depends on hash randomization.
    return sorted(_jsonable(v) for v in value)
  raise CassetteError(
      f"Cannot build a stable cassette key from {type(value).__name__}. "
      "Add a case to recording._jsonable, or pass the parameter's name to "
      "@cassette(ignore=...) if it does not affect the response."
  )


def _scrub(value: Any, key_name: str = "") -> Any:
  """Replaces secret-looking values so cassettes are safe to read and share."""
  lowered = key_name.lower()
  if value and any(marker in lowered for marker in _SECRET_MARKERS):
    return "<redacted>"
  if isinstance(value, dict):
    return {k: _scrub(v, k) for k, v in value.items()}
  if isinstance(value, list):
    return [_scrub(v, key_name) for v in value]
  return value


def _provenance(client: Any) -> dict[str, Any]:
  """Metadata recorded alongside every cassette."""
  packages = (
      "google-cloud-geminidataanalytics",
      "google-genai",
  )
  versions = {}
  for package in packages:
    try:
      versions[package] = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
      continue
  return {
      "recorded_on": datetime.date.today().isoformat(),
      "client": type(client).__name__,
      "library_versions": versions,
  }


def _load(call: Call) -> Any:
  path = call.path()
  if not path.is_file():
    raise CassetteMissError(
        f"No cassette for {call.method}.\n"
        f"  looked for: {path}\n"
        "  request:    "
        f"{json.dumps(_scrub(call.key_payload), indent=2, sort_keys=True)}\n"
        "Re-record with PRISM_AGENT_BACKEND=record against a real project."
    )
  with path.open("r", encoding="utf-8") as handle:
    document = json.load(handle)
  return document["response"]


def write_cassette(
    call: Call,
    payload: Any,
    metadata: dict[str, Any] | None = None,
) -> pathlib.Path:
  """Writes one cassette to disk and returns its path.

  Public because tests turn responses they already have (golden fixtures, or
  ``trial.trace_results`` rows captured from a real project) into cassettes
  without going through ``record`` mode.

  Args:
    call: The call the cassette answers. Build it with ``plan_call()``.
    payload: The already-encoded response body, as the codec would encode it.
    metadata: Provenance. Defaults to a marker saying the cassette was written
      directly rather than recorded from a live call.

  Returns:
    The path written.
  """
  path = call.path()
  path.parent.mkdir(parents=True, exist_ok=True)
  document = {
      "metadata": metadata or {"source": "written directly, not recorded"},
      "request": _scrub(call.key_payload),
      "response": payload,
  }
  # Write to a sibling temp file and rename. In ``record`` mode the writers are
  # concurrent trial subprocesses and two can answer the same call; interleaved
  # writes would leave a truncated cassette that fails to parse on the next
  # replay. rename(2) within a directory is atomic.
  handle = tempfile.NamedTemporaryFile(
      mode="w",
      encoding="utf-8",
      dir=path.parent,
      prefix=f".{path.stem}.",
      suffix=".tmp",
      delete=False,
  )
  try:
    with handle:
      json.dump(document, handle, indent=2, sort_keys=True)
      handle.write("\n")
    os.replace(handle.name, path)
  except BaseException:
    pathlib.Path(handle.name).unlink(missing_ok=True)
    raise
  return path


def _save(call: Call, client: Any, payload: Any) -> None:
  path = write_cassette(call, payload, metadata=_provenance(client))
  logger.info("[cassette] recorded %s -> %s", call.method, path)


def cassette(
    codec: Codec | None = None,
    *,
    ignore: tuple[str, ...] = (),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
  """Routes a client method through the cassette layer.

  Args:
    codec: How to serialize and deserialize the return value. Defaults to
      ``RawCodec`` for methods that already return JSON-native values.
    ignore: Parameter names excluded from the cassette key. Use for arguments
      that do not change the response (credentials, for example).

  Returns:
    A decorator. In ``live`` mode the wrapper is a straight pass-through.
  """
  codec = codec or RawCodec()

  def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
    signature = inspect.signature(func)

    # Fail at import. A misspelled name would otherwise be a silent no-op,
    # leaving a parameter in the key that was meant to be out of it.
    unknown = set(ignore) - set(signature.parameters)
    if unknown:
      raise CassetteError(
          f"@cassette(ignore=...) on {func.__qualname__} names parameters it"
          f" does not have: {sorted(unknown)}."
      )

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
      backend = current_backend()
      if backend == LIVE:
        return func(self, *args, **kwargs)

      call = _build_call(
          method=func.__name__,
          signature=signature,
          ignore=ignore,
          identity=cassette_identity(self),
          args=(self,) + args,
          kwargs=kwargs,
      )

      if backend == REPLAY:
        return codec.decode(_load(call), call)

      result = func(self, *args, **kwargs)
      _save(call, self, codec.encode(result))
      return result

    # Stashed so plan_call() can rebuild a key through this same code path
    # instead of repeating the rule.
    wrapper.cassette_signature = signature
    wrapper.cassette_ignore = ignore
    return wrapper

  return decorator


def _build_call(
    *,
    method: str,
    signature: inspect.Signature,
    ignore: tuple[str, ...],
    identity: dict[str, Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Call:
  """Normalizes one call's arguments into a keyed ``Call``."""
  bound = signature.bind(*args, **kwargs)
  bound.apply_defaults()
  arguments = dict(bound.arguments)
  receiver = next(iter(signature.parameters), None)
  if receiver is not None:
    arguments.pop(receiver, None)
  key_arguments = {
      name: _jsonable(value)
      for name, value in arguments.items()
      if name not in ignore
  }
  return Call(
      method=method,
      identity=identity,
      arguments=arguments,
      key_payload={"identity": identity, "arguments": key_arguments},
  )


def plan_call(
    method: Callable[..., Any],
    identity: dict[str, Any],
    /,
    **arguments: Any,
) -> Call:
  """Builds the ``Call`` a decorated method would build for these args.

  Lets a test write a cassette that a later real call is guaranteed to find,
  without duplicating the key derivation.

  Args:
    method: The decorated client method, unbound. For example
      ``GeminiDataAnalyticsClient.ask_question``.
    identity: What ``client._cassette_identity()`` will return on the client
      that eventually makes the call.
    **arguments: The call's arguments, by keyword. Defaults are filled in and
      ``ignore``d parameters are dropped, exactly as at call time.

  Returns:
    A ``Call`` whose ``path()`` is where the cassette belongs.

  Raises:
    TypeError: If ``method`` is not decorated with ``@cassette``.
  """
  signature = getattr(method, "cassette_signature", None)
  if signature is None:
    raise TypeError(
        f"{getattr(method, '__qualname__', method)} is not a @cassette method."
    )
  return _build_call(
      method=method.__name__,
      signature=signature,
      ignore=getattr(method, "cassette_ignore", ()),
      identity=identity,
      # The receiver is dropped from the key, so a placeholder is enough.
      args=(None,),
      kwargs=arguments,
  )


def cassette_identity(client: Any) -> dict[str, Any]:
  """Returns the per-client fields that participate in the cassette key."""
  getter = getattr(client, "_cassette_identity", None)
  if callable(getter):
    return getter()
  return {}


def offline() -> bool:
  """True when the process must not make real API calls."""
  return current_backend() == REPLAY
