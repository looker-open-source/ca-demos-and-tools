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
import { Link } from "react-router-dom";
import "./styles/HomePage.css";

function HomePage() {
  return (
    <div className="homepage">
      <header className="page-header">
        <h1 className="main-heading">
          Explore data interactively using natural language
        </h1>
        <p className="sub-heading">
          This demo showcases the Conversational Analytics API, powered by
          Google Gemini. Choose an experience:
        </p>
      </header>

      <main className="content">
        {/* First row: 3 cards */}

        <div className="data-card">
          <img src="cymbalpets.png" alt="Cymbal Pets" className="card-image" />
          <h2 className="card-title">Cymbal Pets</h2>
          <p className="card-subtitle">Explore retail data</p>
          <p className="card-description">
            This Looker data source contains programmatically generated data
            about customers, orders, stores, and suppliers. Choose between
            classic chat (no theme) or a branded chat (Cymbal Pets theme).
          </p>
          <div className="card-actions">
            <Link to="/chat/cymbalpets" className="card-button">
              Try Classic
            </Link>
            <Link to="/chat/cymbalpets_branded" className="card-button">
              Try Branded
            </Link>
          </div>
        </div>

        <div className="data-card">
          <img
            src="cymbalpets.png"
            alt="Cymbal Pets Embed"
            className="card-image"
          />
          <h2 className="card-title">Cymbal Pets Embed</h2>
          <p className="card-subtitle">Looker embedded dashboards</p>
          <p className="card-description">
            Same dataset, now displayed alongside a Looker dashboard. The CA
            agent automatically understands your active dashboard filters, so
            your questions are answered in the right context.
          </p>
          <div className="card-actions">
            <Link
              to="/chat/cymbalpets_embed/business_pulse"
              className="card-button"
            >
              Business Pulse
            </Link>
            <Link
              to="/chat/cymbalpets_embed/supplier_metrics"
              className="card-button"
            >
              Supplier Metrics
            </Link>
          </div>
        </div>

        <div className="data-card">
          <img
            src="cymbalpets.png"
            alt="Cymbal Pets Multimodal"
            className="card-image"
          />
          <h2 className="card-title">Cymbal Pets Multimodal</h2>
          <p className="card-subtitle">Talk with your data!</p>
          <p className="card-description">
            Tired of typing? Try speaking to your data using the Gemini Live
            API. This agent lets you query the Cymbal Pets dataset using your
            voice. Choose between the Looker and BigQuery datasources. For
            Looker, the agent will decide which LookML explore to use. For
            BigQuery, the agent will decide which table(s) to select from.
          </p>
          <div className="card-actions">
            <Link to="/chat/multimodal?datasource=bq" className="card-button">
              BigQuery
            </Link>
            <Link
              to="/chat/multimodal?datasource=looker"
              className="card-button"
            >
              Looker
            </Link>
          </div>
        </div>

        {/* Second row: 3 cards */}

        <div className="data-card">
          <img src="openaq.png" alt="OpenAQ Data" className="card-image" />
          <h2 className="card-title">OpenAQ Data</h2>
          <p className="card-subtitle">Explore air quality data</p>
          <p className="card-description">
            This BigQuery public data source is an open-source project to
            surface air quality data from around the world. The data includes
            air quality measurements from 5490 locations in 47 countries.
          </p>
          <div className="card-actions">
            <Link to="/chat/openaq" className="card-button">
              Try it out
            </Link>
          </div>
        </div>

        <div className="data-card">
          <img src="thelook.png" alt="The Look Data" className="card-image" />
          <h2 className="card-title">The Look Events Data</h2>
          <p className="card-subtitle">Explore web events data</p>
          <p className="card-description">
            This BigQuery data source contains programmatically generated events
            for The Look fictitious e-commerce store. This contains user
            sessions, events, traffic source, and geographic location.
          </p>
          <div className="card-actions">
            <Link to="/chat/thelook" className="card-button">
              Try it out
            </Link>
          </div>
        </div>

        <div className="data-card">
          <img src="resources.png" alt="Resources" className="card-image" />
          <h2 className="card-title">Resources</h2>
          <p className="card-subtitle">Learn more about the API</p>
          <p className="card-description">
            The Conversational Analytics API is an automated analyst as a
            service that can answer data analytics questions by using GenAI
            building blocks and enabling developers to build custom experiences.
          </p>
          <div className="card-actions">
            <Link to="/resources" className="card-button">
              Learn more
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}

export default HomePage;
