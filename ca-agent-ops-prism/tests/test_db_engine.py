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

"""Pooling settings on the shared engine."""

from prism.server import db


def test_the_pool_validates_and_retires_connections():
  """Cloud Run idles and Cloud SQL hangs up, and the pool cannot tell.

  Without these the first query after a quiet spell raises OperationalError on
  a connection the pool still believes is good. There is no public accessor for
  either setting, so this reads the private attributes create_engine wrote.
  """
  pool = db.engine.pool

  assert pool._pre_ping is True  # pylint: disable=protected-access
  assert pool._recycle == 1800  # pylint: disable=protected-access
