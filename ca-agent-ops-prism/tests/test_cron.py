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

"""Unit tests for the pure-Python timezone-aware cron parser and calculator."""

import datetime

from prism.common import cron
import pytest

_UTC = datetime.timezone.utc


def test_parse_cron_accepts_standard_5_field_forms():
  parsed = cron.parse_cron_expression("*/15 9-17 1,15 JAN-JUN MON-FRI")
  assert parsed.minutes == (0, 15, 30, 45)
  assert parsed.hours == tuple(range(9, 18))
  assert parsed.days_of_month == (1, 15)
  assert parsed.months == tuple(range(1, 7))
  assert parsed.days_of_week == (1, 2, 3, 4, 5)
  assert parsed.dom_restricted
  assert parsed.dow_restricted


def test_star_step_day_field_combines_with_and_like_standard_cron():
  """A "*/2" day of month is unrestricted, so both day fields must match."""
  parsed = cron.parse_cron_expression("0 9 */2 * 1")
  assert not parsed.dom_restricted
  assert parsed.dow_restricted

  runs = cron.preview_next_runs(
      "0 9 */2 * 1",
      tz_name="UTC",
      count=3,
      after=datetime.datetime(2026, 11, 1, tzinfo=_UTC),
  )
  # Odd-numbered Mondays only: Nov 9 and 23, then Dec 7.
  assert [r.date() for r in runs] == [
      datetime.date(2026, 11, 9),
      datetime.date(2026, 11, 23),
      datetime.date(2026, 12, 7),
  ]


def test_both_restricted_day_fields_combine_with_or():
  """Two restricted day fields match when either one does."""
  runs = cron.preview_next_runs(
      "0 9 1 * 1",
      tz_name="UTC",
      count=3,
      after=datetime.datetime(2026, 10, 30, tzinfo=_UTC),
  )
  # Nov 1 (the 1st) or any Monday (Nov 2, Nov 9).
  assert [r.date() for r in runs] == [
      datetime.date(2026, 11, 1),
      datetime.date(2026, 11, 2),
      datetime.date(2026, 11, 9),
  ]


def test_parse_cron_maps_sunday_seven_to_zero():
  parsed = cron.parse_cron_expression("0 8 * * 7")
  assert parsed.days_of_week == (0,)
  assert not parsed.dom_restricted
  assert parsed.dow_restricted


@pytest.mark.parametrize(
    "bad_expr",
    [
        "",
        "0 9 * *",
        "0 9 * * * *",
        "60 9 * * *",
        "0 24 * * *",
        "0 9 0 * *",
        "0 9 32 * *",
        "0 9 * 13 *",
        "0 9 * * 8",
        "*/0 9 * * *",
        "10-5 9 * * *",
        "0 0 31 2 *",
        "0 0 31 4 *",
        "abc 9 * * *",
    ],
)
def test_parse_cron_rejects_invalid_expressions(bad_expr: str):
  """Rejects malformed or unreachable 5-field cron expressions."""
  with pytest.raises(ValueError):
    cron.parse_cron_expression(bad_expr)


def test_leap_day_expression_resolves_next_leap_year():
  after = datetime.datetime(2026, 3, 1, 0, 0, tzinfo=_UTC)
  nxt = cron.next_run_time("0 0 29 2 *", tz_name="UTC", after=after)
  assert nxt == datetime.datetime(2028, 2, 29, 0, 0, tzinfo=_UTC)


def test_dom_and_dow_union_semantics_match_posix_cron():
  # Both DOM (15th) and DOW (Monday=1) restricted: fires on whichever comes
  # first. 2026-06-01 is a Monday, before 2026-06-15.
  after = datetime.datetime(2026, 5, 31, 12, 0, tzinfo=_UTC)
  nxt = cron.next_run_time("0 9 15 * 1", tz_name="UTC", after=after)
  assert nxt == datetime.datetime(2026, 6, 1, 9, 0, tzinfo=_UTC)


def test_dst_spring_forward_skips_nonexistent_local_hour():
  # In America/New_York on 2026-03-08, clocks jump from 01:59 EST to 03:00 EDT.
  # A daily 02:30 local schedule does not exist on 2026-03-08 and advances to
  # 2026-03-09 02:30 EDT (06:30 UTC).
  after = datetime.datetime(2026, 3, 8, 5, 0, tzinfo=_UTC)
  nxt = cron.next_run_time(
      "30 2 * * *", tz_name="America/New_York", after=after
  )
  assert nxt == datetime.datetime(2026, 3, 9, 6, 30, tzinfo=_UTC)


def test_dst_fall_back_advances_monotonically_in_utc():
  """Advances strictly in UTC order across ambiguous DST fall-back hours."""
  # In America/New_York on 2026-11-01, 01:30 occurs at 05:30 UTC (EDT, fold=0)
  # and 06:30 UTC (EST, fold=1). Hourly *:30 must hit both in strict UTC order.
  start = datetime.datetime(2026, 11, 1, 5, 0, tzinfo=_UTC)
  runs = cron.preview_next_runs(
      "30 * * * *", tz_name="America/New_York", count=3, after=start
  )
  assert runs == [
      datetime.datetime(2026, 11, 1, 5, 30, tzinfo=_UTC),
      datetime.datetime(2026, 11, 1, 6, 30, tzinfo=_UTC),
      datetime.datetime(2026, 11, 1, 7, 30, tzinfo=_UTC),
  ]
  assert not cron.preview_next_runs("30 * * * *", tz_name="UTC", count=0)


def test_validate_timezone_accepts_iana_and_rejects_unknown():
  assert cron.validate_timezone(" America/Chicago ").key == "America/Chicago"
  with pytest.raises(ValueError, match="Unknown timezone"):
    cron.validate_timezone("Mars/Olympus_Mons")
  with pytest.raises(ValueError, match="Timezone is required"):
    cron.validate_timezone("   ")


def test_build_preset_cron_and_describe_cron_round_trip():
  """Formats preset cron strings and human-readable schedule descriptions."""
  hourly = cron.build_preset_cron("HOURLY", minute=15)
  assert hourly == "15 * * * *"
  assert cron.describe_cron(hourly, "UTC") == "Hourly at :15 (UTC)"

  daily = cron.build_preset_cron("DAILY", hour=14, minute=30)
  assert daily == "30 14 * * *"
  assert (
      cron.describe_cron(daily, "America/New_York")
      == "Daily at 14:30 (America/New_York)"
  )

  weekly = cron.build_preset_cron("WEEKLY", hour=9, minute=0, day_of_week=1)
  assert weekly == "0 9 * * 1"
  assert cron.describe_cron(weekly, "UTC") == "Weekly on Mon at 09:00 (UTC)"

  assert cron.describe_cron("*/10 * * * *", "UTC") == "Every 10 min (UTC)"
  assert (
      cron.describe_cron("0 9,17 * * 1-5", "UTC") == "Cron 0 9,17 * * 1-5 (UTC)"
  )
  assert cron.describe_cron("not a cron", "UTC") == "not a cron (UTC)"


def test_build_preset_cron_rejects_invalid_inputs():
  with pytest.raises(ValueError):
    cron.build_preset_cron("HOURLY", minute=99)
  with pytest.raises(ValueError):
    cron.build_preset_cron("DAILY", hour=25)
  with pytest.raises(ValueError):
    cron.build_preset_cron("WEEKLY", day_of_week=9)
  with pytest.raises(ValueError):
    cron.build_preset_cron("CUSTOM")
