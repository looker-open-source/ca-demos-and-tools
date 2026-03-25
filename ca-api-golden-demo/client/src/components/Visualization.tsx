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

import React, { useEffect, useRef } from "react";
import embed from "vega-embed";

interface VisualizationProps {
  spec: any;
}

/**
 * Recursively converts a gRPC-style Protobuf Struct/Value into a plain JS object.
 */
function fromProto(obj: any): any {
  if (obj === null || typeof obj !== "object") return obj;

  // Handle arrays
  if (Array.isArray(obj)) return obj.map(fromProto);

  // Handle Protobuf Value
  if (obj.kind && typeof obj.kind === "string" && obj.hasOwnProperty(obj.kind)) {
    if (obj.kind === "structValue") return fromProto(obj.structValue);
    if (obj.kind === "listValue") return fromProto(obj.listValue?.values || []);
    if (obj.kind === "nullValue") return null;
    return fromProto(obj[obj.kind]);
  }

  // Handle Protobuf Struct
  if (obj.fields && typeof obj.fields === "object") {
    const res: any = {};
    for (const key in obj.fields) {
      res[key] = fromProto(obj.fields[key]);
    }
    return res;
  }

  // Regular object
  const res: any = {};
  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      res[key] = fromProto(obj[key]);
    }
  }
  return res;
}

const Visualization: React.FC<VisualizationProps> = ({ spec }) => {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (spec && chartRef.current) {
      // The SDK returns gRPC-style objects. We unwrap them here.
      const plainSpec = fromProto(spec);
      const updatedSpec = { ...plainSpec, width: "container" };
      embed(chartRef.current, updatedSpec).catch((error) =>
        console.error("Vega embed error:", error)
      );
    }
  }, [spec]);

  return (
    <div className="vega-chart-wrapper">
      <div ref={chartRef} className="vega-chart-inner" />
    </div>
  );
};

export default Visualization;
