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

"""Static contract tests for the Dash callback graph.

The app sets ``suppress_callback_exceptions=True``, so Dash silently prunes
callbacks whose components are missing and defers arity errors to request
time. That hides a whole class of defects until someone clicks the wrong
button in production.

All of it can be decided from the registered callback map at import time, so
these tests need no browser and no database, and they cover every registered
callback, not just the paths a journey test happens to walk.
"""

import ast
import collections
import importlib
import inspect
import json
import pathlib
import re
import textwrap
import types
from typing import Any, Iterator

import dash
from dash import _callback
from prism.ui import ids as ids_module

# Importing the app registers every page and every callback.
from prism.ui.app import app
from prism.ui.ids import EvaluationIds
from prism.ui.pages.agent_ids import AgentIds

# Dash registers its own page router callbacks inside _setup_server(), and they
# reference ids Dash injects rather than ids our layouts build. Collection
# imports this module before any test runs a request, so the globals hold only
# our callbacks right now. Take the keys while that is still true.
_OUR_CALLBACKS = frozenset(_callback.GLOBAL_CALLBACK_MAP)


def _callback_specs() -> list[tuple[str, dict[str, Any]]]:
  """Returns (key, spec) for every callback the app registered.

  ``app._setup_server()`` moves the registrations off the module globals and
  onto the app, and it runs on the first request. A test that dispatches to the
  app empties the globals for whatever runs after it. Both places hold the same
  specs, so read whichever one is populated.
  """
  specs = _callback.GLOBAL_CALLBACK_MAP or app.callback_map
  # Four of the contracts below are loops. On an empty map they iterate zero
  # times and pass, which is how the drain hid for as long as it did.
  assert specs, "no callbacks registered"
  return [(key, spec) for key, spec in specs.items() if key in _OUR_CALLBACKS]


def _callback_list() -> list[dict[str, Any]]:
  """Returns every registered spec, in the shape that carries ``running``."""
  return (
      _callback.GLOBAL_CALLBACK_LIST
      or app._callback_list  # pylint: disable=protected-access
  )


def _raw_function(spec: dict[str, Any]):
  """Returns the undecorated Python function, or None for clientside.

  Unwraps all the way down. Dash wraps the registered callable and several
  callbacks add ``@handle_errors`` on top, so one ``__wrapped__`` hop lands on
  a ``(*args, **kwargs)`` shim instead of the real function.
  """
  wrapper = spec.get("callback")
  if wrapper is None:
    return None
  return inspect.unwrap(wrapper)


def _declared_output_count(spec: dict[str, Any]) -> int:
  """Returns how many outputs a callback declares."""
  output = spec["output"]
  return len(output) if isinstance(output, list) else 1


def _dependency_ids(spec: dict[str, Any]) -> tuple[set[str], set[str]]:
  """Returns (plain ids, pattern-matching ``type`` values) a callback uses.

  Dash stringifies dict ids into the ``inputs``/``state`` entries, so those are
  parsed back out rather than treated as plain ids.
  """
  plain: set[str] = set()
  patterns: set[str] = set()

  def _add(component_id: Any) -> None:
    if isinstance(component_id, dict):
      type_value = component_id.get("type")
      if isinstance(type_value, str):
        patterns.add(type_value)
      return
    if not isinstance(component_id, str):
      return
    if component_id.startswith("{"):
      try:
        _add(json.loads(component_id))
      except json.JSONDecodeError:
        pass
      return
    plain.add(component_id)

  for dep in spec.get("raw_inputs", []):
    _add(getattr(dep, "component_id", None))
  for dep in spec.get("inputs", []) + spec.get("state", []):
    _add(dep.get("id") if isinstance(dep, dict) else None)

  output = spec["output"]
  for dep in output if isinstance(output, list) else [output]:
    _add(getattr(dep, "component_id", None))

  return plain, patterns


_UI_PACKAGE_ROOT = pathlib.Path(ids_module.__file__).parent
_CALLBACKS_DIR = _UI_PACKAGE_ROOT / "callbacks"
_SRC_ROOT = _UI_PACKAGE_ROOT.parent.parent


