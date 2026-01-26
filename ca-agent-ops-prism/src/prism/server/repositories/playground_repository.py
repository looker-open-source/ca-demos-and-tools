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

"""Repository for Playground Traces."""

from prism.server.models.playground import PlaygroundTrace
from sqlalchemy.orm import Session


class PlaygroundRepository:
  """Repository for Playground Traces."""

  def __init__(self, session: Session):
    self._session = session

  def save_trace(self, trace: PlaygroundTrace) -> PlaygroundTrace:
    """Saves a PlaygroundTrace."""
    self._session.add(trace)
    self._session.commit()
    self._session.refresh(trace)
    return trace

  def get_trace(self, trace_id: int) -> PlaygroundTrace | None:
    """Gets a PlaygroundTrace by ID."""
    return self._session.get(PlaygroundTrace, trace_id)
