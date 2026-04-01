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

"""Dependency providers for the Direct Client."""

from typing import Generator

from fast_depends import Depends
from prism.server import db
from prism.server.clients import gemini_data_analytics_client
from prism.server.clients import gen_ai_client
from prism.server.config import settings
from prism.server.repositories import agent_repository
from prism.server.repositories import example_repository
from prism.server.repositories import run_repository
from prism.server.repositories import suite_repository
from prism.server.repositories import trial_repository
from prism.server.services import agent_service
from prism.server.services import ai_service
from prism.server.services import bulk_import_service
from prism.server.services import comparison_service
from prism.server.services import dashboard_service
from prism.server.services import execution_service
from prism.server.services import playground_service
from prism.server.services import snapshot_service
from prism.server.services import suggestion_service
from prism.server.services import suite_service
from prism.server.services import timeline_service
from prism.server.services import worker
from sqlalchemy import orm


# --- Client Cache ---
_GEN_AI_CLIENT: gen_ai_client.GenAIClient | None = None
_GDA_CLIENT: gemini_data_analytics_client.GeminiDataAnalyticsClient | None = (
    None
)


# --- Core Providers ---


def get_session() -> Generator[orm.Session, None, None]:
  """Provides a database session with auto-commit/rollback."""
  session = db.SessionLocal()
  try:
    yield session
    session.commit()
  except Exception:
    session.rollback()
    raise
  finally:
    session.close()


# --- Repository Providers ---


def get_agent_repository(
    session: orm.Session = Depends(get_session),
) -> agent_repository.AgentRepository:
  """Provides an AgentRepository."""
  return agent_repository.AgentRepository(session)


def get_suite_repository(
    session: orm.Session = Depends(get_session),
) -> suite_repository.SuiteRepository:
  """Provides a SuiteRepository."""
  return suite_repository.SuiteRepository(session)


def get_example_repository(
    session: orm.Session = Depends(get_session),
) -> example_repository.ExampleRepository:
  """Provides an ExampleRepository."""
  return example_repository.ExampleRepository(session)


def get_run_repository(
    session: orm.Session = Depends(get_session),
) -> run_repository.RunRepository:
  """Provides a RunRepository."""
  return run_repository.RunRepository(session)


def get_trial_repository(
    session: orm.Session = Depends(get_session),
) -> trial_repository.TrialRepository:
  """Provides a TrialRepository."""
  return trial_repository.TrialRepository(session)


# --- Service Providers ---


def get_agent_service(
    session: orm.Session = Depends(get_session),
    repo: agent_repository.AgentRepository = Depends(get_agent_repository),
) -> agent_service.AgentService:
  """Provides an AgentService."""
  return agent_service.AgentService(session, repo)


def get_suite_service(
    session: orm.Session = Depends(get_session),
    suite_repo: suite_repository.SuiteRepository = Depends(
        get_suite_repository
    ),
    example_repo: example_repository.ExampleRepository = Depends(
        get_example_repository
    ),
) -> suite_service.SuiteService:
  """Provides a SuiteService."""
  return suite_service.SuiteService(session, suite_repo, example_repo)


def get_snapshot_service(
    session: orm.Session = Depends(get_session),
    suite_repo: suite_repository.SuiteRepository = Depends(
        get_suite_repository
    ),
    example_repo: example_repository.ExampleRepository = Depends(
        get_example_repository
    ),
) -> snapshot_service.SnapshotService:
  """Provides a SnapshotService."""
  return snapshot_service.SnapshotService(session, suite_repo, example_repo)


def get_gen_ai_client() -> gen_ai_client.GenAIClient:
  """Provides a GenAIClient."""
  global _GEN_AI_CLIENT
  if _GEN_AI_CLIENT is None:
    _GEN_AI_CLIENT = gen_ai_client.GenAIClient(
        project=settings.gcp_genai_project,
        location=settings.gcp_genai_location,
    )
  return _GEN_AI_CLIENT


def get_suggestion_service(
    v_client: gen_ai_client.GenAIClient = Depends(get_gen_ai_client),
    trial_repo: trial_repository.TrialRepository = Depends(
        get_trial_repository
    ),
    ex_repo: example_repository.ExampleRepository = Depends(
        get_example_repository
    ),
) -> suggestion_service.SuggestionService:
  """Provides a SuggestionService."""
  return suggestion_service.SuggestionService(v_client, trial_repo, ex_repo)


def get_gda_client() -> gemini_data_analytics_client.GeminiDataAnalyticsClient:
  """Provides a GeminiDataAnalyticsClient."""
  global _GDA_CLIENT
  if _GDA_CLIENT is None:
    _GDA_CLIENT = gemini_data_analytics_client.GeminiDataAnalyticsClient(
        project=""
    )
  return _GDA_CLIENT


def get_execution_service(
    session: orm.Session = Depends(get_session),
    snap_service: snapshot_service.SnapshotService = Depends(
        get_snapshot_service
    ),
    sug_service: suggestion_service.SuggestionService = Depends(
        get_suggestion_service
    ),
    gda_client: gemini_data_analytics_client.GeminiDataAnalyticsClient = Depends(
        get_gda_client
    ),
) -> execution_service.ExecutionService:
  """Provides an ExecutionService."""
  return execution_service.ExecutionService(
      session, snap_service, gda_client, suggestion_service=sug_service
  )


def get_playground_service(
    session: orm.Session = Depends(get_session),
) -> playground_service.PlaygroundService:
  """Provides a PlaygroundService."""
  return playground_service.PlaygroundService(session)


def get_dashboard_service(
    session: orm.Session = Depends(get_session),
) -> dashboard_service.DashboardService:
  """Provides a DashboardService."""
  return dashboard_service.DashboardService(session)


def get_timeline_service() -> timeline_service.TimelineService:
  """Provides a TimelineService."""
  return timeline_service.TimelineService()


def get_comparison_service(
    session: orm.Session = Depends(get_session),
) -> comparison_service.ComparisonService:
  """Provides a ComparisonService."""
  return comparison_service.ComparisonService(session)


def get_bulk_import_service(
    v_client: gen_ai_client.GenAIClient = Depends(get_gen_ai_client),
) -> bulk_import_service.BulkImportService:
  """Provides a BulkImportService."""
  return bulk_import_service.BulkImportService(v_client)


def get_ai_service(
    v_client: gen_ai_client.GenAIClient = Depends(get_gen_ai_client),
) -> ai_service.AIService:
  """Provides an AIService."""
  return ai_service.AIService(v_client)


def get_worker_pool_service() -> worker.WorkerProcessManager:
  """Provides a WorkerProcessManager."""
  return worker.WorkerProcessManager()
