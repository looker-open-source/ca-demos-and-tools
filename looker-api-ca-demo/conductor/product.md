# Initial Concept\n\nA demo reference app to showcase new APIs for the Looker SDK integration with Google Conversational Analytics API (Gemini Data Analytics API) with backend server and frontend. Typescript Node and React for simplicity.

# Product Guide: Looker SDK & Gemini Data Analytics Demo

## Target Audience
- **Developers**: The primary audience is software engineers and architects looking for clear, well-documented examples of how to integrate the Looker SDK with the Google Conversational Analytics (Gemini Data Analytics) API.

## Core Goals
- **Reference Code**: Provide high-quality, idiomatic TypeScript code for both backend (Node.js) and frontend (React) that serves as a definitive reference for this integration.
- **Feature Showcase**: Demonstrate the powerful combination of Looker's data governance and Gemini's conversational capabilities.
- **Boilerplate Template**: Offer a functional starting point (boilerplate) that developers can adapt for their own Looker and Gemini-powered applications.

## Key Features
- **Conversational UI**: A natural language interface allowing users to query their data as if they were talking to an expert.
- **User-Based Authentication (OAuth)**: Support for individual user login via Looker OAuth 2.0 (PKCE). Includes **automatic token refresh** logic via a backend proxy to ensure continuous sessions without manual re-authentication.
- **Data Visualization**: Dynamic rendering of Looker-sourced data within a React-based frontend, providing immediate visual feedback to conversational queries.
- **Payload & Statement Management**: Robust local management of API payloads and conversation state, demonstrating how to handle complex interactions and send refined context back to the Gemini Data Analytics API.
- **Multi-Agent Support**: Flexible agent discovery, selection, and local caching to ensure instantaneous transitions between conversational contexts. Includes **descriptive metadata tooltips** (purpose, sources, and capabilities) for immediate visibility during selection.
- **Enhanced Stream Control**: Real-time feedback and control, including the ability to stop active AI queries.
- **Conversation Discovery & Management**: Easy discovery of past sessions via a persistent dropdown, with support for renaming and permanent deletion.
- **Transparent Reasoning**: Visibility into the AI's "thought" process through collapsible reasoning sections.
- **Refined Workspace UX**: Optimized layout for data exploration, including fixed-height constraints, collapsible components, and intelligent empty-state handling to manage complex visualizations and large data tables.
- **Noise-Free Chat**: Intelligent message filtering that suppresses redundant or technical payloads from the chat history, keeping the focus on the conversation while moving detailed data to the Insight Workspace.
- **AI-First UX**: Visually engaging loading states (AI-First Glow) and streamlined transitions that maintain focus on the conversational flow.

## User Experience & Design
- **Clean & Modern**: A minimalist design language that prioritizes the conversational flow while ensuring data visualizations are clear, accessible, and high-impact. The interface will focus on reducing noise and highlighting the "magic" of AI-driven data exploration.

## API Reference
The implementation focuses on routing queries through the **Looker API** via the **Looker SDK (26.4+)**. This ensures that all conversational interactions respect Looker's centralized governance and security model.

### Mapping GCP to Looker API
The mapping between GCP Conversational Analytics concepts and Looker is handled by the SDK:
- **Looker 'user_message'** maps to GCP 'query'.
- **Looker 'conversation_id'** maps to GCP 'conversation'.
- Response structures are parsed and rendered as rich UI components.
