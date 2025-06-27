// Copyright 2025 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import yaml from "js-yaml";
import { format } from "sql-formatter";
import { datasource } from "utils/MultimodalLiveClient";

interface TableReferences {
  projectId: string;
  datasetId: string;
  tableId: string;
}

interface LookerQueryFilter {
  field: string;
  value: string;
}

interface LookerQuery {
  model: string;
  explore: string;
  fields?: string[];
  filters?: LookerQueryFilter[];
  sorts?: string[];
  limit?: string;
}

function areAllValuesEmpty(obj: any) {
  return Object.values(obj).every((value) => {
    return value === "" || value === null || value === false;
  });
}

export function transformDataQnAResponse(dataqnaResponse: any[]) {
  let questionReceived = null;
  let schemaResultDatasources = null;
  let derivedQuestion = "";
  let generatedSQL = "";
  let generatedLookerQuery = "";
  let data = null;
  let name = "";
  let chartQueryInstructions = "";
  let vegaConfig = null;
  let text = "";
  let errorMessage = "";
  let ignoreMessage = false;

  // Advanced Python Analysis only fields
  let analysisQuestion = "";
  let analysisProgressCsv = null;
  let analysisProgressVegaChart = null;
  let analysisProgressText = null;
  let analysisProgressCode = null;

  try {
    for (const item of dataqnaResponse) {
      if (item && item.systemMessage) {
        const { systemMessage } = item;
        if (
          systemMessage.schema &&
          systemMessage.schema.query &&
          systemMessage.schema.query.question
        ) {
          questionReceived = true;
        }
        if (
          systemMessage.schema &&
          systemMessage.schema.result &&
          systemMessage.schema.result.datasources &&
          systemMessage.schema.result.datasources.length > 0
        ) {
          schemaResultDatasources = true;
        }

        if (systemMessage.data) {
          if (systemMessage.data.query) {
            derivedQuestion = `Writing a query for the question '${systemMessage.data.query.question}'`;
          }
          if (systemMessage.data.generatedSql) {
            generatedSQL = format(systemMessage.data.generatedSql);
          }
          if (systemMessage.data.generatedLookerQuery) {
            generatedLookerQuery = systemMessage.data.generatedLookerQuery;
          }
          if (systemMessage.data.result && systemMessage.data.result.data) {
            data = systemMessage.data.result.data;
          }
          if (systemMessage.data.result && systemMessage.data.result.name) {
            name = systemMessage.data.result.name;
          }
        }

        // Advanced Python Analysis only fields
        if (systemMessage.analysis) {
          if (systemMessage.analysis.query) {
            analysisQuestion = `Writing a query for the question '${systemMessage.analysis.query.question}'`;
          }
          if (systemMessage.analysis.progressEvent) {
            analysisProgressCsv =
              systemMessage.analysis.progressEvent.resultCsvData;
            analysisProgressVegaChart =
              systemMessage.analysis.progressEvent.resultVegaChartJson;
            analysisProgressText =
              systemMessage.analysis.progressEvent.resultNaturalLanguage;
            analysisProgressCode = systemMessage.analysis.progressEvent.code;
          }
        }

        if (systemMessage.chart) {
          if (
            systemMessage.chart.query &&
            systemMessage.chart.query.instructions
          ) {
            chartQueryInstructions = systemMessage.chart.query.instructions;
          }
          if (
            systemMessage.chart.result &&
            systemMessage.chart.result.vegaConfig
          ) {
            vegaConfig = systemMessage.chart.result.vegaConfig;
          }
        }

        if (systemMessage.text && systemMessage.text.parts) {
          text += systemMessage.text.parts.join(" ");
        }

        if (systemMessage.error) {
          errorMessage = systemMessage.error.text;
        }
      }

      if (item && item.error) {
        errorMessage = item.error.message;
      }
    }

    if (
      // Purposefully not including: questionReceived, schemaResultDatasources, chartQueryInstructions.
      // These are all temporary status that are not rendered permanently
      areAllValuesEmpty({
        derivedQuestion,
        generatedSQL,
        generatedLookerQuery,
        data,
        name,
        analysisQuestion,
        analysisProgressCsv,
        analysisProgressVegaChart,
        analysisProgressText,
        analysisProgressCode,
        vegaConfig,
        text,
        errorMessage,
      })
    ) {
      ignoreMessage = true;
    }

    return {
      questionReceived,
      schemaResultDatasources,
      derivedQuestion,
      generatedSQL,
      generatedLookerQuery,
      data,
      name,
      analysisQuestion,
      analysisProgressCsv,
      analysisProgressVegaChart,
      analysisProgressText,
      analysisProgressCode,
      chartQueryInstructions,
      vegaConfig,
      text,
      errorMessage,
      ignoreMessage,
    };
  } catch (error) {
    console.error("Error transforming DataQnA response:", error);
    return null;
  }
}