def _id_constant_names() -> dict[str, set[str]]:
  """Maps each id string to the constant name(s) that define it.

  Looks inside every class declared in an ``*ids*.py`` module under the UI
  package, including nested ones such as ``AgentIds.Detail``.
  """
  by_value: dict[str, set[str]] = collections.defaultdict(set)

  def _visit(cls: type) -> None:
    for attr, value in vars(cls).items():
      if attr.startswith("_"):
        continue
      if isinstance(value, str):
        by_value[value].add(attr)
      elif isinstance(value, type):
        _visit(value)

  for path in sorted(_UI_PACKAGE_ROOT.rglob("*ids*.py")):
    relative = path.relative_to(_UI_PACKAGE_ROOT.parent.parent)
    module = importlib.import_module(
        str(relative.with_suffix("")).replace("/", ".")
    )
    for value in vars(module).values():
      if isinstance(value, type):
        _visit(value)

  return by_value


_CONSTRUCTED_VALUES_CACHE: set[str] | None = None

# Id constant names reached through an attribute chain this module cannot
# resolve. Populated by _attribute_value as the walks run, so anything reading
# it has to have walked first.
_DYNAMIC_ATTRS: set[str] = set()


_WILDCARDS = frozenset({"ALL", "MATCH", "ALLSMALLER"})


def _builds_pattern_id(node: ast.Dict) -> bool:
  """True if a dict literal builds a pattern-matching id, not uses one."""
  keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
  if len(keys) != len(node.keys) or "type" not in keys:
    return False
  for value in node.values:
    if isinstance(value, ast.Attribute) and value.attr in _WILDCARDS:
      return False
    if isinstance(value, ast.Name) and value.id in _WILDCARDS:
      return False
  return True


def _module_namespace(path: pathlib.Path) -> dict[str, Any]:
  """The globals of the UI module at ``path``, already imported by the app."""
  relative = path.relative_to(_SRC_ROOT).with_suffix("")
  return vars(importlib.import_module(str(relative).replace("/", ".")))


def _attribute_value(node: ast.Attribute, namespace: dict[str, Any]) -> Any:
  """Resolves ``Ids.Detail.BTN`` to the string it holds, or None.

  Only modules and classes are walked through. Going through an arbitrary
  object would evaluate properties, and ``dash.callback_context.triggered_id``
  raises outside a request.

  A chain rooted in something else, such as the ``ids_class`` argument
  ``assertion_components`` threads through, cannot be resolved from the
  source. Its leaf name goes into _DYNAMIC_ATTRS, which is the only thing the
  name fallback below is allowed to match.
  """
  parts = []
  current: ast.AST = node
  while isinstance(current, ast.Attribute):
    parts.append(current.attr)
    current = current.value
  if not isinstance(current, ast.Name):
    return None

  obj = namespace.get(current.id)
  if not isinstance(obj, (types.ModuleType, type)):
    # Id constants are all SCREAMING_CASE, so this keeps every ordinary
    # self.foo out of the fallback set.
    if parts[0].isupper():
      _DYNAMIC_ATTRS.add(parts[0])
    return None

  for part in reversed(parts):
    if isinstance(obj, types.ModuleType):
      obj = obj.__dict__.get(part)
    elif isinstance(obj, type):
      obj = vars(obj).get(part)
    else:
      return None
    if obj is None:
      return None
  return obj if isinstance(obj, str) else None


def _concat_value(node: ast.AST, namespace: dict[str, Any]) -> str | None:
  """Evaluates ``<id constant> + "suffix"`` chains to their string value."""
  if isinstance(node, ast.Constant):
    return node.value if isinstance(node.value, str) else None
  if isinstance(node, ast.Attribute):
    return _attribute_value(node, namespace)
  if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
    left = _concat_value(node.left, namespace)
    right = _concat_value(node.right, namespace)
    if left is not None and right is not None:
      return left + right
  return None


