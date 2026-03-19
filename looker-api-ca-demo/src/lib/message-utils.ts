// Copyright 2026 Google LLC
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

/**
 * Formats a raw result name into a user-friendly header.
 * Example: "total_revenue_by_month" -> "Here's the query result for Total Revenue By Month"
 */
export function formatDataHeader(name: string): string {
  const formattedName = name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
  return `Here's the query result for ${formattedName}`;
}

/**
 * Extracts Looker query from a system message if present.
 */
export function getLookerQuery(systemMessage: any): any | null {
  // Try to get Looker query object
  if (systemMessage.data?.query?.looker) {
    return systemMessage.data?.query?.looker;
  }
  return null;
}

/**
 * Constructs a Looker Explore URL from the query metadata in a system message.
 * Follows the pattern: https://<instance>/explore/<model>/<explore>?fields=f1,f2&f[filter]=val&sorts=s1&limit=500
 */
export function getLookerExploreUrl(
  systemMessage: any,
  baseUrl?: string,
): string | null {
  const query = systemMessage.data?.query?.looker;
  if (!query || !query.model || !query.explore) {
    return null;
  }

  let instanceUrl = baseUrl || process.env.NEXT_PUBLIC_LOOKER_BASE_URL || "";
  if (!instanceUrl) return null;

  // Clean instance URL: remove API path if present (e.g., :19999/api/4.0)
  instanceUrl = instanceUrl.replace(/(:\d+)?\/api\/\d+\.\d+$/, "");

  const exploreName = query.explore;

  const params = new URLSearchParams();

  if (query.fields && Array.isArray(query.fields)) {
    params.append("fields", query.fields.join(","));
  }

  if (query.sorts && Array.isArray(query.sorts)) {
    params.append("sorts", query.sorts.join(","));
  }

  if (query.limit) {
    params.append("limit", String(query.limit));
  }

  if (query.pivots && Array.isArray(query.pivots)) {
    params.append("pivots", query.pivots.join(","));
  }

  // Construct the base Explore path
  let exploreUrl = `${instanceUrl}/explore/${query.model}/${exploreName}?${params.toString()}`;

  // Add filters: f[field_name]=expression
  if (Array.isArray(query.filters)) {
    query.filters.forEach((f: any) => {
      if (f.field && f.value !== undefined) {
        exploreUrl += `&f[${f.field}]=${encodeURIComponent(String(f.value))}`;
      }
    });
  } else if (query.filters && typeof query.filters === "object") {
    Object.entries(query.filters).forEach(([field, expr]) => {
      exploreUrl += `&f[${field}]=${encodeURIComponent(String(expr))}`;
    });
  }

  return exploreUrl;
}

/**
 * Parses a Looker message object into the format expected by the UI.
 * Handles both the standard Message object (with type/message fields)
 * and raw systemMessage/userMessage objects (used in streaming).
 */
export function parseLookerMessage(lm: any, lookerBaseUrl?: string) {
  // Determine type: explicitly provided or inferred from content
  let type = lm.type as "user" | "system";
  if (!type) {
    if (lm.systemMessage) type = "system";
    else if (lm.userMessage) type = "user";
  }

  let text = "";
  let payload = null;
  let isThought = false;
  let parts: string[] = [];

  // Extract the message body (lm.message if standard, or lm itself if raw)
  const msgBody = lm.message || lm;

  if (type === "user") {
    const userMsg = msgBody.userMessage || msgBody.user_message;
    if (typeof userMsg === "string") {
      text = userMsg;
    } else {
      text = userMsg?.text || "";
    }
  } else {
    const systemMessage = msgBody.systemMessage;
    if (systemMessage) {
      if (systemMessage.text) {
        parts = systemMessage.text.parts || [];
        text = parts.join("\n\n").replace(/\\n/g, "\n");
        isThought = systemMessage.text.textType === "THOUGHT";
      } else if (systemMessage.schema?.query) {
        // text = `${systemMessage.schema.query.question}`;
      } else if (
        systemMessage.data?.query?.looker ||
        systemMessage.data?.result?.data
      ) {
        const lookerQuery = getLookerQuery(systemMessage);
        const exploreUrl = getLookerExploreUrl(systemMessage, lookerBaseUrl);

        const resultData = systemMessage.data?.result?.data;
        const resultName = systemMessage.data?.result?.name || "Query Result";

        payload = {
          data: resultData,
          formattedHeader: formatDataHeader(resultName),
          query: lookerQuery,
          exploreUrl: exploreUrl,
        };
      } else if (systemMessage.chart?.result?.vegaConfig) {
        payload = {
          vegaConfig: systemMessage.chart.result.vegaConfig,
          isChart: true,
        };
      } else if (systemMessage.error) {
        text = systemMessage.error.text;
      }
    }
  }

  return { type, text, payload, isThought, parts };
}