export function constructLookerUrl(query: LookerQuery): string {
  const encodedModel = encodeURIComponent(query.model);
  const encodedExplore = encodeURIComponent(query.explore);
  let urlPath = `${process.env.REACT_APP_LOOKER_INSTANCE_URI}/explore/${encodedModel}/${encodedExplore}`;

  const queryParams: string[] = [];

  // Fields are joined by a comma. Each individual field name is URI encoded e.g., fields=users.id,orders.created_date
  if (query.fields && query.fields.length > 0) {
    const fieldsString = query.fields
      .map((field) => encodeURIComponent(field))
      .join(",");
    queryParams.push(`fields=${fieldsString}`);
  }

  // Filters use the format f[field_name]=value. The field_name part within brackets is literal e.g., f[users.country]=USA&f[orders.status]=complete
  if (query.filters && query.filters.length > 0) {
    query.filters.forEach((filter) => {
      const filterKey = `f[${filter.field}]`;
      const filterValue = encodeURIComponent(filter.value);
      queryParams.push(`${filterKey}=${filterValue}`);
    });
  }

  // Sorts are joined by a comma e.g., sorts=orders.created_date%20desc,users.last_name%20asc
  if (query.sorts && query.sorts.length > 0) {
    const sortsString = query.sorts
      .map((sort) => encodeURIComponent(sort))
      .join(",");
    queryParams.push(`sorts=${sortsString}`);
  }

  // Handle 'limit' parameter
  if (
    query.limit !== undefined &&
    query.limit !== null &&
    query.limit.toString().length > 0
  ) {
    queryParams.push(`limit=${encodeURIComponent(query.limit)}`);
  }

  if (queryParams.length > 0) {
    return `${urlPath}?${queryParams.join("&")}`;
  }

  return urlPath;
}

export function parseFilters(event: any) {
  const rawUrl = event.page.url;
  const queryIndex = rawUrl.indexOf("?");
  if (queryIndex === -1) return {}; // no query string

  const query = rawUrl.slice(queryIndex + 1);
  const pairs = query.split("&");
  const result: Record<string, string> = {};

  for (let pair of pairs) {
    const [rawKey, rawValue = ""] = pair.split("=");
    if (!rawKey || rawValue === "") continue; // skip empty keys or values

    // decode plus→space and percent‐escapes
    const keyDecoded = decodeURIComponent(rawKey.replace(/\+/g, " "));
    const valueDecoded = decodeURIComponent(rawValue.replace(/\+/g, " "));

    // skip embed controls
    if (["embed_domain", "allow_login_screen", "sdk"].includes(keyDecoded)) {
      continue;
    }

    // if it's a tile_id filter, strip off the prefix up to the first dot
    let cleanKey = keyDecoded;
    if (cleanKey.startsWith("tile_id") && cleanKey.includes(".")) {
      cleanKey = cleanKey.substring(cleanKey.indexOf(".") + 1);
    }

    result[cleanKey] = valueDecoded;
  }

  return result;
}

// For Cymbal Pets Embed
// Update dashboard filters to system instructions
export function updateSystemInstructions(
  fullSystemInstructionYAML: any,
  currentFilters: string
) {
  const fullSystemInstructionJSON: any = yaml.load(fullSystemInstructionYAML);
  const filteredSystemInstructionJSON = fullSystemInstructionJSON.filter(
    (obj: any) => !obj.hasOwnProperty("current_filters")
  );
  filteredSystemInstructionJSON.push({ current_filters: currentFilters });

  console.log({ filteredSystemInstructionJSON });

  return yaml.dump(filteredSystemInstructionJSON);
}

