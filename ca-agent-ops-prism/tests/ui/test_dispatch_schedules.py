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

"""HTTP callback dispatch tests for `/schedules` and scheduled run badges."""

from __future__ import annotations

import datetime
import json
from typing import Any
from unittest import mock

import fast_depends
from prism.client import dependencies
from prism.common.schemas.execution import RunStatus
from prism.common.schemas.schedule import ScheduleCadence
from prism.common.schemas.schedule import ScheduleCreate
from prism.common.schemas.schedule import ScheduleSchema
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
from prism.server.models.run import Run
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.schedule_repository import ScheduleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.execution_service import ExecutionService
from prism.server.services.schedule_service import ScheduleService
from prism.server.services.snapshot_service import SnapshotService
from prism.ui.callbacks import schedules_callbacks
from prism.ui.components import schedule_components
from prism.ui.constants import NOTIFICATION_CONTAINER
from prism.ui.ids import EvaluationIds
from prism.ui.ids import ScheduleIds
from prism.ui.pages import schedules as schedules_page
import pydantic
from tests.ui import dash_http

_UTC = datetime.timezone.utc


def _by_input(deps: list[dict[str, Any]], address: str) -> dict[str, Any]:
  matches = [
      dep
      for dep in deps
      if any(dash_http.address(i) == address for i in dep["inputs"])
  ]
  assert (
      len(matches) == 1
  ), f"expected 1 callback for {address!r}, got {matches}"
  return matches[0]


def _create_modal_dep(deps: list[dict[str, Any]]) -> dict[str, Any]:
  """Returns the callback the New Schedule button drives."""
  matches = [
      dep
      for dep in deps
      if any(
          ScheduleIds.BTN_OPEN_CREATE in dash_http.address(i)
          for i in dep["inputs"]
      )
  ]
  assert len(matches) == 1, matches
  return matches[0]


def _edit_modal_dep(deps: list[dict[str, Any]]) -> dict[str, Any]:
  """Returns the callback the detail page Edit button drives."""
  matches = [
      dep
      for dep in deps
      if any(
          ScheduleIds.BTN_EDIT in dash_http.address(i) for i in dep["inputs"]
      )
  ]
  assert len(matches) == 1, matches
  return matches[0]


def _modal_untouched(response) -> bool:
  """True when a modal callback answered without writing to the modal."""
  assert response.status_code in (200, 204), response.status_code
  written = dash_http.body(response).get("response", {})
  return ScheduleIds.MODAL not in written


def _seed_schedule(
    db_session,
    agent_id: int,
    suite_id: int,
    name: str = "Morning Ops Check",
    is_enabled: bool = True,
):
  """Seeds an EvalSchedule row via ScheduleService for UI callback tests."""
  gda_mock = mock.MagicMock(spec=GeminiDataAnalyticsClient)
  gda_mock.get_datasource_kind.return_value = "bq"
  gda_mock.get_agent_context.return_value = {"system_instruction": "UI test"}
  snap = SnapshotService(
      db_session, SuiteRepository(db_session), ExampleRepository(db_session)
  )
  exec_svc = ExecutionService(db_session, snap, gda_mock)
  sched_svc = ScheduleService(
      db_session, ScheduleRepository(db_session), exec_svc
  )
  return sched_svc.create_schedule(
      ScheduleCreate(
          name=name,
          agent_id=agent_id,
          test_suite_id=suite_id,
          cadence=ScheduleCadence.DAILY,
          cron_expression="0 9 * * *",
          timezone="UTC",
          concurrency=2,
          is_enabled=is_enabled,
      ),
      now=datetime.datetime(2026, 10, 30, 8, 0, tzinfo=_UTC),
  )


