import React from "react";
import "./styles/Resources.css";

function Resources() {
  return (
    <div className="resources-page">
      <h1>Resources</h1>

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
      </section>

      <section className="resource-section">
        <h2>PRD</h2>
        <p>
          Read the Product Requirements Document:{" "}
          <a
            href="http://go/data-qna-agent-prd"
            target="_blank"
            rel="noopener noreferrer"
          >
            go/data-qna-agent-prd
          </a>
        </p>
      </section>

      <section className="resource-section">
        <h2>Documentation</h2>
        <p>
          Explore the API documentation:{" "}
          <a
            href="https://cloud.google.com/looker/docs/dataqna-home"
            target="_blank"
            rel="noopener noreferrer"
          >
            https://cloud.google.com/looker/docs/dataqna-home
          </a>
        </p>
        <p>
          Release Notes:{" "}
          <a
            href="https://cloud.google.com/looker/docs/dataqna-api-release-notes"
            target="_blank"
            rel="noopener noreferrer"
          >
            https://cloud.google.com/looker/docs/dataqna-api-release-notes
          </a>
        </p>
      </section>
    </div>
  );
}

export default Resources;
