# Conversational Analytics Demos and Tools

This repository houses a collection of demos and tools for the [Conversational Analytics API](https://cloud.google.com/gemini/docs/conversational-analytics-api/overview). The examples herein are designed to showcase the API's capabilities and provide practical integration patterns.

## 🚀 Overview

The Conversational Analytics API offers a natural language interface to programmatically query data from BigQuery, Looker, and Looker Studio. This allows for the seamless integration of powerful data conversation features into your applications.

## 📂 Projects

### [Conversational Analytics API Golden Demo](/ca-api-golden-demo/README.md)

This project provides various examples of how to integrate the Conversational Analytics API into web applications. The demos include:

- Direct Agent Querying: Shows how to directly query the Conversational Analytics agent from a web interface.
- Embedded Looker Dashboard Integration: Demonstrates how to use the API alongside an embedded Looker dashboard and share filter context.
- Multimodal Conversation with Gemini Live API: Illustrates an advanced use case, combining the Conversational Analytics API with the [Gemini Live API](https://cloud.google.com/vertex-ai/generative-ai/docs/live-api) for a multimodal conversational experience.

### [Streaming: Conversational Analytics API with ADK](/ca-api-adk-streaming/README.md)

This project provides an example of how to use streaming with the Conversational Analytics API and ADK. The demo includes:

- A root agent that uses a custom ADK Agent class, and connects to the CA API streaming responses back asynchronously.
- Showcases examples of how to save various json partials from the CA API (like the viz response, or raw data result) to Agent session temp storage to be accessed by subsequent agents in the same invocation.
- Documentation on how to deploy this agent to Agent Engine or run locally
- Examples of using this Agent in a multi agent system.

### [Conversational Analytics API with ADK React Demo](/ca-api-adk-react-demo/README.md)

A generic, configurable web frontend designed to interact with any ADK API Server instance.

- Built with React, TypeScript, and Material UI, this application provides a polished chat experience designed for CA API agents.
- Use this as a custom frontend to pair with the ADK examples in this repo or any ADK API server.

### [Prism](/ca-agent-ops-prism/README.md)

This project provides a comprehensive platform for monitoring and evaluating Gemini Data Analytics Agents. It offers a structured way to run test suites, capture traces, and evaluate agent performance via a dedicated diagnostic UI. Features include:

- Test Suite Management: Enables organizing and running complex evaluations for GDA agents.
- Trace Capture: Provides detailed visibility into agent execution steps and tool calls.
- Assertion Engine: Automates the validation of agent responses using structured assertions.
- Diagnostic UI: Offers high-density tables and comparison dashboards for deep-dive analysis.
