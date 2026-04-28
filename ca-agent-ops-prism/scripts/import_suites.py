"""Import YAML test suite definitions into Prism.

Each YAML file becomes one Prism suite named after the file stem. Existing
questions in that suite are fully replaced — assertions included — so the
file is always the source of truth.

Usage:
    uv run python scripts/import_suites.py <yaml_file_or_dir>
    uv run python scripts/import_suites.py <yaml_file_or_dir> --dry-run
    uv run python scripts/import_suites.py --list
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

import psycopg2
import psycopg2.extras
import yaml

DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://ben:mysecretpassword@localhost:5432/prism"
)

# YAML assertion type values → PostgreSQL assertiontype enum labels.
# Inverse of the mapping in export_suite.py.
TYPE_MAP: dict[str, str] = {
    "data-check-row": "DATA_CHECK_ROW",
    "data-check-row-count": "DATA_CHECK_ROW_COUNT",
    "query-contains": "QUERY_CONTAINS",
    "text-contains": "TEXT_CONTAINS",
    "chart-check-type": "CHART_CHECK_TYPE",
    "duration-max-ms": "DURATION_MAX_MS",
    "latency-max-ms": "LATENCY_MAX_MS",
    "looker-query-match": "LOOKER_QUERY_MATCH",
    "ai-judge": "AI_JUDGE",
}


def connect() -> psycopg2.extensions.connection:
    return psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def cmd_list() -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, "
            "(SELECT COUNT(*) FROM examples e "
            " WHERE e.test_suite_id = ts.id AND NOT e.is_archived) AS n "
            "FROM test_suites ts WHERE NOT is_archived ORDER BY id;"
        )
        rows = cur.fetchall()
    if not rows:
        print("No suites found.")
        return
    for row in rows:
        print(f"  {row['id']:>3}  {row['name']:<40}  {row['n']} questions")


def _import_file(cur, path: Path, dry_run: bool) -> tuple[str, int, str]:
    """Import one YAML file. Returns (suite_name, question_count, action)."""
    with open(path) as f:
        data = yaml.safe_load(f)

    if not data:
        return path.stem, 0, "skipped (empty)"

    # Support both the legacy bare-list format and the new {label, cases} mapping.
    if isinstance(data, list):
        suite_name = path.stem
        cases = data
    else:
        suite_name = data.get("label") or path.stem
        cases = data.get("cases") or []

    if not cases:
        return suite_name, 0, "skipped (no cases)"

    cur.execute(
        "SELECT id FROM test_suites WHERE name = %s AND NOT is_archived;",
        (suite_name,),
    )
    row = cur.fetchone()

    if row:
        suite_id = row["id"]
        action = "updated"
    else:
        suite_id = None
        action = "created"

    if dry_run:
        return suite_name, len(cases), f"dry-run ({action})"

    if suite_id is None:
        cur.execute(
            "INSERT INTO test_suites (name, tags, is_archived) VALUES (%s, %s, false) RETURNING id;",
            (suite_name, json.dumps({})),
        )
        suite_id = cur.fetchone()["id"]
    else:
        # Full replace: delete assertions then examples for this suite.
        cur.execute(
            "DELETE FROM assertions WHERE example_id IN "
            "(SELECT id FROM examples WHERE test_suite_id = %s);",
            (suite_id,),
        )
        cur.execute(
            "DELETE FROM examples WHERE test_suite_id = %s;",
            (suite_id,),
        )

    for case in cases:
        cur.execute(
            "INSERT INTO examples (test_suite_id, logical_id, question, is_archived) "
            "VALUES (%s, %s, %s, false) RETURNING id;",
            (suite_id, str(uuid.uuid4()), case["question"]),
        )
        example_id = cur.fetchone()["id"]

        for a in case.get("asserts", []):
            db_type = TYPE_MAP.get(a["type"])
            if db_type is None:
                print(
                    f"  WARNING: unknown assertion type '{a['type']}' in "
                    f"{path.name} — skipping",
                    file=sys.stderr,
                )
                continue
            weight = a.get("weight", 1.0)
            params = {k: v for k, v in a.items() if k not in ("type", "weight")}
            cur.execute(
                "INSERT INTO assertions (example_id, type, weight, params, is_archived) "
                "VALUES (%s, %s::assertiontype, %s, %s, false);",
                (example_id, db_type, weight, json.dumps(params)),
            )

    return suite_name, len(cases), action


def cmd_import(path: Path, dry_run: bool) -> None:
    yaml_files = [path] if path.is_file() else sorted(path.rglob("*.yaml"))

    if not yaml_files:
        sys.exit(f"No YAML files found at {path}")

    with connect() as conn:
        with conn.cursor() as cur:
            for yaml_file in yaml_files:
                try:
                    name, count, action = _import_file(cur, yaml_file, dry_run)
                    print(f"  {action}: {name} ({count} questions)")
                except Exception as exc:  # pylint: disable=broad-except
                    print(f"  ERROR: {yaml_file.name}: {exc}", file=sys.stderr)
                    raise
        if not dry_run:
            conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import YAML test suites into Prism (full replace per file)."
    )
    parser.add_argument("path", nargs="?", help="YAML file or directory of YAML files")
    parser.add_argument("--list", action="store_true", help="List existing suites and exit")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing to DB")
    args = parser.parse_args()

    if args.list or args.path is None:
        cmd_list()
        return

    cmd_import(Path(args.path), dry_run=args.dry_run)


if __name__ == "__main__":
    main()
