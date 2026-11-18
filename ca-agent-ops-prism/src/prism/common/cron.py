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

"""Pure-Python 5-field cron parser and timezone-aware schedule calculator."""

import dataclasses
import datetime
import re
import zoneinfo

COMMON_TIMEZONES: tuple[str, ...] = (
    "UTC",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Phoenix",
    "America/Toronto",
    "America/Sao_Paulo",
    "Europe/London",
    "Europe/Berlin",
    "Europe/Paris",
    "Europe/Amsterdam",
    "Asia/Tokyo",
    "Asia/Singapore",
    "Asia/Kolkata",
    "Australia/Sydney",
)

_MONTH_NAMES: dict[str, int] = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_DOW_NAMES: dict[str, int] = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
}

_DOW_LABELS: dict[int, str] = {
    0: "Sun",
    1: "Mon",
    2: "Tue",
    3: "Wed",
    4: "Thu",
    5: "Fri",
    6: "Sat",
}

_MAX_DAYS_PER_MONTH: dict[int, int] = {
    1: 31,
    2: 29,
    3: 31,
    4: 30,
    5: 31,
    6: 30,
    7: 31,
    8: 31,
    9: 30,
    10: 31,
    11: 30,
    12: 31,
}

_TOKEN_RE = re.compile(r"^[A-Za-z0-9*,/\-]+$")


@dataclasses.dataclass(frozen=True)
class ParsedCron:
  """Parsed 5-field POSIX cron expression."""

  expression: str
  minutes: tuple[int, ...]
  hours: tuple[int, ...]
  days_of_month: tuple[int, ...]
  months: tuple[int, ...]
  days_of_week: tuple[int, ...]
  dom_restricted: bool
  dow_restricted: bool


def validate_timezone(tz_name: str) -> zoneinfo.ZoneInfo:
  """Validates and returns a ZoneInfo instance for an IANA timezone name."""
  cleaned = (tz_name or "").strip()
  if not cleaned:
    raise ValueError("Timezone is required.")
  try:
    return zoneinfo.ZoneInfo(cleaned)
  except (zoneinfo.ZoneInfoNotFoundError, ValueError, KeyError) as exc:
    raise ValueError(f"Unknown timezone: '{cleaned}'.") from exc


def _parse_atom(
    token: str,
    min_val: int,
    max_val: int,
    names: dict[str, int] | None,
    field_name: str,
) -> int:
  """Converts a single cron atom (integer or 3-letter alias) to int."""
  lowered = token.lower()
  if names and lowered in names:
    return names[lowered]
  if not token.isdigit():
    raise ValueError(f"Invalid value '{token}' in cron {field_name} field.")
  value = int(token)
  if value < min_val or value > max_val:
    raise ValueError(
        f"Value {value} out of range ({min_val}-{max_val}) in cron"
        f" {field_name} field."
    )
  return value


def _parse_field(
    raw_field: str,
    min_val: int,
    max_val: int,
    field_name: str,
    names: dict[str, int] | None = None,
    normalize_seven_to_zero: bool = False,
) -> tuple[tuple[int, ...], bool]:
  """Parses one cron field into a sorted tuple of ints and restriction flag.

  The flag follows standard cron: a field starting with "*" counts as
  unrestricted even with a step, so "*/2" in day_of_month is not a day rule of
  its own. That decides how the two day fields combine in _day_matches.

  Args:
    raw_field: The field text.
    min_val: The smallest value the field allows.
    max_val: The largest value the field allows.
    field_name: The field name used in error messages.
    names: Optional three-letter aliases, for months and weekdays.
    normalize_seven_to_zero: Whether 7 means Sunday, as in day_of_week.

  Returns:
    The matched values, sorted, and whether the field is restricted.

  Raises:
    ValueError: If the field is malformed or out of range.
  """
  if not raw_field or not _TOKEN_RE.match(raw_field):
    raise ValueError(f"Invalid cron {field_name} field: '{raw_field}'.")

  if raw_field == "*":
    end = 6 if normalize_seven_to_zero else max_val
    return tuple(range(min_val, end + 1)), False

  values: set[int] = set()
  for part in raw_field.split(","):
    if not part:
      raise ValueError(f"Empty list item in cron {field_name} field.")

    step = 1
    if "/" in part:
      pieces = part.split("/")
      if len(pieces) != 2 or not pieces[1].isdigit():
        raise ValueError(f"Invalid step '{part}' in cron {field_name} field.")
      base, step_str = pieces
      step = int(step_str)
      if step <= 0:
        raise ValueError(
            f"Step must be positive in cron {field_name} field: '{part}'."
        )
    else:
      base = part

    if base == "*":
      start = min_val
      end = 6 if normalize_seven_to_zero else max_val
    elif "-" in base:
      bounds = base.split("-")
      if len(bounds) != 2 or not bounds[0] or not bounds[1]:
        raise ValueError(f"Invalid range '{part}' in cron {field_name} field.")
      start = _parse_atom(bounds[0], min_val, max_val, names, field_name)
      end = _parse_atom(bounds[1], min_val, max_val, names, field_name)
      if normalize_seven_to_zero and start == 7 and end == 7:
        start = 0
        end = 0
      if start > end:
        raise ValueError(
            f"Range start exceeds end in cron {field_name} field: '{part}'."
        )
    else:
      atom = _parse_atom(base, min_val, max_val, names, field_name)
      if "/" in part:
        start = atom
        end = max_val
      else:
        start = atom
        end = atom

    for v in range(start, end + 1, step):
      values.add(0 if (normalize_seven_to_zero and v == 7) else v)

  if not values:
    raise ValueError(f"Cron {field_name} field matched no values.")
  return tuple(sorted(values)), not raw_field.startswith("*")


