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

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  formatDataHeader,
  getLookerQuery,
  getLookerExploreUrl,
} from "./message-utils";

describe("message-utils", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    vi.resetModules();
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  describe("formatDataHeader", () => {
    it("should format underscores to spaces and capitalize each word", () => {
      expect(formatDataHeader("total_revenue_by_month")).toBe(
        "Here's the query result for Total Revenue By Month",
      );
    });

    it("should handle single word", () => {
      expect(formatDataHeader("revenue")).toBe(
        "Here's the query result for Revenue",
      );
    });
  });

  describe("getLookerQuery", () => {
    it("should extract query object from systemMessage.data.query.looker", () => {
      const mockQuery = { model: "test", explore: "test" };
      const systemMessage = { data: { query: { looker: mockQuery } } };
      expect(getLookerQuery(systemMessage)).toEqual(mockQuery);
    });

    it("should return null if not present", () => {
      const systemMessage = { data: { result: {} } };
      expect(getLookerQuery(systemMessage)).toBe(null);
    });
  });

  describe("getLookerExploreUrl", () => {
    it("should construct a valid Explore URL using 'explore' field", () => {
      process.env.NEXT_PUBLIC_LOOKER_BASE_URL = "https://demo.looker.com:19999/api/4.0";

      const systemMessage = {
        data: {
          query: {
            looker: {
              model: "thelook",
              explore: "orders_explore",
              fields: ["orders.id"],
            },
          },
        },
      };

      const url = getLookerExploreUrl(systemMessage);
      expect(url).toContain(
        "https://demo.looker.com/explore/thelook/orders_explore",
      );
      expect(url).toContain("fields=orders.id");
    });

    it("should construct a valid Explore URL with complex query metadata", () => {
      process.env.NEXT_PUBLIC_LOOKER_BASE_URL = "https://demo.looker.com:19999/api/4.0";

      const systemMessage = {
        data: {
          query: {
            looker: {
              model: "thelook",
              explore: "orders",
              fields: ["orders.id", "orders.status"],
              filters: { "orders.created_date": "7 days" },
              sorts: ["orders.created_date desc"],
              limit: 500,
            },
          },
        },
      };

      const url = getLookerExploreUrl(systemMessage);
      expect(url).toContain("https://demo.looker.com/explore/thelook/orders");
      expect(url).toContain("fields=orders.id%2Corders.status");
      expect(url).toContain("limit=500");
      expect(url).toContain("sorts=orders.created_date+desc");
      expect(url).toContain("f[orders.created_date]=7%20days");
    });

    it("should return null if essential query info is missing", () => {
      const systemMessage = {
        data: { query: { looker: { model: "thelook" } } },
      };
      expect(getLookerExploreUrl(systemMessage)).toBe(null);
    });
  });
});
