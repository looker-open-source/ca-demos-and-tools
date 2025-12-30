# Getting Started with Create React App

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).

## Prerequisites

Before you begin, ensure you have the following installed:

* **Node.js** (LTS version recommended)
* **pnpm** (Package Manager)

If you do not have `pnpm` installed, you can enable it via corepack (if using Node v16.13+) or install it globally:

```bash
npm install -g pnpm

## Running the ca-api-adk-react-demo

In the project directory, you can run:

### `pnpm start` or

Dev: pnpm run start:dev (Loads .env.dev)

Remote: pnpm run start:remote (Loads .env.remote)

Prod: pnpm run start:prod (Loads .env.production)

Runs the app in the development mode.\
Open [http://localhost:5173] or (http://localhost:5174) to view it in the browser.

The page will reload if you make edits.\
You will also see any lint errors in the console.

## Running the ca-api-adk-streaming for Backend Connectivity

Inside ca-api-adk-streaming : adk web

## Local curl Testing Steps 

adk api_server
# server listens on http://localhost:8000 by default

(See “Running the Server” and “Local testing” in the ADK API Server docs. )

List available apps
curl -X GET http://localhost:8000/list-apps
# Expect: ["ca_api_agent","deployment"]

Create session
curl 'http://localhost:5173/api/apps/ca_api_agent/users/user/sessions' \
#Except: [{"id": "0693b331-xxxx-xxxx-xxxx-147aa9260e54","appName": "ca_api_agent","userId": "user","state": {},"events": [],"lastUpdateTime": 1766731642.315164}]

List available events in active session
curl 'http://localhost:5173/api/apps/ca_api_agent/users/user/sessions/60f2642d-1f11-42db-8059-a9a6c0e3501f' \
#Expect: {"id": "60f2642d-xxxx-xxxx-xxxx-a9a6c0e3501f","appName": "ca_api_agent","userId": "user","state": {},"events": [{"content": {"parts": [{"text": "can you read this file?"},{"inlineData": {"data": "QmCC","displayName": "qqwqw.png","mimeType": "image/png" }}],"role": "user"},"invocationId": "e-c9a8d818-xxxx-xxxx-xxxx-c84ccad3e098","author": "user","actions": {"stateDelta": {},"artifactDelta": {},"requestedAuthConfigs": {},"requestedToolConfirmations": {}},"id": "671938c4-xxxx-xxxx-xxxx-45f6a4923c98","timestamp": 1766731818.800519},{"content": {"parts": [{text": "I can read the image and here's the information:\n\n*   Invocation ID: e-fb559c85-5219-4023-9496-9deb49935de0\n*   invocation: 2718.85ms\n*   invoke\\_agent Conve...: 2696.95ms\n*   invoke\\_agent Co...: 2701.24ms\n*   call\\_llm: 2697.67ms"}],"role": "model"},"partial": false,"turnComplete": true,"invocationId": "e-c9a8d818-d8fb-4902-a97b-c84ccad3e098","author": "ConversationalAnalyticsAgent","actions": {"stateDelta": {},"artifactDelta": {},"requestedAuthConfigs": {},"requestedToolConfirmations": {}},"id": "3567c87e-b9f5-4c04-a663-6608586dd564","timestamp": 1766731822.927168}],"lastUpdateTime": 1766731822.927168}


List trace/ events

curl 'http://localhost:5173/api/debug/trace/session/60f2642d-1f11-42db-8059-a9a6c0e3501f' \-H 'Accept: text/event-stream, application/json, text/plain, */*' 
#Expect: [{ "name": "call_llm", "span_id": 121, "trace_id": 211, "start_time": 1766731818819841311, "end_time": 1766731822946958404, "attributes": { "gen_ai.system": "gcp.vertex.agent", "gen_ai.request.model": "gemini-2.0-flash-lite", "gcp.vertex.agent.invocation_id": "e-c9a8d818-xxxx-xxxx-xxxx-c84ccad3e098", "gcp.vertex.agent.session_id": "60f2642d-xxxx-xxxx-xxxx-a9a6c0e3501f", "gcp.vertex.agent.event_id": "5b6acbdd-xxxx-xxxx-xxxx-477948719346", "gcp.vertex.agent.llm_request": "{\"model\": \"gemini-2.0-flash-lite\", \"config\": {\"http_options\": {\"headers\": {\"x-goog-api-client\": \"google-adk/1.21.0 gl-python/3.13.7\", \"user-agent\": \"google-adk/1.21.0 gl-python/3.13.7\"}}, \"system_instruction\": \"You are a specialized data analysis assistant. Your primary purpose is to answer user questions about business analytics by retrieving data using your available tools.\\n\\n    ### Core Logic\\n    1.  **Analyze the User's Request:** First, determine the user's intent.\\n        * **Analytics Question:** Is the user asking for metrics, KPIs, statistics, trends, or information about the dataset (e.g., \\\"What were last week's sales?\\\", \\\"List all customer tables\\\")?\\n        * **General Conversation:** Is the user making small talk (e.g., \\\"Hello,\\\" \\\"How are you?\\\", \\\"Thank you\\\")?\\n\\n    2.  **Take Action:**\\n        * **If it IS an analytics question:** You MUST use the `nlq` tool (Looker query tool) to find the answer. You do not know this information and cannot make it up.\\n        * **If it is NOT an analytics question:** Respond directly as a helpful assistant. Do NOT use any tools.\\n\\n    ### Handling Tool Results (Crucial)\\n    When the tool returns information, it will be a JSON object. Your response to the user MUST follow these rules:\\n\\n    * **USE THIS:** Base your *entire* answer **exclusively** on the raw JSON data found within the `data` property of the tool's response.\\n    * **IGNORE THIS:** You MUST **ignore** all other properties, such as `summary` or `viz`, that may be present in the response.\\n    * **SYNTHESIZE:** Your job is to translate the raw `data` (which might be a list or dictionary) into a clear, human-readable, natural-language answer.\\n    * **DO NOT** output the raw JSON to the user.\\n\\nYou are an agent. Your internal name is \\\"ConversationalAnalyticsAgent\\\".\", \"tools\": [{\"function_declarations\": [{\"description\": \"\\nExecutes a query against the Looker analytics platform to retrieve specific data or metadata.\\n\\nUse this tool to answer any question that requires fetching, querying, or describing\\nanalytics data. This includes, but is not limited to, metrics, key performance\\nindicators (KPIs), statistics, trends, data points, or information about the\\ndataset structure (e.g., table schemas, column names, or available dimensions).\\n\\nThis tool translates the user's natural language question into a database\\nquery, runs it against the Looker instance, and returns the structured data results.\\n\\nArgs:\\n    question (str): natural language question\\n\", \"name\": \"tool_intercept\", \"parameters\": {\"properties\": {\"question\": {\"type\": \"STRING\"}}, \"required\": [\"question\"], \"type\": \"OBJECT\"}, \"response\": {\"type\": \"NULL\"}}]}], \"labels\": {\"adk_agent_name\": \"ConversationalAnalyticsAgent\"}, \"thinking_config\": {\"include_thoughts\": false, \"thinking_budget\": 0}}, \"contents\": [{\"parts\": [{\"text\": \"can you read this file?\"}], \"role\": \"user\"}]}", "gcp.vertex.agent.llm_response": "{\"model_version\":\"gemini-2.0-flash-lite\",\"content\":{\"parts\":[{\"text\":\"I can read the image and here's the information:\\n\\n*   Invocation ID: e-fb559c85-xxxx-xxx-xxx-9deb49935de0\\n*   invocation: 2718.85ms\\n*   invoke\\\\_agent Conve...: 2696.95ms\\n*   invoke\\\\_agent Co...: 2701.24ms\\n*   call\\\\_llm: 2697.67ms\"}],\"role\":\"model\"},\"finish_reason\":\"STOP\",\"usage_metadata\":{\"candidates_token_count\":120,\"candidates_tokens_details\":[{\"modality\":\"TEXT\",\"token_count\":120}],\"prompt_token_count\":2335,\"prompt_tokens_details\":[{\"modality\":\"IMAGE\",\"token_count\":1806},{\"modality\":\"TEXT\",\"token_count\":529}],\"total_token_count\":2455,\"traffic_type\":\"ON_DEMAND\"},\"avg_logprobs\":-0.04844109217325846}", "gen_ai.usage.input_tokens": 2335, "gen_ai.usage.output_tokens": 120, "gen_ai.response.finish_reasons": [ "stop" ] }, "parent_span_id": 1232 }]

Post Chat stream
curl 'http://localhost:5173/api/run_sse' \-H 'Accept: text/event-stream, application/json, text/plain, */*' \ --data-raw '{"appName":"ca_api_agent","userId":"user","sessionId":"60f2642d-1f11-42db-8059-a9a6c0e3501f","newMessage":{"role":"user","parts":[{"text":"hi"}]},"streaming":false,"stateDelta":null}'
#Expect: data: {"content":{"parts":[{"text":"Hello! How can I help you today?\n"}],"role":"model"},"partial":false,"turnComplete":true,"invocationId":"e-01a5bffd-xxxx-xxxx-xxxx-2819b82420b1","author":"ConversationalAnalyticsAgent","actions":{"stateDelta":{},"artifactDelta":{},"requestedAuthConfigs":{},"requestedToolConfirmations":{}},"id":"8df58f4e-xxxx-xxxx-xxxx-8f7630b51770","timestamp":1767005610.888791}



## Available Scripts

### `npm test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `npm run build`

Dev: pnpm run build:dev

Remote: pnpm run build:remote

Prod: pnpm run build:prod

pnpm run build

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

See the section about [deployment](https://facebook.github.io/create-react-app/docs/deployment) for more information.

### `npm run eject`

**Note: this is a one-way operation. Once you `eject`, you can’t go back!**

If you aren’t satisfied with the build tool and configuration choices, you can `eject` at any time. This command will remove the single build dependency from your project.

Instead, it will copy all the configuration files and the transitive dependencies (webpack, Babel, ESLint, etc) right into your project so you have full control over them. All of the commands except `eject` will still work, but they will point to the copied scripts so you can tweak them. At this point you’re on your own.

You don’t have to ever use `eject`. The curated feature set is suitable for small and middle deployments, and you shouldn’t feel obligated to use this feature. However we understand that this tool wouldn’t be useful if you couldn’t customize it when you are ready for it.

## Learn More

You can learn more in the [Create React App documentation](https://facebook.github.io/create-react-app/docs/getting-started).

To learn React, check out the [React documentation](https://reactjs.org/).