def _values_in(node: ast.AST, namespace: dict[str, Any]) -> set[str]:
  """Every id string ``node`` could produce.

  String literals, attribute chains resolved to their value, and
  concatenations, because ``id=Ids.SUGGESTION_LIST + "-group"`` produces an id
  that appears nowhere as a literal.
  """
  values: set[str] = set()
  for child in ast.walk(node):
    if isinstance(child, ast.Constant) and isinstance(child.value, str):
      values.add(child.value)
    elif isinstance(child, ast.Attribute):
      resolved = _attribute_value(child, namespace)
      if resolved is not None:
        values.add(resolved)
    elif isinstance(child, ast.BinOp) and isinstance(child.op, ast.Add):
      joined = _concat_value(child, namespace)
      if joined is not None:
        values.add(joined)
  return values


def _constructed_values() -> set[str]:
  """Every id value some module could attach to a component.

  Which source counts is coarse, because ids reach components through factory
  functions, dict-returning helpers, and a dynamically built id class
  (``type("AssertionModalIds", (), {...})`` in
  ``pages/test_suite_questions.py``):

  * everything in ``pages`` and ``components``, which exist to build
    components;
  * inside ``callbacks``, only the ``id=`` expressions. Callbacks both render
    components and declare dependencies on them, and only the former counts.

  What each source says is not coarse. An attribute is resolved to the id it
  holds, so the constant's name no longer stands in for its value. Names are
  reused: BTN_ARCHIVE is three different ids, and under the old name match any
  one of the three being rendered anywhere covered all three.

  An id no source produces is referenced by a callback and attached to
  nothing, which under ``suppress_callback_exceptions`` fails silently.
  """
  global _CONSTRUCTED_VALUES_CACHE
  if _CONSTRUCTED_VALUES_CACHE is not None:
    return _CONSTRUCTED_VALUES_CACHE

  values: set[str] = set()
  for path in sorted(_UI_PACKAGE_ROOT.rglob("*.py")):
    tree = ast.parse(path.read_text(), filename=str(path))
    namespace = _module_namespace(path)

    if _CALLBACKS_DIR in path.parents:
      # Charts and other shared renderers take the id under their own keyword
      # name (``container_id=``, ``dropdown_id=``), so match any *_id keyword.
      roots: list[ast.AST] = [
          keyword.value
          for node in ast.walk(tree)
          if isinstance(node, ast.Call)
          for keyword in node.keywords
          if keyword.arg == "id" or (keyword.arg or "").endswith("_id")
      ]
      # A dict literal with a concrete index builds a pattern-matching id; the
      # ALL/MATCH form is a dependency on components built elsewhere.
      roots += [
          node
          for node in ast.walk(tree)
          if isinstance(node, ast.Dict) and _builds_pattern_id(node)
      ]
    elif "ids" in path.name:
      # An id module's constants are declarations, not uses; counting them
      # would make this check vacuous. Its factory functions do build ids, so
      # scan only their bodies.
      roots = [
          node
          for node in ast.walk(tree)
          if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
      ]
    else:
      roots = [tree]

    for root in roots:
      values |= _values_in(root, namespace)

  _CONSTRUCTED_VALUES_CACHE = values
  return values


def _is_constructed(component_id: str, names: dict[str, set[str]]) -> bool:
  """True if some module could attach ``component_id`` to a component."""
  if component_id in _constructed_values():
    return True
  # Two ids are left, both reached as ``ids_class.INLINE_SUG_ADD_BTN`` on a
  # class handed in as an argument. Their constant names are all the source
  # says, so for those names only the old name match still applies.
  return bool(names.get(component_id, set()) & _DYNAMIC_ATTRS)


_REFERENCED_VALUES_CACHE: dict[pathlib.Path, set[str]] | None = None


