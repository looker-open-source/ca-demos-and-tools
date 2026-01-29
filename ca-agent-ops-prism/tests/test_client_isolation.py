"""Tests to enforce architecture boundaries for prism.client."""

import ast
import os
from typing import Set

import pytest


def get_imports(file_path: str) -> Set[str]:
  """Parses a Python file and returns a set of imported module names."""
  with open(file_path, "r", encoding="utf-8") as f:
    try:
      tree = ast.parse(f.read(), filename=file_path)
    except SyntaxError:
      return set()

  imports = set()
  for node in ast.walk(tree):
    if isinstance(node, ast.Import):
      for alias in node.names:
        imports.add(alias.name)
    elif isinstance(node, ast.ImportFrom):
      if node.module:
        imports.add(node.module)
  return imports


def test_client_imports():
  """Client MUST NOT import from prism.ui.

  Allowed prism.* imports:
  - prism.client
  - prism.server
  - prism.common
  """
  # Locate src/prism/client
  base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  client_dir = os.path.join(base_dir, "src", "prism", "client")

  if not os.path.exists(client_dir):
    pytest.fail(f"Could not find prism.client directory at {client_dir}")

  forbidden_prefixes = [
      "prism.ui",
  ]
  offending_imports = []

  for root, _, files in os.walk(client_dir):
    for file in files:
      if not file.endswith(".py"):
        continue

      file_path = os.path.join(root, file)
      rel_path = os.path.relpath(file_path, base_dir)

      imports = get_imports(file_path)

      for imp in imports:
        for prefix in forbidden_prefixes:
          if imp == prefix or imp.startswith(prefix + "."):
            offending_imports.append(f"{rel_path}: imports '{imp}'")

  if offending_imports:
    msg = (
        "Architecture Violation: prism.client must NOT import from prism.ui.\n"
        "Found the following violations:\n"
        + "\n".join(offending_imports)
    )
    pytest.fail(msg)