def test_schedules_page_load_renders_empty_state_then_rows_and_filters(
    dash_client, callback_errors, db_session, seeded
):
  """Verifies /schedules empty state, table rows, and URL query filter sync."""
  deps = dash_http.dependencies(dash_client)
  load_dep = dash_http.find(
      deps, f"{ScheduleIds.LIST_CONTAINER}.children", triggered_by="url"
  )

  # Empty state before any schedule exists.
  empty_resp = dash_http.fire_url(dash_client, load_dep, "/schedules", "")
  assert empty_resp.status_code == 200
  assert "No evaluation schedules configured" in json.dumps(
      dash_http.body(empty_resp)
  )
  callback_errors.assert_none()

  active_sched = _seed_schedule(
      db_session,
      seeded.agent_id,
      seeded.suite_id,
      name="Active Daily",
      is_enabled=True,
  )
  paused_sched = _seed_schedule(
      db_session,
      seeded.agent_id,
      seeded.suite_id,
      name="Paused Weekly",
      is_enabled=False,
  )

  all_resp = dash_http.fire_url(dash_client, load_dep, "/schedules", "")
  assert all_resp.status_code == 200
  dumped_all = json.dumps(dash_http.body(all_resp))
  assert "Active Daily" in dumped_all
  assert "Paused Weekly" in dumped_all
  assert active_sched.agent_name in dumped_all

  active_only = dash_http.fire_url(
      dash_client, load_dep, "/schedules", "?status=active"
  )
  dumped_active = json.dumps(dash_http.body(active_only))
  assert "Active Daily" in dumped_active
  assert "Paused Weekly" not in dumped_active

  paused_only = dash_http.fire_url(
      dash_client, load_dep, "/schedules", "?status=paused"
  )
  dumped_paused = json.dumps(dash_http.body(paused_only))
  assert "Paused Weekly" in dumped_paused
  assert "Active Daily" not in dumped_paused
  assert paused_sched.id is not None

  # Filter sync callbacks round-trip URL query parameters cleanly.
  sync_dep = dash_http.find(deps, f"{ScheduleIds.FILTER_STATUS}.value")
  sync_resp = dash_http.fire_url(
      dash_client,
      sync_dep,
      "/schedules",
      f"?agent_id={seeded.agent_id}&suite_id={seeded.suite_id}&status=active&archived=true",
  )
  sync_body = dash_http.body(sync_resp)["response"]
  assert sync_body[ScheduleIds.FILTER_AGENT]["value"] == str(seeded.agent_id)
  assert sync_body[ScheduleIds.FILTER_SUITE]["value"] == str(seeded.suite_id)
  assert sync_body[ScheduleIds.FILTER_STATUS]["value"] == "active"
  assert sync_body[ScheduleIds.SWITCH_ARCHIVED]["checked"]

  url_dep = _by_input(deps, f"{ScheduleIds.FILTER_AGENT}.value")
  url_resp = dash_http.fire(
      dash_client,
      url_dep,
      {
          f"{ScheduleIds.FILTER_AGENT}.value": str(seeded.agent_id),
          f"{ScheduleIds.FILTER_SUITE}.value": None,
          f"{ScheduleIds.FILTER_STATUS}.value": "paused",
          f"{ScheduleIds.SWITCH_ARCHIVED}.checked": False,
          "url.search": "?create=1&prefill_suite_id=3",
      },
      changed=[f"{ScheduleIds.FILTER_STATUS}.value"],
  )
  assert url_resp.status_code == 200
  new_search = dash_http.body(url_resp)["response"]["url"]["search"]
  assert f"agent_id={seeded.agent_id}" in new_search
  assert "status=paused" in new_search
  assert "create=" not in new_search
  callback_errors.assert_none()