def _referenced_values_by_module() -> dict[pathlib.Path, set[str]]:
  """Every id value each UI module names, keyed by the module that names it.

  Wider than _constructed_values, which only looks at ``id=`` expressions: a
  constant counts as referenced if anything reads it, dependency declarations
  included. Keyed by module so a constant's own definition can be left out.
  """
  global _REFERENCED_VALUES_CACHE
  if _REFERENCED_VALUES_CACHE is None:
    by_module = {}
    for path in sorted(_UI_PACKAGE_ROOT.rglob("*.py")):
      tree = ast.parse(path.read_text(), filename=str(path))
      namespace = _module_namespace(path)
      found: set[str] = set()
      for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
          value = _attribute_value(node, namespace)
          if value is not None:
            found.add(value)
      by_module[path] = found
    _REFERENCED_VALUES_CACHE = by_module
  return _REFERENCED_VALUES_CACHE


def _function_ast(func) -> ast.FunctionDef | None:
  """Parses just the source of ``func`` into a FunctionDef node."""
  try:
    source = textwrap.dedent(inspect.getsource(func))
  except (OSError, TypeError):
    return None
  try:
    module = ast.parse(source)
  except SyntaxError:
    return None
  for node in module.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
      return node
  return None


def _own_returns(fn_node: ast.FunctionDef) -> Iterator[ast.Return]:
  """Yields Return nodes belonging to ``fn_node``, not to nested functions."""
  stack: list[ast.AST] = list(ast.iter_child_nodes(fn_node))
  while stack:
    node = stack.pop()
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
      continue
    if isinstance(node, ast.Return):
      yield node
    stack.extend(ast.iter_child_nodes(node))


def test_app_registers_callbacks():
  """Sanity check that the map is populated before the contracts run."""
  assert len(_callback_specs()) > 100


def test_the_contracts_still_see_the_callbacks_after_a_request(dash_client):
  """One dispatch moves the registrations, and the contracts read them late.

  ``app._setup_server()`` empties the module globals into the app on the first
  request. Every contract below that loops over the map would then iterate
  nothing and pass. Alphabetical test order is what hid this, not anything in
  the tests themselves.
  """
  dash_client.get("/_dash-dependencies")

  assert not _callback.GLOBAL_CALLBACK_MAP
  assert len(_callback_specs()) > 100


def test_callback_signature_arity():
  """Each callback must accept exactly len(inputs) + len(state) arguments.

  Dash flattens inputs and state into positional arguments. A mismatch is an
  unconditional TypeError the moment the callback fires.
  """
  problems = []
  for _, spec in _callback_specs():
    func = _raw_function(spec)
    if func is None:  # clientside
      continue
    signature = inspect.signature(func)
    if any(
        p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
        for p in signature.parameters.values()
    ):
      continue
    declared = len(spec["inputs"]) + len(spec["state"])
    actual = len(signature.parameters)
    if declared != actual:
      problems.append(
          f"{func.__module__}.{func.__name__} "
          f"(line {func.__code__.co_firstlineno}): "
          f"declares {declared} dependencies but accepts {actual} arguments"
      )

  assert not problems, "Callback signature arity mismatch:\n  " + "\n  ".join(
      problems
  )


def test_callback_return_arity():
  """Literal tuple/list returns must match the declared output count."""
  problems = []
  for _, spec in _callback_specs():
    func = _raw_function(spec)
    if func is None:
      continue
    expected = _declared_output_count(spec)
    if expected == 1:
      # A single-output callback may legitimately return a tuple as its value.
      continue
    fn_node = _function_ast(func)
    if fn_node is None:
      continue
    for ret in _own_returns(fn_node):
      value = ret.value
      if not isinstance(value, (ast.Tuple, ast.List)):
        continue
      if any(isinstance(e, ast.Starred) for e in value.elts):
        continue
      if len(value.elts) != expected:
        problems.append(
            f"{func.__module__}.{func.__name__} "
            f"(return on line {func.__code__.co_firstlineno + ret.lineno - 1}):"
            f" returns {len(value.elts)} values but declares {expected} outputs"
        )

  assert not problems, "Callback return arity mismatch:\n  " + "\n  ".join(
      problems
  )


