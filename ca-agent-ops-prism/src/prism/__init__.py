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

"""Prism Core Backend Package."""

import ast
import hashlib
from importlib import metadata
import pathlib


def _compute_code_hash() -> str:
  """Returns a short SHA-256 digest of the package AST and prompt templates."""
  pkg_dir = pathlib.Path(__file__).resolve().parent
  digest = hashlib.sha256()
  for path in sorted(pkg_dir.rglob("*")):
    if not path.is_file() or "__pycache__" in path.parts:
      continue
    rel = path.relative_to(pkg_dir).as_posix()
    if path.suffix == ".py":
      tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
      digest.update(f"{rel}\0{ast.dump(tree)}\n".encode("utf-8"))
    elif path.suffix == ".txt":
      text = path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
      digest.update(f"{rel}\0{text}\n".encode("utf-8"))
  return digest.hexdigest()[:7]


__code_hash__ = _compute_code_hash()
try:
  _pkg_version = metadata.version("prism")
except metadata.PackageNotFoundError:
  _pkg_version = "0.1.1"
__version__ = f"{_pkg_version}+{__code_hash__}"
