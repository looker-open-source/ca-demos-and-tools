"""Tests to ensure prism.common remains a leaf node with no dependencies on other prism modules."""

import ast
import os
import sys
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


def test_prism_common_isolation():
  """Ensures prism.common does not import from prism.server, prism.ui, or prism.client."""
  # Locate src/prism/common
  # Assuming this test runs from project root or proper python path
  # We try to find the absolute path relative to this test file
  base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  common_dir = os.path.join(base_dir, "src", "prism", "common")

  if not os.path.exists(common_dir):
    pytest.fail(f"Could not find prism.common directory at {common_dir}")

  forbidden_prefixes = [
      "prism.server",
      "prism.ui",
      "prism.client",
      # We could also ban 'prism.app' etc if they verify existent
  ]

  offending_imports = []

  for root, _, files in os.walk(common_dir):
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
        "Architecture Violation: prism.common must NOT import from other prism"
        " modules.\nFound the following violations:\n"
        + "\n".join(offending_imports)
    )
    pytest.fail(msg)