def test_page_layouts_render_with_default_arguments():
  """Every registered page layout must be callable with no arguments.

  Dash calls a page layout with only the path variables it parsed, so a bad
  default crashes the page for anyone arriving by a route that omits that
  variable.
  """
  failures = []
  for module_name, page in dash.page_registry.items():
    layout = page["layout"]
    if not callable(layout):
      continue
    try:
      layout()
    except Exception as exc:  # pylint: disable=broad-except
      failures.append(f"{module_name}: {type(exc).__name__}: {exc}")

  assert not failures, (
      "Page layout(s) raised when called with default arguments:\n  "
      + "\n  ".join(failures)
  )


def test_callback_component_ids_are_constructed_somewhere():
  """Every component id a callback references must be built by some component.

  suppress_callback_exceptions=True makes Dash prune callbacks whose
  components never appear, so a feature can be fully implemented, completely
  unreachable, and nothing fails.
  """
  names = _id_constant_names()

  missing = collections.defaultdict(list)
  for key, spec in _callback_specs():
    func = _raw_function(spec)
    label = (
        f"{func.__module__}.{func.__name__}" if func else f"clientside {key}"
    )
    used_plain, used_patterns = _dependency_ids(spec)
    for component_id in used_plain | used_patterns:
      if not _is_constructed(component_id, names):
        missing[component_id].append(label)

  assert not missing, (
      "Callback references component id(s) that no layout renders:\n  "
      + "\n  ".join(
          f"{cid!r} <- {sorted(set(users))}"
          for cid, users in sorted(missing.items())
      )
  )


def test_every_id_constant_is_referenced_outside_its_own_module():
  """An id nothing mentions is a component that was removed, or never built.

  52 of these had accumulated. Some named components deleted years of commits
  ago, some were the leftovers of a modal that was replaced by an inline
  editor. Reading the id classes as the inventory of the UI, which is what they
  are for, meant reading a list that was a fifth wrong.

  A reference is the constant's value, whether written as a literal anywhere
  in ``src`` or reached through an attribute chain that resolves to it. The
  literal scan is textual because it has to cover the clientside callbacks
  that carry ids as JavaScript strings.

  The bare constant name is not a reference. Names are reused across id
  classes: BTN_ARCHIVE names three different ids, so anything writing
  ``Ids.BTN_ARCHIVE`` used to vouch for all three at once.

  Only ``src`` is scanned. Counting the tests too meant an id that production
  had stopped rendering stayed "referenced" for as long as one test still
  named it, which is the case this is for.

  Values are matched as whole tokens. Ids nest: ``assert-modal`` is a prefix of
  ``assert-modal-open-btn`` and ``sug-accordion`` of ``sug-accordion-header``.
  There are 28 such pairs, and under a substring match the shorter one of each
  is referenced by the longer one and can never be reported.
  """
  root = pathlib.Path(__file__).resolve().parents[2]
  sources = {
      path: path.read_text() for path in sorted((root / "src").rglob("*.py"))
  }
  # The scan reports nothing if it reads nothing, and the tests it used to read
  # were most of what it read.
  assert len(sources) > 50, f"only {len(sources)} source files scanned"

  referenced = _referenced_values_by_module()
  unreferenced = []
  scanned = 0
  for path in sorted(_UI_PACKAGE_ROOT.rglob("*.py")):
    if "ids" not in path.name:
      continue
    tree = ast.parse(sources[path], filename=str(path))
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
      for node in cls.body:
        if not isinstance(node, ast.Assign):
          continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
          continue
        value = (
            node.value.value if isinstance(node.value, ast.Constant) else None
        )
        if not isinstance(value, str):
          continue
        scanned += 1
        elsewhere = [t for p, t in sources.items() if p != path]
        # Hyphens are not word characters, so \b would put a boundary inside
        # every id. The surrounding character has to be neither.
        token = rf"(?<![\w-]){re.escape(value)}(?![\w-])"
        quoted = any(re.search(token, t) for t in elsewhere)
        resolved = any(
            value in values
            for module, values in referenced.items()
            if module != path
        )
        # The ids_class indirection again. Its leaf names are all the source
        # has, so for those the name still counts.
        dynamic = target.id in _DYNAMIC_ATTRS
        if not quoted and not resolved and not dynamic:
          unreferenced.append(
              f"{path.name}:{node.lineno} {cls.name}.{target.id}"
          )

  assert scanned > 100, f"only {scanned} id constants scanned"
  assert (
      not unreferenced
  ), "Id constant(s) nothing references:\n  " + "\n  ".join(unreferenced)