def parse_cron_expression(expression: str) -> ParsedCron:
  """Parses and validates a 5-field cron expression."""
  normalized = " ".join((expression or "").strip().split())
  if not normalized:
    raise ValueError("Cron expression is required.")

  fields = normalized.split(" ")
  if len(fields) != 5:
    raise ValueError(
        "Cron expression must have exactly 5 fields: minute hour"
        " day_of_month month day_of_week."
    )

  minutes, _ = _parse_field(fields[0], 0, 59, "minute")
  hours, _ = _parse_field(fields[1], 0, 23, "hour")
  days_of_month, dom_restricted = _parse_field(fields[2], 1, 31, "day_of_month")
  months, _ = _parse_field(fields[3], 1, 12, "month", names=_MONTH_NAMES)
  days_of_week, dow_restricted = _parse_field(
      fields[4],
      0,
      7,
      "day_of_week",
      names=_DOW_NAMES,
      normalize_seven_to_zero=True,
  )

  if dom_restricted and not dow_restricted:
    min_day = min(days_of_month)
    has_reachable_date = any(min_day <= _MAX_DAYS_PER_MONTH[m] for m in months)
    if not has_reachable_date:
      raise ValueError(
          f"Cron expression '{normalized}' never matches a valid calendar date."
      )

  return ParsedCron(
      expression=normalized,
      minutes=minutes,
      hours=hours,
      days_of_month=days_of_month,
      months=months,
      days_of_week=days_of_week,
      dom_restricted=dom_restricted,
      dow_restricted=dow_restricted,
  )


def validate_cron_expression(expression: str) -> str:
  """Validates a 5-field cron expression and returns its normalized form."""
  return parse_cron_expression(expression).expression


def build_preset_cron(
    cadence: str,
    hour: int = 9,
    minute: int = 0,
    day_of_week: int = 1,
) -> str:
  """Builds a normalized 5-field cron expression for preset UI cadences."""
  if minute < 0 or minute > 59:
    raise ValueError("Minute must be between 0 and 59.")
  if hour < 0 or hour > 23:
    raise ValueError("Hour must be between 0 and 23.")
  if day_of_week < 0 or day_of_week > 6:
    raise ValueError("Day of week must be between 0 (Sun) and 6 (Sat).")

  key = cadence.strip().upper()
  if key == "HOURLY":
    return f"{minute} * * * *"
  if key == "DAILY":
    return f"{minute} {hour} * * *"
  if key == "WEEKLY":
    return f"{minute} {hour} * * {day_of_week}"
  raise ValueError(f"Unsupported preset cadence: '{cadence}'.")


def _day_matches(parsed: ParsedCron, candidate: datetime.date) -> bool:
  """Applies standard cron day-of-month and day-of-week matching rules.

  Either day field matches when both are restricted. Otherwise both have to
  match, so "0 9 */2 * 1" runs on odd-numbered Mondays only. Treating "*/2" as
  restricted made it every odd day plus every Monday.

  Args:
    parsed: The parsed expression.
    candidate: The local calendar date to test.

  Returns:
    Whether the expression can fire on `candidate`.
  """
  cron_dow = (candidate.weekday() + 1) % 7
  dom_match = candidate.day in parsed.days_of_month
  dow_match = cron_dow in parsed.days_of_week

  if parsed.dom_restricted and parsed.dow_restricted:
    return dom_match or dow_match
  return dom_match and dow_match


