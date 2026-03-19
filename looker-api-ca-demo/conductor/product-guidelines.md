# Product Guidelines: Looker SDK & Gemini Data Analytics Demo

## Prose & Documentation Style
- **Concise & Technical**: Documentation, comments, and UI text should be direct, efficient, and technically accurate. Avoid unnecessary fluff or overly conversational language.
- **Reference-Centric**: Every piece of code and documentation should be written with the primary goal of being a clear, reusable reference for developers. Use comments to explain *why* something is done, not just *what* is being done.
- **Consistency**: Maintain consistent terminology between the Looker SDK, the Gemini Data Analytics API, and the reference application code.

## Branding & Visual Identity
- **High-Contrast Dark Mode**: The UI will employ a high-contrast dark theme. Use deep blacks or dark greys for backgrounds with vibrant, neon-like accents (e.g., electric blue, cyan, or bright purple) to highlight interactive elements and data points. This creates a modern, "AI-first" aesthetic.
- **AI-First Glow**: Use a high-contrast neon cyan pulse (`bg-cyan-400`) for initial loading overlays and pulsing visual indicators to signal AI activity.
- **Typography**: Use clean, modern sans-serif fonts for the primary UI, with monospace fonts reserved for code snippets, API keys, and raw data outputs to reinforce the technical nature of the demo.

## UX Principles
- **Responsiveness First**: The interface must feel fast and fluid. Use optimistic UI updates and clear loading states where latency is unavoidable (e.g., during AI query processing).
- **Streaming-First Interaction**: Prioritize streaming responses to provide immediate, incremental feedback to the user. This reduces perceived latency and makes the AI interaction feel more organic.
- **Simplicity & Focus**: Reduce cognitive load by maintaining simple, uncluttered layouts. Use height constraints and collapsible elements to manage information density. The primary focus should always be the conversational interface and the resulting data visualizations, with technical payloads isolated from the chat flow.
- **Transparency & Feedback**: Always provide clear feedback on system actions. When a conversational query is being processed, show the intermediate steps or the "thinking" process (e.g., "Interpreting query...", "Fetching Looker data...") to build user trust.
- **Seamless Transitions**: Agent switches and session resets should be instantaneous. Any active AI queries must be aborted silently to ensure the interface remains reactive and uncluttered by "cancelled" notifications during navigation.

## Accessibility
- **Minimal Priority**: While basic readability should be maintained, full WCAG compliance is not a primary requirement for this specific technical reference demo. Focus on the core functionality and aesthetic goals.