def test_id_constants_are_unique_within_each_class():
  """Two names for one id makes call sites look distinct when they are not."""
  problems = []
  for class_name, cls in vars(ids_module).items():
    if not isinstance(cls, type):
      continue
    by_value = collections.defaultdict(list)
    for attr, value in vars(cls).items():
      if attr.startswith("_") or not isinstance(value, str):
        continue
      by_value[value].append(attr)
    for value, attrs in by_value.items():
      if len(attrs) > 1:
        problems.append(f"{class_name}: {sorted(attrs)} all equal {value!r}")

  assert not problems, "Aliased id constants:\n  " + "\n  ".join(problems)


def test_handle_errors_is_not_applied_above_the_callback_decorator():
  """@handle_errors must sit below @typed_callback to have any effect.

  Decorators apply bottom-up, and typed_callback registers the inner function
  with Dash immediately. Anything stacked above it wraps an object Dash never
  calls, so the error handling is dead code.
  """
  problems = []

  for path in sorted(_CALLBACKS_DIR.glob("*.py")):
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
      if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        continue
      names = [_decorator_name(d) for d in node.decorator_list]
      if "handle_errors" not in names:
        continue
      registrars = [
          i
          for i, n in enumerate(names)
          if n in ("typed_callback", "callback", "dash.callback")
      ]
      if not registrars:
        continue
      if names.index("handle_errors") < min(registrars):
        problems.append(
            f"{path.name}:{node.lineno} {node.name}: @handle_errors is above "
            "the callback decorator and is therefore dead code"
        )

  assert not problems, "Dead @handle_errors decorators:\n  " + "\n  ".join(
      problems
  )


def _decorator_name(node: ast.AST) -> str:
  """Best-effort dotted name of a decorator expression."""
  if isinstance(node, ast.Call):
    return _decorator_name(node.func)
  if isinstance(node, ast.Name):
    return node.id
  if isinstance(node, ast.Attribute):
    return f"{_decorator_name(node.value)}.{node.attr}"
  return ""


# The three buttons that start an evaluation run.
_RUN_START_BUTTONS = (
    EvaluationIds.BTN_START_RUN,
    EvaluationIds.BTN_START_NEW_EVAL,
    AgentIds.Detail.EvalModal.BTN_START,
)


def test_run_start_buttons_are_disabled_while_the_run_is_created():
  """Every run-start button must be disabled while its callback runs.

  Creating a run snapshots the agent context and spawns trials against a paid
  API, which takes long enough to click twice. The callback cannot tell an
  impatient second click from a deliberate second run, so Dash's ``running=``
  is what stops it.
  """
  problems = []
  for button_id in _RUN_START_BUTTONS:
    specs = [
        spec
        for spec in _callback_list()
        if any(
            dep.get("id") == button_id and dep.get("property") == "n_clicks"
            for dep in spec["inputs"]
        )
    ]
    if not specs:
      problems.append(f"{button_id}: no callback takes it as an Input")
    for spec in specs:
      while_running = spec.get("running", {}).get("running", {})
      if while_running.get(f"{button_id}.disabled") is not True:
        problems.append(
            f"{button_id}: the callback it fires does not disable it for the"
            " duration"
        )

  assert not problems, "Unguarded run-start button(s):\n  " + "\n  ".join(
      problems
  )