def test_modal_prefill_preset_sync_preview_and_save_flow(
    dash_client, callback_errors, db_session, seeded
):
  """Verifies schedule modal deep-link prefill, preset sync, preview, and save."""
  del db_session
  deps = dash_http.dependencies(dash_client)
  modal_dep = _create_modal_dep(deps)

  # Deep-link prefill from ?create=1&prefill_suite_id=<id>.
  prefill_resp = dash_http.fire_url(
      dash_client,
      modal_dep,
      "/schedules",
      f"?create=1&prefill_suite_id={seeded.suite_id}",
  )
  assert prefill_resp.status_code == 200
  modal_body = dash_http.body(prefill_resp)["response"]
  assert modal_body[ScheduleIds.MODAL]["opened"]
  assert modal_body[ScheduleIds.SELECT_SUITE]["value"] == str(seeded.suite_id)
  assert (
      f"Daily {seeded.suite_name}" == modal_body[ScheduleIds.INPUT_NAME][
          "value"
      ]
  )

  # Preset controls sync HOURLY, WEEKLY, and CUSTOM.
  preset_dep = _by_input(deps, f"{ScheduleIds.SEGMENT_CADENCE}.value")
  weekly_resp = dash_http.fire(
      dash_client,
      preset_dep,
      {
          f"{ScheduleIds.SEGMENT_CADENCE}.value": "WEEKLY",
          f"{ScheduleIds.SELECT_DOW}.value": "3",
          f"{ScheduleIds.INPUT_HOUR}.value": 14,
          f"{ScheduleIds.INPUT_MINUTE}.value": 15,
      },
      changed=[f"{ScheduleIds.SEGMENT_CADENCE}.value"],
  )
  assert weekly_resp.status_code == 200
  assert (
      dash_http.body(weekly_resp)["response"][ScheduleIds.INPUT_CRON]["value"]
      == "15 14 * * 3"
  )

  # Live preview renders upcoming fires for valid cron and alert for invalid.
  preview_dep = dash_http.find(
      deps, f"{ScheduleIds.PREVIEW_CONTAINER}.children"
  )
  ok_preview = dash_http.fire(
      dash_client,
      preview_dep,
      {
          f"{ScheduleIds.INPUT_CRON}.value": "15 14 * * 3",
          f"{ScheduleIds.SELECT_TIMEZONE}.value": "America/New_York",
          f"{ScheduleIds.SWITCH_ENABLED}.checked": True,
          f"{ScheduleIds.SWITCH_SUGGESTIONS}.checked": True,
      },
  )
  assert ok_preview.status_code == 200
  assert "Run 1" in json.dumps(dash_http.body(ok_preview))
  assert "Run 3" in json.dumps(dash_http.body(ok_preview))

  bad_preview = dash_http.fire(
      dash_client,
      preview_dep,
      {
          f"{ScheduleIds.INPUT_CRON}.value": "99 99 * * *",
          f"{ScheduleIds.SELECT_TIMEZONE}.value": "UTC",
          f"{ScheduleIds.SWITCH_ENABLED}.checked": True,
          f"{ScheduleIds.SWITCH_SUGGESTIONS}.checked": False,
      },
  )
  assert bad_preview.status_code == 200
  assert "out of range" in json.dumps(dash_http.body(bad_preview))

  # Save schedule validation error then valid creation + edit.
  save_dep = _by_input(deps, f"{ScheduleIds.BTN_SAVE}.n_clicks")
  missing_name_resp = dash_http.fire(
      dash_client,
      save_dep,
      {
          f"{ScheduleIds.BTN_SAVE}.n_clicks": 1,
          f"{ScheduleIds.INPUT_NAME}.value": "   ",
          f"{ScheduleIds.SELECT_AGENT}.value": str(seeded.agent_id),
          f"{ScheduleIds.SELECT_SUITE}.value": str(seeded.suite_id),
      },
      changed=[f"{ScheduleIds.BTN_SAVE}.n_clicks"],
  )
  assert (
      dash_http.body(missing_name_resp)["response"][ScheduleIds.MODAL_ERROR][
          "children"
      ]
      == "Schedule name is required."
  )

  create_resp = dash_http.fire(
      dash_client,
      save_dep,
      {
          f"{ScheduleIds.BTN_SAVE}.n_clicks": 1,
          f"{ScheduleIds.STORE_EDIT_ID}.data": None,
          f"{ScheduleIds.INPUT_NAME}.value": "Created Via Callback",
          f"{ScheduleIds.SELECT_AGENT}.value": str(seeded.agent_id),
          f"{ScheduleIds.SELECT_SUITE}.value": str(seeded.suite_id),
          f"{ScheduleIds.SEGMENT_CADENCE}.value": "DAILY",
          f"{ScheduleIds.INPUT_CRON}.value": "0 9 * * *",
          f"{ScheduleIds.SELECT_TIMEZONE}.value": "UTC",
          f"{ScheduleIds.INPUT_CONCURRENCY}.value": 3,
          f"{ScheduleIds.SWITCH_SUGGESTIONS}.checked": False,
          f"{ScheduleIds.SWITCH_ENABLED}.checked": True,
          "url.search": f"?create=1&prefill_suite_id={seeded.suite_id}",
      },
      changed=[f"{ScheduleIds.BTN_SAVE}.n_clicks"],
  )
  assert create_resp.status_code == 200
  create_body = dash_http.body(create_resp)["response"]
  assert not create_body[ScheduleIds.MODAL]["opened"]
  created_id = create_body[ScheduleIds.UPDATE_SIGNAL]["data"]["schedule_id"]

  # Edit modal load from the detail page Edit button, then save update.
  edit_dep = _edit_modal_dep(deps)
  edit_wild = edit_dep["inputs"][0]
  edit_open_resp = dash_http.fire(
      dash_client,
      edit_dep,
      {dash_http.address(edit_wild): [(created_id, 1)]},
      changed=[dash_http.pattern_address(edit_wild, created_id)],
  )
  assert edit_open_resp.status_code == 200
  assert (
      dash_http.body(edit_open_resp)["response"][ScheduleIds.STORE_EDIT_ID][
          "data"
      ]
      == created_id
  )

  update_resp = dash_http.fire(
      dash_client,
      save_dep,
      {
          f"{ScheduleIds.BTN_SAVE}.n_clicks": 2,
          f"{ScheduleIds.STORE_EDIT_ID}.data": created_id,
          f"{ScheduleIds.INPUT_NAME}.value": "Renamed Via Callback",
          f"{ScheduleIds.SELECT_AGENT}.value": str(seeded.agent_id),
          f"{ScheduleIds.SELECT_SUITE}.value": str(seeded.suite_id),
          f"{ScheduleIds.SEGMENT_CADENCE}.value": "DAILY",
          f"{ScheduleIds.INPUT_CRON}.value": "0 10 * * *",
          f"{ScheduleIds.SELECT_TIMEZONE}.value": "UTC",
          f"{ScheduleIds.INPUT_CONCURRENCY}.value": 4,
          f"{ScheduleIds.SWITCH_SUGGESTIONS}.checked": True,
          f"{ScheduleIds.SWITCH_ENABLED}.checked": True,
          "url.search": "",
      },
      changed=[f"{ScheduleIds.BTN_SAVE}.n_clicks"],
  )
  assert update_resp.status_code == 200
  assert "Updated schedule" in json.dumps(
      dash_http.body(update_resp)["response"][NOTIFICATION_CONTAINER]
  )
  callback_errors.assert_none()