// For Multimodal Live
// Remove any references to views/tables not required for current query
export function trimSystemInstructions(
  fullSystemInstructionYAML: any,
  datasourceReferences: any,
  datasource: datasource
) {
  const fullSystemInstructionJSON: any = yaml.load(fullSystemInstructionYAML);
  let dynamicSystemInstructionJSON: any = {};

  if (datasource === "bq") {
    dynamicSystemInstructionJSON = trimSystemInstructionsBQ(
      fullSystemInstructionJSON,
      datasourceReferences
    );
  } else if (datasource === "looker") {
    dynamicSystemInstructionJSON = trimSystemInstructionsLooker(
      fullSystemInstructionJSON,
      datasourceReferences
    );
  } else {
    console.error("Invalid datasource supplied", datasource);
    dynamicSystemInstructionJSON = fullSystemInstructionJSON;
  }

  console.log({ dynamicSystemInstructionJSON });
  return yaml.dump(dynamicSystemInstructionJSON);
}

// For BigQuery - remove unused tables, glossaries, core_relationships, and additional_instructions
function trimSystemInstructionsBQ(
  fullSystemInstructionJSON: any,
  datasourceReferences: any
) {
  const dynamicSystemInstructionJSON: any = {};
  const allowedTables = datasourceReferences.map(
    (ref: TableReferences) => `${ref.projectId}.${ref.datasetId}.${ref.tableId}`
  );

  // 1. Copy system_description
  try {
    dynamicSystemInstructionJSON.system_description =
      fullSystemInstructionJSON.system_description;
  } catch (err) {
    console.error("Error copying system_description:", err);
    dynamicSystemInstructionJSON.system_description = "";
  }

  // 2. Filter the tables array
  try {
    if (Array.isArray(fullSystemInstructionJSON.tables)) {
      dynamicSystemInstructionJSON.tables =
        fullSystemInstructionJSON.tables.filter((tableObj: any) => {
          // Check if tableObj.table exists and has a name property.
          if (tableObj && tableObj.table && tableObj.table.name) {
            const tableName = tableObj.table.name;
            return allowedTables.includes(tableName);
          } else {
            console.warn(
              "Skipping a table entry due to missing table.name",
              tableObj
            );
            return false;
          }
        });
    } else {
      console.warn("tables is not an array");
      dynamicSystemInstructionJSON.tables = fullSystemInstructionJSON.tables;
    }
  } catch (err) {
    console.error("Error filtering tables:", err);
    dynamicSystemInstructionJSON.tables = fullSystemInstructionJSON.tables;
  }

  // 3. Filter glossaries by table property
  try {
    if (Array.isArray(fullSystemInstructionJSON.glossaries)) {
      dynamicSystemInstructionJSON.glossaries =
        fullSystemInstructionJSON.glossaries.filter((glosObj: any) => {
          // Check if glossary exists and has a table property
          if (glosObj && glosObj.glossary && glosObj.glossary.table) {
            const tableName = glosObj.glossary.table;
            return allowedTables.includes(tableName);
          } else {
            console.warn(
              "Skipping glossary entry due to missing table property",
              glosObj
            );
            return false;
          }
        });
    } else {
      console.warn("glossaries is not an array");
      dynamicSystemInstructionJSON.glossaries =
        fullSystemInstructionJSON.glossaries;
    }
  } catch (err) {
    console.error("Error filtering glossaries:", err);
    dynamicSystemInstructionJSON.glossaries =
      fullSystemInstructionJSON.glossaries;
  }

  // 4. Filter core_relationships: only keep entity if at least one table is allowed.
  try {
    if (Array.isArray(fullSystemInstructionJSON.core_relationships)) {
      dynamicSystemInstructionJSON.core_relationships =
        fullSystemInstructionJSON.core_relationships.filter(
          (entityObj: any) => {
            if (
              entityObj &&
              entityObj.entity &&
              Array.isArray(entityObj.entity.tables)
            ) {
              const filteredTables = entityObj.entity.tables.filter(
                (tableName: string) => allowedTables.includes(tableName)
              );
              return filteredTables.length > 0;
            } else {
              console.warn(
                "Skipping core_relationships entry due to missing entity.tables",
                entityObj
              );
              return false;
            }
          }
        );
    } else {
      console.warn("core_relationships is not an array");
      dynamicSystemInstructionJSON.core_relationships =
        fullSystemInstructionJSON.core_relationships;
    }
  } catch (err) {
    console.error("Error filtering core_relationships:", err);
    dynamicSystemInstructionJSON.core_relationships =
      fullSystemInstructionJSON.core_relationships;
  }

  // 5. Filter additional_instructions: if instruction has a "table" property, check it.
  try {
    if (Array.isArray(fullSystemInstructionJSON.additional_instructions)) {
      dynamicSystemInstructionJSON.additional_instructions =
        fullSystemInstructionJSON.additional_instructions.filter(
          (instrObj: any) => {
            if (instrObj.table) {
              return allowedTables.includes(instrObj.table);
            }
            return true;
          }
        );
    } else {
      console.warn("additional_instructions is not an array");
      dynamicSystemInstructionJSON.additional_instructions =
        fullSystemInstructionJSON.additional_instructions;
    }
  } catch (err) {
    console.error("Error filtering additional_instructions:", err);
    dynamicSystemInstructionJSON.additional_instructions =
      fullSystemInstructionJSON.additional_instructions;
  }

  return dynamicSystemInstructionJSON;
}

