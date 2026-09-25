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

"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

## Autogenerate indents every line after the first by four spaces, and hardcodes
## that four. A body written at this repo's two then lands its second operation
## deeper than its first and the file will not import, so the lines are pulled
## back to two on the way in. Continuation lines inside a call end up at six,
## which is legal and which the formatter tidies.


def upgrade() -> None:
  ${(upgrade if upgrade else "pass").replace("\n    ", "\n  ")}


def downgrade() -> None:
  ${(downgrade if downgrade else "pass").replace("\n    ", "\n  ")}
