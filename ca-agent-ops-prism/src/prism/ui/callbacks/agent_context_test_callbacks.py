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

"""Callbacks for the Agent Context Prototype Page."""

import json

import dash
from dash import ALL
from dash import callback
from dash import Input
from dash import Output
from dash import State
from prism.ui.pages.context_prototype import render_bq_table_row
from prism.ui.pages.context_prototype import render_context_summary
from prism.ui.pages.context_prototype import render_example_row
from prism.ui.pages.context_prototype import render_glossary_row
from prism.ui.pages.context_prototype import render_golden_row
from prism.ui.pages.context_prototype import render_looker_explore_row
from prism.ui.pages.context_prototype import render_relation_row
from prism.ui.pages.context_prototype_ids import ContextPrototypeIds as Ids


def _get_triggered_index(triggered_id: str) -> int:
  """Extracts the index from a pattern-matching ID string."""
  try:
    return json.loads(triggered_id.split(".")[0])["index"]
  except (ValueError, KeyError):
    return -1


@callback(
    Output("section-bq-ds", "style"),
    Output("section-looker-ds", "style"),
    Input(Ids.SELECT_DS_TYPE, "value"),
)
def toggle_ds_sections(ds_type: str) -> tuple[dict, dict]:
  """Toggles visibility of datasource sections based on selected type."""
  if ds_type == "bq":
    return {"display": "block"}, {"display": "none"}
  return {"display": "none"}, {"display": "block"}


@callback(
    Output(Ids.BQ_TABLE_LIST, "children"),
    Input(Ids.BTN_ADD_BQ_TABLE, "n_clicks"),
    Input(Ids.bq_table_delete(ALL), "n_clicks"),
    State(Ids.bq_table_row(ALL), "id"),
)
def update_bq_tables(
    add_clicks: int | None,
    delete_clicks: list[int | None],
    existing: list[dict],
) -> list:
  """Updates the list of BigQuery tables."""
  del add_clicks, delete_clicks
  ctx = dash.callback_context
  tid = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
  if not tid and not existing:
    return [render_bq_table_row(0)]
  indices = [rid["index"] for rid in existing]
  if "btn-add-bq-table" in tid:
    indices.append(max(indices) + 1 if indices else 0)
  elif "bq-table-delete" in tid:
    idx = _get_triggered_index(tid)
    indices = [i for i in indices if i != idx]
  return [render_bq_table_row(i) for i in indices]


@callback(
    Output(Ids.LOOKER_EXPLORE_LIST, "children"),
    Input(Ids.BTN_ADD_LOOKER_EXPLORE, "n_clicks"),
    Input(Ids.looker_explore_delete(ALL), "n_clicks"),
    State(Ids.looker_explore_row(ALL), "id"),
)
def update_looker_explores(
    add_clicks: int | None,
    delete_clicks: list[int | None],
    existing: list[dict],
) -> list:
  """Updates the list of Looker explores."""
  del add_clicks, delete_clicks
  ctx = dash.callback_context
  tid = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
  if not tid and not existing:
    return [render_looker_explore_row(0)]
  indices = [rid["index"] for rid in existing]
  if "btn-add-looker-explore" in tid:
    indices.append(max(indices) + 1 if indices else 0)
  elif "looker-explore-delete" in tid:
    idx = _get_triggered_index(tid)
    indices = [i for i in indices if i != idx]
  return [render_looker_explore_row(i) for i in indices]


@callback(
    Output(Ids.EXAMPLE_LIST, "children"),
    Input(Ids.BTN_ADD_EXAMPLE, "n_clicks"),
    Input(Ids.example_delete(ALL), "n_clicks"),
    State(Ids.example_row(ALL), "id"),
)
def update_example_list(
    add_clicks: int | None,
    delete_clicks: list[int | None],
    existing: list[dict],
) -> list:
  """Updates the list of SQL examples."""
  del add_clicks, delete_clicks
  ctx = dash.callback_context
  tid = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
  if not tid and not existing:
    return [render_example_row(0)]
  indices = [rid["index"] for rid in existing]
  if "btn-add-example" in tid:
    indices.append(max(indices) + 1 if indices else 0)
  elif "example-delete" in tid:
    idx = _get_triggered_index(tid)
    indices = [i for i in indices if i != idx]
  return [render_example_row(i) for i in indices]


@callback(
    Output(Ids.GOLDEN_LIST, "children"),
    Input(Ids.BTN_ADD_GOLDEN, "n_clicks"),
    Input(Ids.golden_delete(ALL), "n_clicks"),
    State(Ids.golden_row(ALL), "id"),
)
def update_golden_list(
    add_clicks: int | None,
    delete_clicks: list[int | None],
    existing: list[dict],
) -> list:
  """Updates the list of golden queries."""
  del add_clicks, delete_clicks
  ctx = dash.callback_context
  tid = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
  if not tid and not existing:
    return [render_golden_row(0)]
  indices = [rid["index"] for rid in existing]
  if "btn-add-golden" in tid:
    indices.append(max(indices) + 1 if indices else 0)
  elif "golden-delete" in tid:
    idx = _get_triggered_index(tid)
    indices = [i for i in indices if i != idx]
  return [render_golden_row(i) for i in indices]