def test_row_actions_evaluations_schedule_filter_and_run_detail_badge(
    dash_client, callback_errors, db_session, seeded
):
  """Verifies row buttons, /evaluations schedule filter, and run header badge."""
  sched = _seed_schedule(
      db_session, seeded.agent_id, seeded.suite_id, name="Badge Schedule"
  )
  deps = dash_http.dependencies(dash_client)

  row_dep = next(
      dep
      for dep in deps
      if any(
          ScheduleIds.BTN_RUN_NOW in dash_http.address(i) for i in dep["inputs"]
      )
  )
  run_now_in = next(
      i
      for i in row_dep["inputs"]
      if ScheduleIds.BTN_RUN_NOW in dash_http.address(i)
  )
  pause_in = next(
      i
      for i in row_dep["inputs"]
      if ScheduleIds.BTN_TOGGLE_PAUSE in dash_http.address(i)
  )
  archive_in = next(
      i
      for i in row_dep["inputs"]
      if ScheduleIds.BTN_ARCHIVE_ROW in dash_http.address(i)
  )
  restore_in = next(
      i
      for i in row_dep["inputs"]
      if ScheduleIds.BTN_RESTORE_ROW in dash_http.address(i)
  )

  gda_mock = mock.MagicMock(spec=GeminiDataAnalyticsClient)
  gda_mock.get_datasource_kind.return_value = "bq"
  gda_mock.get_agent_context.return_value = {"system_instruction": "Row run"}

  with fast_depends.dependency_provider.scope(
      dependencies.get_gda_client, lambda: gda_mock
  ):
    run_resp = dash_http.fire(
        dash_client,
        row_dep,
        {dash_http.address(run_now_in): [(sched.id, 1)]},
        changed=[dash_http.pattern_address(run_now_in, sched.id)],
    )
    assert run_resp.status_code == 200
    run_id = dash_http.body(run_resp)["response"][ScheduleIds.UPDATE_SIGNAL][
        "data"
    ]["run_id"]

    # Second Run Now while active returns red Action Refused toast.
    refused_resp = dash_http.fire(
        dash_client,
        row_dep,
        {dash_http.address(run_now_in): [(sched.id, 2)]},
        changed=[dash_http.pattern_address(run_now_in, sched.id)],
    )
    assert "Action Refused" in json.dumps(dash_http.body(refused_resp))
    # The refusal still redraws the header, which re-enables the button the
    # click disabled in the browser.
    refused_signal = dash_http.body(refused_resp)["response"][
        ScheduleIds.UPDATE_SIGNAL
    ]["data"]
    assert refused_signal["action"] == "refused"

    # Pause, Resume, Archive, and Restore over HTTP.
    for inp, expected_word in [
        (pause_in, "Schedule Paused"),
        (pause_in, "Schedule Resumed"),
        (archive_in, "Schedule Archived"),
        (restore_in, "Schedule Restored"),
    ]:
      act_resp = dash_http.fire(
          dash_client,
          row_dep,
          {dash_http.address(inp): [(sched.id, 1)]},
          changed=[dash_http.pattern_address(inp, sched.id)],
      )
      assert act_resp.status_code == 200
      assert expected_word in json.dumps(dash_http.body(act_resp))

  # An unexpected failure also redraws the header, so the button comes back.
  failing_client = mock.MagicMock()
  failing_client.schedules.trigger_schedule_now.side_effect = RuntimeError(
      "context call failed"
  )
  with mock.patch.object(
      schedules_callbacks, "get_client", return_value=failing_client
  ):
    failed_resp = dash_http.fire(
        dash_client,
        row_dep,
        {dash_http.address(run_now_in): [(sched.id, 3)]},
        changed=[dash_http.pattern_address(run_now_in, sched.id)],
    )
  failed = dash_http.body(failed_resp)["response"]
  assert failed[ScheduleIds.UPDATE_SIGNAL]["data"]["action"] == "failed"
  assert "Action Failed" in json.dumps(failed[NOTIFICATION_CONTAINER])
  callback_errors.assert_logged("Schedule action schedules-btn-run-now failed")

  # Verify /evaluations?schedule_id=<id> renders filter banner and badge.
  eval_list_dep = dash_http.find(
      deps, f"{EvaluationIds.RUN_LIST_CONTAINER}.children", triggered_by="url"
  )
  eval_resp = dash_http.fire_url(
      dash_client, eval_list_dep, "/evaluations", f"?schedule_id={sched.id}"
  )
  assert eval_resp.status_code == 200
  dumped_eval = json.dumps(dash_http.body(eval_resp))
  assert "Filtered to runs from schedule: Badge Schedule" in dumped_eval
  assert "Scheduled" in dumped_eval
  assert f"/evaluations/runs/{run_id}" in dumped_eval
  assert f"/evaluations/runs/{seeded.run_id}" not in dumped_eval

  # Finish scheduled run and verify Run Detail header shows schedule provenance.
  db_session.get(Run, run_id).status = RunStatus.COMPLETED
  db_session.commit()

  store_dep = dash_http.find(deps, f"{EvaluationIds.RUN_DATA_STORE}.data")
  store_resp = dash_http.fire_url(
      dash_client, store_dep, f"/evaluations/runs/{run_id}", ""
  )
  assert store_resp.status_code == 200
  run_data = dash_http.body(store_resp)["response"][
      EvaluationIds.RUN_DATA_STORE
  ]["data"]

  detail_dep = dash_http.find(
      deps, f"{EvaluationIds.RUN_BREADCRUMBS_CONTAINER}.children"
  )
  detail_resp = dash_http.fire(
      dash_client,
      detail_dep,
      {f"{EvaluationIds.RUN_DATA_STORE}.data": run_data},
  )
  assert detail_resp.status_code == 200
  assert "Schedule: Badge Schedule" in json.dumps(dash_http.body(detail_resp))
  callback_errors.assert_none()


