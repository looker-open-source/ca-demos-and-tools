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
          Google Gemini. Choose a dataset to explore:
        </p>
      </header>

      <main className="content">
        <Link to="/chat/openaq" className="data-card">
          <img src="openaq.png" alt="OpenAQ Data" className="card-image" />
          <h2 className="card-title">OpenAQ Data</h2>
          <p className="card-subtitle">Explore air quality data</p>
          <p className="card-description">
            This BigQuery public data source is an open-source project to
            surface air quality data from around the world. The data includes
            air quality measurements from 5490 locations in 47 countries.
          </p>
          <button className="card-button">Try it out</button>
        </Link>

        <Link to="/chat/thelook" className="data-card">
          <img src="thelook.png" alt="The Look Data" className="card-image" />
          <h2 className="card-title">The Look Events Data</h2>
          <p className="card-subtitle">Explore web events data</p>
          <p className="card-description">
            This BigQuery data source contains programatically generated events
            for The Look fictitious e-commerce store. This contains user
            sessions, events, traffic source, and geographic location.
          </p>
          <button className="card-button">Try it out</button>
        </Link>

        <Link to="/chat/cymbalpets" className="data-card">
          <img src="cymbalpets.png" alt="Cymbal Pets" className="card-image" />
          <h2 className="card-title">Cymbal Pets Classic</h2>
          <p className="card-subtitle">Explore retail data</p>
          <p className="card-description">
            This Looker data source contains programatically generated data
            about customers, orders, stores, and suppliers. Use the top menu to
            view this data in an embedded or multimodal context.
          </p>
          <button className="card-button">Try it out</button>
        </Link>

        <Link to="/resources" className="data-card">
          <img src="resources.png" alt="Resources" className="card-image" />
          <h2 className="card-title">Resources</h2>
          <p className="card-subtitle">Learn more about the API</p>
          <p className="card-description">
            The Conversational Analytics API is an automated analyst as a
            service that can answer data analytics questions by using GenAI
            building blocks and enabling developers to build custom experiences.
          </p>
          <button className="card-button">Learn more</button>
        </Link>
      </main>
    </div>
  );
}

export default HomePage;