def next_run_time(
    expression: str,
    tz_name: str = "UTC",
    after: datetime.datetime | None = None,
) -> datetime.datetime:
  """Computes the next UTC execution timestamp strictly after `after`.

  Evaluates wall-clock fields in `tz_name` (handling DST gaps and folds via
  round-trip validation) and returns a timezone-aware UTC datetime.

  Args:
    expression: Normalized or raw 5-field cron expression.
    tz_name: IANA timezone name in which cron fields are evaluated.
    after: Reference datetime; defaults to current UTC time when omitted.

  Returns:
    Next scheduled execution timestamp as a timezone-aware UTC datetime.
  """
  parsed = parse_cron_expression(expression)
  tz = validate_timezone(tz_name)

  if after is None:
    after_utc = datetime.datetime.now(datetime.timezone.utc)
  elif after.tzinfo is None:
    after_utc = after.replace(tzinfo=datetime.timezone.utc)
  else:
    after_utc = after.astimezone(datetime.timezone.utc)

  # Floor to the start of the current UTC minute so any future minute boundary
  # strictly greater than after_utc is considered.
  after_local = after_utc.astimezone(tz)
  # Start one day earlier than after_local.date() only if needed? Starting at
  # after_local.date() is safe even across fall-back because both folds of the
  # ambiguous local hour share the same local date.
  cur_date = after_local.date()
  limit_date = cur_date + datetime.timedelta(days=366 * 5)
  months_set = set(parsed.months)

  while cur_date <= limit_date:
    if cur_date.month not in months_set:
      if cur_date.month == 12:
        cur_date = datetime.date(cur_date.year + 1, 1, 1)
      else:
        cur_date = datetime.date(cur_date.year, cur_date.month + 1, 1)
      continue

    if not _day_matches(parsed, cur_date):
      cur_date += datetime.timedelta(days=1)
      continue

    day_candidates: list[datetime.datetime] = []
    for hour in parsed.hours:
      for minute in parsed.minutes:
        for fold in (0, 1):
          local_dt = datetime.datetime(
              cur_date.year,
              cur_date.month,
              cur_date.day,
              hour,
              minute,
              0,
              0,
              tzinfo=tz,
              fold=fold,
          )
          utc_dt = local_dt.astimezone(datetime.timezone.utc)
          if utc_dt <= after_utc:
            continue
          # Reject nonexistent local times during spring-forward DST gaps, and
          # deduplicate normal (non-ambiguous) minutes where fold=0 and fold=1
          # map to the same UTC instant.
          roundtrip = utc_dt.astimezone(tz)
          if (
              roundtrip.year == cur_date.year
              and roundtrip.month == cur_date.month
              and roundtrip.day == cur_date.day
              and roundtrip.hour == hour
              and roundtrip.minute == minute
          ):
            day_candidates.append(utc_dt)

    if day_candidates:
      return min(day_candidates)

    cur_date += datetime.timedelta(days=1)

  raise ValueError(
      f"No matching run time found within 5 years for '{parsed.expression}'."
  )


def preview_next_runs(
    expression: str,
    tz_name: str = "UTC",
    count: int = 3,
    after: datetime.datetime | None = None,
) -> list[datetime.datetime]:
  """Returns the next `count` UTC run times for UI schedule previews."""
  if count <= 0:
    return []
  results: list[datetime.datetime] = []
  cursor = after
  for _ in range(count):
    nxt = next_run_time(expression, tz_name=tz_name, after=cursor)
    results.append(nxt)
    cursor = nxt
  return results


def describe_cron(expression: str, tz_name: str = "UTC") -> str:
  """Returns a concise human-readable description of a cron expression."""
  try:
    normalized = validate_cron_expression(expression)
  except ValueError:
    return f"{expression} ({tz_name})"

  f_min, f_hour, f_dom, f_mon, f_dow = normalized.split(" ")
  if (
      f_min.startswith("*/")
      and f_min[2:].isdigit()
      and (f_hour, f_dom, f_mon, f_dow) == ("*", "*", "*", "*")
  ):
    return f"Every {int(f_min[2:])} min ({tz_name})"
  if f_min.isdigit() and (f_hour, f_dom, f_mon, f_dow) == ("*", "*", "*", "*"):
    return f"Hourly at :{int(f_min):02d} ({tz_name})"
  if (
      f_min.isdigit()
      and f_hour.isdigit()
      and (f_dom, f_mon, f_dow) == ("*", "*", "*")
  ):
    return f"Daily at {int(f_hour):02d}:{int(f_min):02d} ({tz_name})"
  if f_min.isdigit() and f_hour.isdigit() and (f_dom, f_mon) == ("*", "*"):
    parsed = parse_cron_expression(normalized)
    if len(parsed.days_of_week) == 1:
      dow_label = _DOW_LABELS[parsed.days_of_week[0]]
      return (
          f"Weekly on {dow_label} at"
          f" {int(f_hour):02d}:{int(f_min):02d} ({tz_name})"
      )
  return f"Cron {normalized} ({tz_name})"
