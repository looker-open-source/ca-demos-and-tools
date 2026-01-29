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

"""Service for validating assertion data using Pydantic schemas."""

import logging
from typing import Any

from prism.common.schemas.assertion import AssertionRequest
import pydantic
import yaml


def validate_assertion(assertion_data: dict[str, Any]) -> str | None:
  """Validates assertion data against Pydantic schemas.

  Args:
      assertion_data: The raw assertion data to validate.

  Returns:
      A user-friendly error message if validation fails, else None.
  """
  try:
    # Use TypeAdapter for the discriminated union
    pydantic.TypeAdapter(AssertionRequest).validate_python(assertion_data)
    return None
  except pydantic.ValidationError as e:
    # Format a user-friendly error message
    error_msgs = []
    for error in e.errors():
      loc = " -> ".join(str(l) for l in error["loc"])
      msg = error["msg"]
      error_msgs.append(f"{loc}: {msg}")

    error_str = "; ".join(error_msgs)
    logging.warning("Assertion validation failed: %s", error_str)
    return error_str
  except Exception as e:  # pylint: disable=broad-exception-caught
    logging.exception("Unexpected error during assertion validation")
    return str(e)


def parse_yaml_safely(
    yaml_str: str,
) -> tuple[dict[str, Any] | None, str | None]:
  """Parses YAML string safely and returns (data, error_message)."""
  if not yaml_str:
    return {}, None
  try:
    data = yaml.safe_load(yaml_str)
    if not isinstance(data, dict):
      return None, "YAML must resolve to a dictionary/object."
    return data, None
  except yaml.YAMLError as e:
    return None, f"Invalid YAML format: {str(e)}"
  except Exception as e:  # pylint: disable=broad-exception-caught
    return None, f"Unexpected error parsing YAML: {str(e)}"
