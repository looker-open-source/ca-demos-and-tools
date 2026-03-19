# Tech Stack: Looker SDK & Gemini Data Analytics Demo

## Core Technologies
- **Language**: **TypeScript** - Used across the entire stack for type safety and robust integration.
- **Framework**: **Next.js (React)** - Utilizing **React Server Components (RSC)** for server-side logic and API interactions.
- **SDK**: **Looker SDK (26.4+)** - Official `@looker/sdk-node` package used for all backend interactions with the Looker API.
- **Authentication**: **Looker OAuth 2.0 (PKCE)** - Utilizing `@looker/sdk-rtl` for secure, browser-based user authentication, with **proactive token refresh** via a custom backend proxy endpoint (`/api/token/refresh`).
- **State Management**: **Zustand** - For centralized management of message history, authentication state (token monitoring), and UI state.
- **Styling**: **Tailwind CSS** - Used for rapid development, featuring a high-contrast dark theme with neon-cyan accents for an "AI-First" aesthetic.
- **Visualization**: **Recharts** & **Vega-Lite** - For rendering dynamic charts and tables from Looker data.
- **Markdown**: **react-markdown** - For rendering AI responses with rich formatting.

## API Integration Strategy
- **Official SDK Integration**: The application utilizes the **Looker SDK (release 26.4+)** for all Conversational Analytics interactions.
- **Dual-Mode Auth**: Supports both server-side Service Account credentials and client-side User OAuth tokens, proxied via a stateless backend.
- **Persistence**: Conversations and their metadata are managed via the Looker SDK methods, with local state managed by Zustand for immediate UI responsiveness.
- **Caching**: Agent data is cached locally after initial discovery to optimize switching and suppress redundant loading states.
- **Streaming**: SDK streaming capabilities are leveraged to provide real-time updates for chat responses.

## Infrastructure & Environment
- **Environment Variables**: Managed natively by Next.js via `.env` files. External libraries like `dotenv` are not required.
- **Logging**: Implementing a lightweight logging utility for tracking API interactions and debugging stream parsing issues.
- **Storage**: Initial implementation will use in-memory state (Zustand), with potential for local storage (JSONL format, named as `<timestamp>_<conversation_id>.jsonl`) for development.

## Build & Development
- **Package Manager**: **npm** (default).
- **Testing**: **Vitest** - Used for unit and component testing (replaces Jest for better ESM support).
