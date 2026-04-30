"""Export a Prism test suite to the bulk-import YAML format.

Usage:
    uv run python scripts/export_suite.py <suite_id> [output.yaml]
    uv run python scripts/export_suite.py --list
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras
import yaml

DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://ben:mysecretpassword@localhost:5432/prism"
)

# DB stores Python enum NAMES; bulk-import YAML uses the enum VALUES.
# Mapping comes from src/prism/common/schemas/assertion.py::AssertionType.
TYPE_MAP = {
    "DATA_CHECK_ROW": "data-check-row",
    "DATA_CHECK_ROW_COUNT": "data-check-row-count",
    "QUERY_CONTAINS": "query-contains",
    "TEXT_CONTAINS": "text-contains",
    "CHART_CHECK_TYPE": "chart-check-type",
    "DURATION_MAX_MS": "duration-max-ms",
    "LATENCY_MAX_MS": "latency-max-ms",
    "LOOKER_QUERY_MATCH": "looker-query-match",
    "AI_JUDGE": "ai-judge",
}


def connect():
    return psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def list_suites() -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, (SELECT COUNT(*) FROM examples e "
            "WHERE e.test_suite_id = ts.id AND NOT e.is_archived) AS n "
            "FROM test_suites ts WHERE NOT is_archived ORDER BY id;"
        )
        for row in cur.fetchall():
            print(f"  {row['id']:>3}  {row['name']:<30}  {row['n']} cases")


def export_suite(suite_id: int) -> list[dict]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT name FROM test_suites WHERE id = %s;", (suite_id,))
        suite = cur.fetchone()
        if suite is None:
            sys.exit(f"Suite {suite_id} not found")

        cur.execute(
            "SELECT id, question FROM examples "
            "WHERE test_suite_id = %s AND NOT is_archived ORDER BY id;",
            (suite_id,),
        )
        examples = cur.fetchall()

        cur.execute(
            "SELECT example_id, type::text AS type, weight, params FROM assertions "
            "WHERE example_id = ANY(%s) AND NOT is_archived ORDER BY id;",
            ([e["id"] for e in examples],),
        )
        asserts_by_example: dict[int, list[dict]] = {}
        for a in cur.fetchall():
            entry: dict = {"type": TYPE_MAP.get(a["type"], a["type"])}
            if a["weight"] != 1.0:
                entry["weight"] = a["weight"]
            params = dict(a["params"] or {})
            # Strip internal wrapper fields not accepted by the bulk-import schema.
            params.pop("original_assertion_id", None)
            params.pop("reasoning", None)
            # looker-query-match keeps a `params:` key; other types inline `value`/`columns`.
            for k, v in params.items():
                entry[k] = v
            asserts_by_example.setdefault(a["example_id"], []).append(entry)

        return [
            {"question": e["question"], "assertions": asserts_by_example.get(e["id"], [])}
            for e in examples
        ]


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] == "--list":
        list_suites()
        return

    suite_id = int(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    data = export_suite(suite_id)
    yaml_str = yaml.safe_dump(data, sort_keys=False, default_flow_style=False, width=120)

    if output_path:
        output_path.write_text(yaml_str)
        print(f"Wrote {len(data)} cases to {output_path}")
    else:
        print(yaml_str)


if __name__ == "__main__":
    main()