@callback(
    Output(Ids.GLOSSARY_LIST, "children"),
    Input(Ids.BTN_ADD_GLOSSARY, "n_clicks"),
    Input(Ids.glossary_delete(ALL), "n_clicks"),
    State(Ids.glossary_row(ALL), "id"),
)
def update_glossary_list(
    add_clicks: int | None,
    delete_clicks: list[int | None],
    existing: list[dict],
) -> list:
  """Updates the list of glossary terms."""
  del add_clicks, delete_clicks
  ctx = dash.callback_context
  tid = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
  if not tid and not existing:
    return [render_glossary_row(0)]
  indices = [rid["index"] for rid in existing]
  if "btn-add-glossary" in tid:
    indices.append(max(indices) + 1 if indices else 0)
  elif "glossary-delete" in tid:
    idx = _get_triggered_index(tid)
    indices = [i for i in indices if i != idx]
  return [render_glossary_row(i) for i in indices]


@callback(
    Output(Ids.RELATION_LIST, "children"),
    Input(Ids.BTN_ADD_RELATION, "n_clicks"),
    Input(Ids.relation_delete(ALL), "n_clicks"),
    State(Ids.relation_row(ALL), "id"),
)
def update_relation_list(
    add_clicks: int | None,
    delete_clicks: list[int | None],
    existing: list[dict],
) -> list:
  """Updates the list of schema relationships."""
  del add_clicks, delete_clicks
  ctx = dash.callback_context
  tid = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
  if not tid and not existing:
    return []
  indices = [rid["index"] for rid in existing]
  if "btn-add-relation" in tid:
    indices.append(max(indices) + 1 if indices else 0)
  elif "relation-delete" in tid:
    idx = _get_triggered_index(tid)
    indices = [i for i in indices if i != idx]
  return [render_relation_row(i) for i in indices]


@callback(
    Output(Ids.OUTPUT_JSON, "children"),
    Output(Ids.SUMMARY_CARD, "children"),
    Input(Ids.INSTRUCTION, "value"),
    Input(Ids.SELECT_DS_TYPE, "value"),
    Input(Ids.bq_table_input(ALL), "value"),
    Input(Ids.LOOKER_URI, "value"),
    Input(Ids.looker_explore_model(ALL), "value"),
    Input(Ids.looker_explore_name(ALL), "value"),
    Input(Ids.example_question(ALL), "value"),
    Input(Ids.example_sql(ALL), "value"),
    Input(Ids.golden_questions(ALL), "value"),
    Input(Ids.golden_model(ALL), "value"),
    Input(Ids.golden_explore(ALL), "value"),
    Input(Ids.glossary_term(ALL), "value"),
    Input(Ids.glossary_desc(ALL), "value"),
    Input(Ids.relation_left_table(ALL), "value"),
    Input(Ids.relation_left_cols(ALL), "value"),
    Input(Ids.relation_right_table(ALL), "value"),
    Input(Ids.relation_right_cols(ALL), "value"),
    Input(Ids.SWITCH_PYTHON, "checked"),
    Input(Ids.INPUT_MAX_BYTES, "value"),
)
def update_json_preview(
    instruction: str | None,
    ds_type: str,
    bq_tables: list[str | None],
    looker_uri: str | None,
    exp_models: list[str | None],
    exp_names: list[str | None],
    ex_qs: list[str | None],
    ex_sqls: list[str | None],
    g_qs: list[str | None],
    g_models: list[str | None],
    g_explores: list[str | None],
    g_terms: list[str | None],
    g_descs: list[str | None],
    r_left_ts: list[str | None],
    r_left_cs: list[str | None],
    r_right_ts: list[str | None],
    r_right_cs: list[str | None],
    python: bool,
    max_bytes: int | None,
) -> tuple[str, dash.development.base_component.Component]:
  """Updates both the JSON preview and the elegant summary card."""
  # 1. Datasources
  ds_refs = {}
  if ds_type == "bq":
    table_refs = []
    for t in bq_tables:
      if t:
        parts = t.split(".")
        if len(parts) == 3:
          table_refs.append({
              "project_id": parts[0],
              "dataset_id": parts[1],
              "table_id": parts[2],
          })
    ds_refs = {"bq": {"table_references": table_refs}}
  else:
    explores = []
    for m, e in zip(exp_models, exp_names):
      if m and e:
        explores.append({
            "looker_instance_uri": looker_uri,
            "lookml_model": m,
            "explore": e,
        })
    ds_refs = {"looker": {"explore_references": explores}}

  # 2. Examples
  examples = []
  for q, s in zip(ex_qs, ex_sqls):
    if q or s:
      examples.append({"natural_language_question": q, "sql_query": s})

  # 3. Golden
  goldens = []
  for qs, m, e in zip(g_qs, g_models, g_explores):
    if qs or m or e:
      questions = [q.strip() for q in qs.split("\n") if q.strip()] if qs else []
      goldens.append({
          "natural_language_questions": questions,
          "looker_query": {"model": m, "explore": e},
      })

  # 4. Glossary
  glossary = []
  for t, d in zip(g_terms, g_descs):
    if t or d:
      glossary.append({"display_name": t, "description": d})

  # 5. Relationships
  relations = []
  for lt, lc, rt, rc in zip(r_left_ts, r_left_cs, r_right_ts, r_right_cs):
    if lt and lc and rt and rc:
      relations.append({
          "left_schema_paths": {"table_fqn": lt, "paths": lc.split(",")},
          "right_schema_paths": {"table_fqn": rt, "paths": rc.split(",")},
      })

  data = {
      "system_instruction": instruction,
      "datasource_references": ds_refs,
      "example_queries": examples,
      "looker_golden_queries": goldens,
      "glossary_terms": glossary,
      "schema_relationships": relations,
      "options": {
          "analysis": {"python": {"enabled": python}},
          "datasource": {"big_query_max_billed_bytes": max_bytes},
      },
  }

  return json.dumps(data, indent=2), render_context_summary(data)