def test_schedules_components_helpers_and_edge_branches(
    dash_client, callback_errors, seeded
):
  """Verifies schedule UI helpers, error formatting, and modal edge branches."""
  page_node = schedules_page.layout()
  assert page_node is not None
  modal_node = schedule_components.render_schedule_modal()
  assert modal_node is not None

  now = datetime.datetime(2026, 10, 30, 12, 0, tzinfo=_UTC)
  archived_item = ScheduleSchema(
      id=91,
      name="Archived Nightly",
      agent_id=seeded.agent_id,
      test_suite_id=seeded.suite_id,
      agent_name="Agent Alpha",
      suite_name="Suite Beta",
      cadence=ScheduleCadence.HOURLY,
      cron_expression="0 * * * *",
      timezone="UTC",
      generate_suggestions=True,
      concurrency=4,
      is_enabled=False,
      is_archived=True,
      last_run_id=77,
      last_run_status=RunStatus.FAILED,
      last_error_message="PermissionDenied: caller lacks access (ref abc123)",
      created_at=now,
      modified_at=now,
  )
  rendered_table = schedule_components.render_schedule_table([archived_item])
  dumped_table = repr(rendered_table)
  assert "Archived Nightly" in dumped_table
  assert "Last Dispatch Failed" in dumped_table
  assert "#77" in dumped_table
  assert "/schedules/view/91" in dumped_table
  assert "Open schedule Archived Nightly" in dumped_table
  # Row actions moved to the detail page, so the list renders none of them.
  for action_id in (
      ScheduleIds.BTN_RUN_NOW,
      ScheduleIds.BTN_TOGGLE_PAUSE,
      ScheduleIds.BTN_EDIT,
      ScheduleIds.BTN_ARCHIVE_ROW,
      ScheduleIds.BTN_RESTORE_ROW,
  ):
    assert action_id not in dumped_table

  # pylint: disable=protected-access
  assert schedules_callbacks._extract_preset_fields("HOURLY", "15 * * * *") == (
      "1",
      9,
      15,
  )
  assert schedules_callbacks._extract_preset_fields("DAILY", "30 6 * * *") == (
      "1",
      6,
      30,
  )
  assert schedules_callbacks._extract_preset_fields("WEEKLY", "45 8 * * 5") == (
      "5",
      8,
      45,
  )
  assert schedules_callbacks._extract_preset_fields("CUSTOM", "bad") == (
      "1",
      9,
      0,
  )

  try:
    ScheduleCreate(
        name="Invalid",
        agent_id=1,
        test_suite_id=1,
        cadence=ScheduleCadence.CUSTOM,
        cron_expression="not a cron",
        timezone="UTC",
    )
  except pydantic.ValidationError as val_err:
    formatted_val = schedules_callbacks._format_validation_error(val_err)
    assert "cron_expression" in formatted_val

  assert (
      schedules_callbacks._format_validation_error(ValueError("bad tz"))
      == "bad tz"
  )
  assert "Check the server log" in schedules_callbacks._format_validation_error(
      RuntimeError("boom")
  )
  # pylint: enable=protected-access

  deps = dash_http.dependencies(dash_client)

  # Populate filter options on /schedules and non-/schedules.
  pop_dep = dash_http.find(deps, f"{ScheduleIds.FILTER_AGENT}.data")
  assert (
      dash_http.fire_url(dash_client, pop_dep, "/agents", "").status_code == 200
  )
  pop_ok = dash_http.fire_url(dash_client, pop_dep, "/schedules", "")
  assert pop_ok.status_code == 200
  assert dash_http.body(pop_ok)["response"][ScheduleIds.FILTER_AGENT]["data"]

  # Refresh callback via interval tick.
  refresh_dep = _by_input(deps, f"{ScheduleIds.POLL_INTERVAL}.n_intervals")
  ref_resp = dash_http.fire(
      dash_client,
      refresh_dep,
      {
          f"{ScheduleIds.POLL_INTERVAL}.n_intervals": 1,
          f"{ScheduleIds.UPDATE_SIGNAL}.data": None,
          "url.pathname": "/schedules",
          "url.search": "",
      },
      changed=[f"{ScheduleIds.POLL_INTERVAL}.n_intervals"],
  )
  assert ref_resp.status_code == 200

  # Empty search sync + clear filters URL round-trip.
  sync_dep = dash_http.find(deps, f"{ScheduleIds.FILTER_STATUS}.value")
  empty_sync = dash_http.fire_url(dash_client, sync_dep, "/schedules", "")
  assert not dash_http.body(empty_sync)["response"][
      ScheduleIds.SWITCH_ARCHIVED
  ]["checked"]

  url_dep = _by_input(deps, f"{ScheduleIds.FILTER_AGENT}.value")
  clear_url = dash_http.fire(
      dash_client,
      url_dep,
      {
          f"{ScheduleIds.FILTER_AGENT}.value": None,
          f"{ScheduleIds.FILTER_SUITE}.value": str(seeded.suite_id),
          f"{ScheduleIds.FILTER_STATUS}.value": "active",
          f"{ScheduleIds.SWITCH_ARCHIVED}.checked": True,
          "url.search": "?agent_id=1",
      },
      changed=[f"{ScheduleIds.SWITCH_ARCHIVED}.checked"],
  )
  assert (
      "archived=true" in dash_http.body(clear_url)["response"]["url"]["search"]
  )

  # Modal open via prefill_agent_id, BTN_OPEN_CREATE, and BTN_CANCEL.
  modal_dep = _create_modal_dep(deps)
  agent_prefill = dash_http.fire_url(
      dash_client,
      modal_dep,
      "/schedules",
      f"?create=1&prefill_agent_id={seeded.agent_id}",
  )
  assert (
      f"Daily {seeded.agent_name} Check"
      == dash_http.body(agent_prefill)["response"][ScheduleIds.INPUT_NAME][
          "value"
      ]
  )

  open_wild = modal_dep["inputs"][0]
  open_click = dash_http.fire(
      dash_client,
      modal_dep,
      {
          dash_http.address(open_wild): [("header", 1)],
          "url.pathname": "/schedules",
          "url.search": "",
      },
      changed=[dash_http.pattern_address(open_wild, "header")],
  )
  assert dash_http.body(open_click)["response"][ScheduleIds.MODAL]["opened"]

  # Create callback ignores every page but /schedules.
  off_page = dash_http.fire(
      dash_client,
      modal_dep,
      {
          dash_http.address(open_wild): [("header", 1)],
          "url.pathname": "/schedules/view/1",
          "url.search": "?create=1",
      },
      changed=[dash_http.pattern_address(open_wild, "header")],
  )
  assert _modal_untouched(off_page)

  # A plain /schedules load with no create flag leaves the modal alone.
  no_create = dash_http.fire_url(dash_client, modal_dep, "/schedules", "")
  assert _modal_untouched(no_create)

  cancel_dep = _by_input(deps, f"{ScheduleIds.BTN_CANCEL}.n_clicks")
  cancel_click = dash_http.fire(
      dash_client,
      cancel_dep,
      {f"{ScheduleIds.BTN_CANCEL}.n_clicks": 1},
      changed=[f"{ScheduleIds.BTN_CANCEL}.n_clicks"],
  )
  cancel_body = dash_http.body(cancel_click)["response"]
  assert not cancel_body[ScheduleIds.MODAL]["opened"]
  assert cancel_body[ScheduleIds.MODAL_ERROR]["hide"]

  unclicked_cancel = dash_http.fire(
      dash_client,
      cancel_dep,
      {f"{ScheduleIds.BTN_CANCEL}.n_clicks": None},
      changed=[f"{ScheduleIds.BTN_CANCEL}.n_clicks"],
  )
  assert _modal_untouched(unclicked_cancel)

  # Edit for a schedule that no longer exists, and an unclicked Edit button.
  edit_dep = _edit_modal_dep(deps)
  edit_wild = edit_dep["inputs"][0]
  missing_edit = dash_http.fire(
      dash_client,
      edit_dep,
      {dash_http.address(edit_wild): [(987654, 1)]},
      changed=[dash_http.pattern_address(edit_wild, 987654)],
  )
  assert _modal_untouched(missing_edit)
  unclicked_edit = dash_http.fire(
      dash_client,
      edit_dep,
      {dash_http.address(edit_wild): [(987654, None)]},
      changed=[dash_http.pattern_address(edit_wild, 987654)],
  )
  assert _modal_untouched(unclicked_edit)

  # Preset CUSTOM branch and empty preview branch.
  preset_dep = _by_input(deps, f"{ScheduleIds.SEGMENT_CADENCE}.value")
  custom_preset = dash_http.fire(
      dash_client,
      preset_dep,
      {
          f"{ScheduleIds.SEGMENT_CADENCE}.value": "CUSTOM",
          f"{ScheduleIds.SELECT_DOW}.value": "1",
          f"{ScheduleIds.INPUT_HOUR}.value": 9,
          f"{ScheduleIds.INPUT_MINUTE}.value": 0,
      },
      changed=[f"{ScheduleIds.SEGMENT_CADENCE}.value"],
  )
  assert (
      dash_http.body(custom_preset)["response"][ScheduleIds.PRESET_CONTROLS][
          "style"
      ]["display"]
      == "none"
  )

  preview_dep = dash_http.find(
      deps, f"{ScheduleIds.PREVIEW_CONTAINER}.children"
  )
  blank_prev = dash_http.fire(
      dash_client,
      preview_dep,
      {
          f"{ScheduleIds.INPUT_CRON}.value": "   ",
          f"{ScheduleIds.SELECT_TIMEZONE}.value": "UTC",
          f"{ScheduleIds.SWITCH_ENABLED}.checked": False,
          f"{ScheduleIds.SWITCH_SUGGESTIONS}.checked": False,
      },
  )
  assert "Enter a 5-field cron expression" in json.dumps(
      dash_http.body(blank_prev)
  )

  # Save missing agent, missing suite, and invalid cron ValidationError.
  save_dep = _by_input(deps, f"{ScheduleIds.BTN_SAVE}.n_clicks")
  no_agent = dash_http.fire(
      dash_client,
      save_dep,
      {
          f"{ScheduleIds.BTN_SAVE}.n_clicks": 1,
          f"{ScheduleIds.INPUT_NAME}.value": "Valid Name",
          f"{ScheduleIds.SELECT_AGENT}.value": None,
          f"{ScheduleIds.SELECT_SUITE}.value": str(seeded.suite_id),
      },
      changed=[f"{ScheduleIds.BTN_SAVE}.n_clicks"],
  )
  assert (
      dash_http.body(no_agent)["response"][ScheduleIds.MODAL_ERROR]["children"]
      == "Select an agent to evaluate."
  )

  no_suite = dash_http.fire(
      dash_client,
      save_dep,
      {
          f"{ScheduleIds.BTN_SAVE}.n_clicks": 1,
          f"{ScheduleIds.INPUT_NAME}.value": "Valid Name",
          f"{ScheduleIds.SELECT_AGENT}.value": str(seeded.agent_id),
          f"{ScheduleIds.SELECT_SUITE}.value": None,
      },
      changed=[f"{ScheduleIds.BTN_SAVE}.n_clicks"],
  )
  assert (
      dash_http.body(no_suite)["response"][ScheduleIds.MODAL_ERROR]["children"]
      == "Select a test suite to run."
  )

  bad_cron_save = dash_http.fire(
      dash_client,
      save_dep,
      {
          f"{ScheduleIds.BTN_SAVE}.n_clicks": 1,
          f"{ScheduleIds.STORE_EDIT_ID}.data": None,
          f"{ScheduleIds.INPUT_NAME}.value": "Valid Name",
          f"{ScheduleIds.SELECT_AGENT}.value": str(seeded.agent_id),
          f"{ScheduleIds.SELECT_SUITE}.value": str(seeded.suite_id),
          f"{ScheduleIds.SEGMENT_CADENCE}.value": "CUSTOM",
          f"{ScheduleIds.INPUT_CRON}.value": "bad cron",
          f"{ScheduleIds.SELECT_TIMEZONE}.value": "UTC",
          f"{ScheduleIds.INPUT_CONCURRENCY}.value": 2,
          f"{ScheduleIds.SWITCH_SUGGESTIONS}.checked": False,
          f"{ScheduleIds.SWITCH_ENABLED}.checked": True,
          "url.search": "",
      },
      changed=[f"{ScheduleIds.BTN_SAVE}.n_clicks"],
  )
  assert "cron_expression" in (
      dash_http.body(bad_cron_save)["response"][ScheduleIds.MODAL_ERROR][
          "children"
      ]
  )
  callback_errors.assert_none()
