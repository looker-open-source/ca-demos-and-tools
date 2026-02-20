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

"""Service for AI-assisted operations like formatting and generation."""

import json
import logging
import os

from prism.common.schemas import agent as agent_schemas
from prism.server.clients import gen_ai_client
import pydantic
import yaml

# Path to the prompt templates
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")
GOLDEN_QUERY_PROMPT_PATH = os.path.join(PROMPTS_DIR, "golden_query_prompt.txt")


class AIService:
  """Service for AI-assisted operations."""

  def __init__(self, gen_ai_client_inst: gen_ai_client.GenAIClient):
    self.gen_ai_client = gen_ai_client_inst
    self._golden_query_template = self._load_prompt_template(
        GOLDEN_QUERY_PROMPT_PATH
    )

  def _load_prompt_template(self, path: str) -> str:
    """Loads a prompt template from the file system."""
    try:
      with open(path, "r") as f:
        return f.read()
    except FileNotFoundError:
      logging.error("Prompt template not found at %s", path)
      return ""

  def format_golden_queries(self, input_text: str) -> str:
    """Uses Gemini to format text into a list of LookerGoldenQuery objects."""
    if not input_text.strip():
      return ""

    prompt = self._golden_query_template.replace("{{input_text}}", input_text)

    try:
      # Pydantic schema for the list of golden queries
      class GoldenQueriesResponse(pydantic.BaseModel):
        golden_queries: list[agent_schemas.LookerGoldenQuery]

      response = self.gen_ai_client.generate_structured(
          prompt, GoldenQueriesResponse
      )

      if not response or not response.golden_queries:
        return input_text

      # Convert to JSON for the editor
      data = [gq.model_dump(mode="json") for gq in response.golden_queries]
      return json.dumps(data, indent=2)

    except Exception:  # pylint: disable=broad-except
      logging.exception("Failed to format golden queries with AI")
      return input_text
