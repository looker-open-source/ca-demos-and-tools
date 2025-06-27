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

import React from "react";
import "./styles/Resources.css";

function Resources() {
  return (
    <div className="resources-page">
      <h1>Resources</h1>

      <section className="resource-section">
        <h2>Demo Contact / Support</h2>
        <p>
          For questions or issues with this demo, contact{" "}
          <a href="mailto:cloud-bi-opm-demos@google.com">
            cloud-bi-opm-demos@google.com
          </a>
          . If you want to customize and expand on this demo, you can deploy
          this in your environment by following the steps here:{" "}
          <a
            href="http://go/ca-api-golden-demo-devkit"
            target="_blank"
            rel="noopener noreferrer"
          >
            go/ca-api-golden-demo-devkit
          </a>
        </p>
      </section>

      <section className="resource-section">
        <h2>API Overview</h2>
        <p>
          Learn more about the Conversational Analytics API:{" "}
          <a
            href="http://go/looker-conversational-analytics"
            target="_blank"
            rel="noopener noreferrer"
          >
            go/looker-conversational-analytics
          </a>
        </p>
        <p>
          Conversational Analytics API FAQ:{" "}
          <a
            href="http://go/ca-api-faq"
            target="_blank"
            rel="noopener noreferrer"
          >
            go/ca-api-faq
          </a>
        </p>
      </section>

      <section className="resource-section">
        <h2>Documentation</h2>
        <p>
          Explore the API (v2) documentation:{" "}
          <a
            href="https://cloud.google.com/gemini/docs/conversational-analytics-api/overview"
            target="_blank"
            rel="noopener noreferrer"
          >
            https://cloud.google.com/gemini/docs/conversational-analytics-api/overview
          </a>
        </p>
        <p>
          API Reference:{" "}
          <a
            href="https://cloud.google.com/gemini/docs/conversational-analytics-api/reference/rest"
            target="_blank"
            rel="noopener noreferrer"
          >
            https://cloud.google.com/gemini/docs/conversational-analytics-api/reference/rest
          </a>
        </p>
      </section>

      <section className="resource-section">
        <h2>Questions / Comments</h2>
        <p>
          CA API chat channel:{" "}
          <a
            href="http://go/cortado-dogfood-chat"
            target="_blank"
            rel="noopener noreferrer"
          >
            go/cortado-dogfood-chat
          </a>
        </p>

        <p>
          YAQS:{" "}
          <a
            href="http://go/ca-api-yaqs"
            target="_blank"
            rel="noopener noreferrer"
          >
            go/ca-api-yaqs
          </a>
        </p>
      </section>
    </div>
  );
}

export default Resources;