def _link_targets() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
  """Returns (exact, prefix) link targets, each mapped to the files using it.

  A plain ``href="/agents"`` is an exact target. An f-string contributes only
  the constant part before its first placeholder, which is enough to catch a
  detail route that was renamed out from under it.
  """
  exact = collections.defaultdict(set)
  prefixes = collections.defaultdict(set)

  for path in sorted(_UI_PACKAGE_ROOT.rglob("*.py")):
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
      if not isinstance(node, ast.keyword) or node.arg != "href":
        continue
      value = node.value
      if isinstance(value, ast.Constant) and isinstance(value.value, str):
        exact[value.value].add(path.name)
      elif isinstance(value, ast.JoinedStr) and value.values:
        head = value.values[0]
        if isinstance(head, ast.Constant) and isinstance(head.value, str):
          prefixes[head.value].add(path.name)

  # A link written any other way contributes nothing, and on an empty result
  # the checks below iterate zero times and pass.
  found = len(exact) + len(prefixes)
  assert found > 10, f"only {found} link targets found in the UI package"
  return exact, prefixes


def test_hrefs_point_at_registered_pages():
  """Every link written in the UI must lead to a page the app registers.

  A dead link raises nothing. Dash finds no page for the path and renders the
  404 layout, which reads as an unbuilt feature rather than a broken link.
  """
  paths = {str(page["path"]) for page in dash.page_registry.values()}
  templates = {
      str(page["path_template"])
      for page in dash.page_registry.values()
      if page.get("path_template")
  }

  exact, prefixes = _link_targets()
  problems = []

  for href, users in sorted(exact.items()):
    # "#" is an anchor and anything with a scheme leaves the app.
    if href in ("", "#") or "://" in href:
      continue
    if href not in paths:
      problems.append(f"{href!r} <- {sorted(users)}")

  for prefix, users in sorted(prefixes.items()):
    if "://" in prefix:
      continue
    if not any(p.startswith(prefix) for p in paths | templates):
      problems.append(f"{prefix}... <- {sorted(users)}")

  assert not problems, "Link(s) to no registered page:\n  " + "\n  ".join(
      problems
  )


# Controls that are rendered unwired on purpose, and why. Anything reaching
# this list is dead UI: it renders, it takes a click, and nothing runs.
_UNWIRED = {
    # Wrapped in a dmc.Anchor, so the href navigates and the id is spare.
    "agent-add-btn-cancel",
    "test-suite-cancel-new-btn",
}

# Controls a callback reads but never fires on. A click does nothing, and
# that is the design: the value is picked up by whatever button runs next.
_STATE_ONLY = {
    # Read by start_run and by the new-eval modal when Start Run is clicked.
    "eval-run-toggle-suggestions",
}

_CLICKABLE = ("Button", "ActionIcon", "Switch", "Checkbox")


def _walk_components(node, visit) -> None:
  """Calls ``visit`` on every component anywhere under ``node``.

  Walking ``children`` alone misses everything a component holds under
  another prop: dmc.Modal takes its header through ``title=``, dmc.Button its
  icon through ``leftSection=``, and dcc.Tab its content through ``label=``.
  The download-diff button lives in a modal title, so it was invisible to both
  contracts below.
  """
  if isinstance(node, (list, tuple)):
    for child in node:
      _walk_components(child, visit)
    return
  if isinstance(node, dict):
    for child in node.values():
      _walk_components(child, visit)
    return
  if not isinstance(node, dash.development.base_component.Component):
    return
  visit(node)
  for prop in getattr(node, "_prop_names", ()) or ():
    if hasattr(node, prop):
      _walk_components(getattr(node, prop), visit)


def _rendered_pages() -> Iterator[tuple[str, Any]]:
  """Yields (path, rendered layout) for every registered page.

  Every layout is callable with no arguments; that is what
  ``test_page_layouts_render_with_default_arguments`` holds.

  Three contracts are loops over this. On an empty registry they iterate zero
  times and pass, reporting nothing, which is how the callback-map drain hid
  for as long as it did. The floor is the same answer ``_callback_specs``
  gives.
  """
  assert (
      len(dash.page_registry) > 10
  ), f"only {len(dash.page_registry)} pages registered"
  for page in dash.page_registry.values():
    layout = page["layout"]
    yield str(page["path"]), (layout() if callable(layout) else layout)


