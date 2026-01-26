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

"""Client for interacting with the Google Vertex AI API."""

import logging
from typing import Any, Type, TypeVar

from prism.server.config import settings
import pydantic
import vertexai
from vertexai.generative_models import GenerationConfig
from vertexai.generative_models import GenerativeModel

# Default model configuration
VERTEX_DEFAULT_MODEL = "gemini-2.5-flash"

ResponseSchema = TypeVar("ResponseSchema", bound=pydantic.BaseModel)


class VertexAIClient:
  """A client for interacting with the Google Vertex AI API."""

  def __init__(self, location: str | None = None):
    """Initializes the VertexAIClient.

    Args:
        location: Optional location. Defaults to GCP_LOCATION env var or
          'us-central1'.
    """
    try:
      self.location = location or settings.gcp_vertex_location
      self.project = settings.gcp_vertex_project

      vertexai.init(project=self.project, location=self.location)

    except Exception as e:  # pylint: disable=broad-except
      logging.error("[VertexAI] Failed to initialize Vertex AI: %s", e)
      raise

  def generate_text(
      self,
      prompt: str,
      model_name: str = VERTEX_DEFAULT_MODEL,
  ) -> str | None:
    """Generates text using the specified Gemini model.

    Args:
        prompt: The text prompt to send to the model.
        model_name: The name of the Gemini model to use.

    Returns:
        The generated text as a string, or None if failed.
    """
    try:
      model = GenerativeModel(model_name)
      response = model.generate_content(prompt)

      if response and response.candidates:
        # Assuming the first candidate is the one we want
        first_candidate = response.candidates[0]
        if first_candidate.content and first_candidate.content.parts:
          return first_candidate.content.parts[0].text

      logging.warning("Vertex AI response was empty or malformed.")
      return None

    except Exception as e:  # pylint: disable=broad-except
      logging.error(
          "[VertexAI] Error during text generation: %s", e, exc_info=True
      )
      raise

  def generate_structured(
      self,
      prompt: str,
      response_schema: Type[ResponseSchema],
      model_name: str = VERTEX_DEFAULT_MODEL,
  ) -> ResponseSchema | None:
    """Generates a structured response from the LLM with the given schema.

    Args:
        prompt: The text prompt to send to the model.
        response_schema: The Pydantic model class to use for validation.
        model_name: The name of the Gemini model to use.

    Returns:
        An instance of the response_schema or None if generation failed.
    """
    try:
      model = GenerativeModel(model_name)

      # Clean schema to be compatible with Vertex AI (no 'const')
      schema_dict = response_schema.model_json_schema()
      cleaned_schema = self._clean_schema(schema_dict)

      generation_config = GenerationConfig(
          response_mime_type="application/json",
          response_schema=cleaned_schema,
      )

      response = model.generate_content(
          prompt, generation_config=generation_config
      )

      if response and response.candidates:
        first_candidate = response.candidates[0]
        if first_candidate.content and first_candidate.content.parts:
          text = first_candidate.content.parts[0].text
          return response_schema.model_validate_json(text)

      logging.warning("Vertex AI structured response was empty.")
      return None

    except Exception as e:  # pylint: disable=broad-except
      logging.error(
          "[VertexAI] Error during structured generation: %s",
          e,
          exc_info=True,
      )
      raise

  def _clean_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
    """Recursively cleans schema to be compatible with Vertex AI.

    - Removes 'const' keys, replacing with 'enum'.
    - Removes 'null' types from 'anyOf' (Vertex AI doesn't support NULL type).
    - Hoists single-item 'anyOf' to the parent level.

    Args:
        schema: The JSON schema dictionary to clean.

    Returns:
        The cleaned JSON schema dictionary.
    """
    if not isinstance(schema, dict):
      return schema

    # Create a copy to modify
    clean = schema.copy()

    # Replace 'const' with 'enum'
    if "const" in clean:
      clean["enum"] = [clean.pop("const")]

    # Handle 'anyOf' for nullable fields
    if "anyOf" in clean and isinstance(clean["anyOf"], list):
      # Filter out null types
      any_of = [
          item
          for item in clean["anyOf"]
          if not (isinstance(item, dict) and item.get("type") == "null")
      ]

      if not any_of:
        # If everything was null (unlikely but possible), remove anyOf
        clean.pop("anyOf")
      elif len(any_of) == 1:
        # Hoist the single item
        single_item = any_of[0]
        clean.pop("anyOf")
        if isinstance(single_item, dict):
          clean.update(single_item)
      else:
        # Keep anyOf but with nulls removed
        clean["anyOf"] = any_of

    # Recurse
    for key, value in clean.items():
      if isinstance(value, dict):
        clean[key] = self._clean_schema(value)
      elif isinstance(value, list):
        clean[key] = [
            self._clean_schema(item) if isinstance(item, dict) else item
            for item in value
        ]

    return clean