// For Looker - remove unused explores, golden queries, glossaries, and additional_instructions
function trimSystemInstructionsLooker(
  fullSystemInstructionJSON: any,
  datasourceReferences: any
) {
  const dynamicJSON: any = {};
  const allowedExplore = datasourceReferences.explore;

  // 1. Copy system_description.
  try {
    dynamicJSON.system_description =
      fullSystemInstructionJSON.system_description || "";
  } catch (err) {
    console.error("Error copying system_description:", err);
    dynamicJSON.system_description = "";
  }

  // 2. Filter golden_queries: keep only those with a matching explore_name.
  try {
    if (Array.isArray(fullSystemInstructionJSON.golden_queries)) {
      dynamicJSON.golden_queries =
        fullSystemInstructionJSON.golden_queries.filter((gqObj: any) => {
          if (
            gqObj &&
            gqObj.golden_query &&
            typeof gqObj.golden_query.explore_name === "string"
          ) {
            return gqObj.golden_query.explore_name === allowedExplore;
          } else {
            console.warn(
              "Skipping golden_query entry due to missing golden_query.explore_name",
              gqObj
            );
            return false;
          }
        });
    } else {
      console.warn("golden_queries is not an array");
      dynamicJSON.golden_queries = fullSystemInstructionJSON.golden_queries;
    }
  } catch (err) {
    console.error("Error filtering golden_queries:", err);
    dynamicJSON.golden_queries = fullSystemInstructionJSON.golden_queries;
  }

  // 3. Filter glossaries: if a glossary has explore_name, keep only if it matches.
  try {
    if (Array.isArray(fullSystemInstructionJSON.glossaries)) {
      dynamicJSON.glossaries = fullSystemInstructionJSON.glossaries.filter(
        (glosObj: any) => {
          if (glosObj && glosObj.glossary) {
            if (glosObj.glossary.explore_name) {
              if (typeof glosObj.glossary.explore_name === "string") {
                return glosObj.glossary.explore_name === allowedExplore;
              } else {
                console.warn("Glossary explore_name is not a string", glosObj);
                return false;
              }
            } else {
              return true;
            }
          }
          console.warn(
            "Skipping glossary entry due to missing glossary property",
            glosObj
          );
          return false;
        }
      );
    } else {
      console.warn("glossaries is not an array");
      dynamicJSON.glossaries = fullSystemInstructionJSON.glossaries;
    }
  } catch (err) {
    console.error("Error filtering glossaries:", err);
    dynamicJSON.glossaries = fullSystemInstructionJSON.glossaries;
  }

  // 4. Filter additional_instructions based on explore_name.
  try {
    if (Array.isArray(fullSystemInstructionJSON.additional_instructions)) {
      dynamicJSON.additional_instructions =
        fullSystemInstructionJSON.additional_instructions.filter(
          (instrObj: any) => {
            if (instrObj && instrObj.explore_name) {
              if (typeof instrObj.explore_name === "string") {
                return instrObj.explore_name === allowedExplore;
              } else {
                console.warn(
                  "Instruction explore_name is not a string",
                  instrObj
                );
                return false;
              }
            }
            return true;
          }
        );
    } else {
      console.warn("additional_instructions is not an array");
      dynamicJSON.additional_instructions =
        fullSystemInstructionJSON.additional_instructions;
    }
  } catch (err) {
    console.error("Error filtering additional_instructions:", err);
    dynamicJSON.additional_instructions =
      fullSystemInstructionJSON.additional_instructions;
  }

  return dynamicJSON;
}