def _rendered_controls() -> dict[str, str]:
  """Maps every clickable id in the page layouts to the page holding it.

  ``_CLICKABLE`` is matched against the class name, so a control rendered as a
  class it does not name contributes nothing and the orphan diff below comes
  back empty. The floor makes a shrinking walk fail rather than pass quietly.
  """
  found = {}

  for path, tree in _rendered_pages():

    def visit(node, path=path):
      component_id = getattr(node, "id", None)
      if isinstance(component_id, str) and type(node).__name__ in _CLICKABLE:
        found.setdefault(component_id, path)

    _walk_components(tree, visit)
  assert len(found) > 50, f"only {len(found)} controls found in the layouts"
  return found


def test_every_rendered_control_has_a_callback_behind_it():
  """A button nothing listens to is indistinguishable from a working one.

  The eval modal's close button shipped with an id built as
  ``BTN_CANCEL + "-x"``, which no callback declared, so the X did nothing.
  Neither the callback map nor the layout is wrong on its own, which is why
  this has to compare the two.

  Only Input counts. State is read when some other component fires, so a
  button that appears nowhere but a State list is exactly the dead button this
  is about: clicking it runs nothing.
  """
  wired = set()
  for _, spec in _callback_specs():
    for dependency in spec["inputs"]:
      if isinstance(dependency["id"], str):
        wired.add(dependency["id"])

  controls = _rendered_controls()
  orphans = {i: page for i, page in controls.items() if i not in wired}

  allowed = _UNWIRED | _STATE_ONLY
  new = {i: page for i, page in orphans.items() if i not in allowed}
  assert not new, "Control(s) no callback listens to:\n  " + "\n  ".join(
      f"{i} on {page}" for i, page in sorted(new.items())
  )

  # Otherwise the lists outlive the dead controls and start hiding live ones.
  stale = allowed - set(orphans)
  assert (
      not stale
  ), f"_UNWIRED/_STATE_ONLY name wired or absent controls: {sorted(stale)}"

  # _STATE_ONLY is an exemption from the Input rule, not from the whole
  # contract. A control nothing reads at all does not belong on it.
  read_as_state = set()
  for _, spec in _callback_specs():
    for dependency in spec["state"]:
      if isinstance(dependency["id"], str):
        read_as_state.add(dependency["id"])
  never_read = _STATE_ONLY - read_as_state
  assert not never_read, (
      "_STATE_ONLY names control(s) no callback reads as State either: "
      f"{sorted(never_read)}"
  )


def _count_id(node, counts: collections.Counter) -> None:
  """Tallies one component's id, if it has a plain string one."""
  component_id = getattr(node, "id", None)
  if isinstance(component_id, str):
    counts[component_id] += 1


def test_no_page_renders_the_same_id_twice():
  """Two elements, one id, and a callback writes to whichever React finds.

  The suggestion edit modal and the assertion modal both pass their ids into
  ``render_assertion_form_content``, and the suggestion one was passing the
  assertion modal's ``VAL_MSG``. Both alerts carried the same id on the same
  page, so the validation message the assertion modal writes was landing in a
  modal nothing opens.

  ``test_id_constants_are_unique_within_each_class`` cannot see this. The two
  constants are distinct; it is the rendered tree that collides.

  Every prop is walked, not just ``children``. A modal's header goes in
  ``title=`` and a button's icon in ``leftSection=``, and React does not care
  which prop a duplicate arrived under.
  """
  duplicates = {}

  for path, tree in _rendered_pages():
    counts = collections.Counter()
    _walk_components(tree, lambda node: _count_id(node, counts))
    repeated = sorted(i for i, n in counts.items() if n > 1)
    if repeated:
      duplicates[path] = repeated

  assert (
      not duplicates
  ), "Duplicate id(s) in a rendered page:\n  " + "\n  ".join(
      f"{page}: {', '.join(ids)}" for page, ids in sorted(duplicates.items())
  )
