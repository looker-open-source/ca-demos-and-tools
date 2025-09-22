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

import express, { Request, Response } from "express";
import path from "path";
import expressWs from "express-ws";
import WebSocket from "ws";
import { getAccessToken } from "./authHelper";
import * as config from "./config";
import { askQuestion } from "./GeminiDataAnalytics";
import { orchestrateQuestion } from "./GeminiOrchestrator";
import logger from "./logger";

const server = express();
const wsServer = expressWs(server);
const app = wsServer.app;
const PORT = process.env.PORT || 8081;

const decoder = new TextDecoder("utf-8");

const startServer = async () => {
  // Pre-fetch looker API keys once at startup
  const lookerClientId = await config.getEnvOrSecret("LOOKER_CLIENT_ID");
  const lookerClientSecret = await config.getEnvOrSecret(
    "LOOKER_CLIENT_SECRET"
  );

  // Retrieve the Looker instance URI from the environment
  const lookerInstanceUri = process.env.LOOKER_INSTANCE_URI;
  if (!lookerInstanceUri) {
    throw new Error("LOOKER_INSTANCE_URI environment variable is not set.");
  }

  // Update the appDatasourceReferences for the looker datasources
  Object.keys(config.appDatasourceReferences).forEach((key) => {
    if (key.startsWith("cymbalpets")) {
      const dsConfig = config.appDatasourceReferences[key];
      if (
        dsConfig.datasourceReferences &&
        "looker" in dsConfig.datasourceReferences
      ) {
        const lookerConfig = dsConfig.datasourceReferences.looker;
        lookerConfig.credentials.oauth.secret.client_id = lookerClientId;
        lookerConfig.credentials.oauth.secret.client_secret =
          lookerClientSecret;
        lookerConfig.explore_references.looker_instance_uri = lookerInstanceUri;
      }
    }
  });
  Object.keys(config.multimodalLookerDatasourceReferences).forEach((key) => {
    const dsConfig = config.multimodalLookerDatasourceReferences[key];
    dsConfig.looker.credentials.oauth.secret.client_id = lookerClientId;
    dsConfig.looker.credentials.oauth.secret.client_secret = lookerClientSecret;
    dsConfig.looker.explore_references.looker_instance_uri = lookerInstanceUri;
  });

  /******************************************************************************************
   *                           MULTIMODAL LIVE API WEBSOCKET                                *
   *----------------------------------------------------------------------------------------*
   * This section handles the Multimodal Live API WebSocket connections. It manages the     *
   * client connection, forwards setup and data messages to/from the multimodal API, and    *
   * logs connection events.                                                                *
   *                                                                                        *
   * Example tasks:                                                                         *
   *   - Receiving and processing setup messages from clients                               *
   *   - Forwarding client messages to the remote Multimodal API                            *
   *   - Relaying responses from the multimodal API back to the client                      *
   ******************************************************************************************/

  app.ws("/ws/multimodal", (clientWs, req) => {
    logger.info("Client connected to /ws/multimodal");
    const bidiUrl = config.loadBidiUrl();
    let setupMessageFromClient: any = null;

    // Listen once for the setup message from the client
    clientWs.once("message", (msg: string) => {
      try {
        const message = JSON.parse(msg);
        if (message.setup) {
          logger.info("[Multimodal Live Client] Received setup message");
          setupMessageFromClient = message;
        } else {
          logger.warn(
            "[Multimodal Live Client] Expected setup message, got:",
            message
          );
        }
      } catch (err) {
        logger.error(
          "[Multimodal Live Client] Error parsing setup, message:",
          err
        );
      }
    });

    // Get OAuth access token first then create the connection
    getAccessToken().then(({ token }) => {
      const apiWs = new WebSocket(bidiUrl, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      // When the API connection opens, send start chat params
      apiWs.on("open", () => {
        logger.info(
          "[Multimodal Live API] Connected to BidiGenerateContent endpoint"
        );
        if (setupMessageFromClient) {
          apiWs.send(JSON.stringify(setupMessageFromClient));
          logger.info("[Multimodal Live API] Forwarded setup message");
        } else {
          logger.warn(
            "[Multimodal Live API] No setup message received from client before Multimodal Live API connection opened."
          );
        }
      });

      // Forward messages received from the client to the API
      clientWs.on("message", (msg: string) => {
        // logger.info(`[Multimodal Live Client] Received from client: ${msg}`);
        if (apiWs.readyState === WebSocket.OPEN) {
          apiWs.send(msg);
        }
      });

      // Forward messages received from the API back to the client
      apiWs.on("message", (data: WebSocket.Data) => {
        const decodedText = decoder.decode(data as Buffer);
        logger.info(`[Multimodal Live API] ${decodedText.slice(0, 150)}`);
        // const message = JSON.parse(decodedText.trim());
        // logger.info(`Received from API: ${JSON.stringify(message)}`);
        if (clientWs.readyState === clientWs.OPEN) {
          clientWs.send(data);
        }
      });

      // On client close, close the API connection as well
      clientWs.on("close", () => {
        logger.info("[Multimodal Live Client] WebSocket closed");
        if (apiWs.readyState === WebSocket.OPEN) {
          apiWs.close();
        }
      });

      // On API close, close client connection
      apiWs.on("close", (code, reason) => {
        logger.info(
          `[Multimodal Live API] WebSocket closed with code ${code}, reason: ${reason}`
        );
        if (clientWs.readyState === clientWs.OPEN) {
          clientWs.close();
        }
      });

      // Log any errors
      clientWs.on("error", (err) => {
        logger.error("[Multimodal Live Client] WebSocket error:", err);
      });

      apiWs.on("error", (err) => {
        logger.error("[Multimodal Live API] WebSocket error:", err);
      });
    });
  });

  //  route for system instructions that the frontend can call once on page load
  app.get("/api/system-instructions", async (req, res) => {
    const { agentPageId } = req.query;
    if (!agentPageId || typeof agentPageId !== "string") {
      return res.status(400).json({ error: "pageId is required" });
    }
    try {
      const systemInstruction = await config.getSystemInstruction(agentPageId);
      res.json({ systemInstruction });
    } catch (err) {
      logger.error("Error fetching system instruction:", err);
      res.status(500).json({ error: "Failed to load system instructions" });
    }
  });

  //  route for orchestration API call
  app.post(
    "/api/orchestrate",
    express.json({ limit: "20mb" }),
    async (req: Request, res: Response) => {
      res.setHeader("Cache-Control", "no-cache");
      res.setHeader("Connection", "keep-alive");
      res.setHeader("Content-Encoding", "none");
      res.setHeader("Content-Type", "application/json; charset=utf-8");
      res.setHeader("Transfer-Encoding", "chunked");
      res.setHeader("X-Accel-Buffering", "no");

      try {
        const { projectId, token } = await getAccessToken();

        if (!req.body.messages) {
          return res.status(400).json({ error: "Messages is required" });
        }
        if (!token) {
          return res.status(400).json({ error: "Error getting token" });
        }

        req.body.projectId = projectId;
        req.body.token = token;

        await orchestrateQuestion(req, res);
      } catch (err) {
        logger.error("Error in /api/orchestrate:", err);
        res.status(500).json({ error: "An error occurred" });
      }
    }
  );

  //  route for cortado API call
  app.post(
    "/api/data",
    express.json({ limit: "20mb" }),
    async (req: Request, res: Response) => {
      res.setHeader("Cache-Control", "no-cache");
      res.setHeader("Connection", "keep-alive");
      res.setHeader("Content-Encoding", "none");
      res.setHeader("Content-Type", "application/json; charset=utf-8");
      res.setHeader("Transfer-Encoding", "chunked");
      res.setHeader("X-Accel-Buffering", "no");

      try {
        const { projectId, token } = await getAccessToken();
        const pageId = req.query.pageId as string;

        if (!pageId) {
          return res.status(400).json({ error: "PageId is required" });
        }
        if (!req.body.messages) {
          return res.status(400).json({ error: "Messages is required" });
        }
        if (!token) {
          return res.status(400).json({ error: "Error getting token" });
        }

        req.body.projectId = projectId;
        req.body.token = token;

        // All pages will use app config except for multimodal
        if (pageId !== "multimodal") {
          const datasourceConfig = config.loadDatasource(pageId);
          req.body.datasourceReferences = datasourceConfig.datasourceReferences;
        }
        // Looker explore is dynamically set on multimodal. This will need API credentials added
        if (
          pageId === "multimodal" &&
          "looker" in req.body.datasourceReferences
        ) {
          const selectedExplore =
            req.body.datasourceReferences?.looker?.explore_references?.explore;
          req.body.datasourceReferences =
            config.getMultimodalLookerDatasource(selectedExplore);
        }

        await askQuestion(req, res);
      } catch (error) {
        logger.error(error);
        res.status(500).json({ error: "An error occurred" });
      }
    }
  );

  // route to generate a Looker embed URL
  app.get("/api/looker-embed", async (req: Request, res: Response) => {
    try {
      const dashboardId = req.query.dashboardId as string;
      const embedUrl = config.generateLookerEmbedUrl(dashboardId);
      res.json({ embedUrl });
    } catch (err) {
      logger.error("Error generating embed URL:", err);
      res.status(500).json({ error: "Failed to generate embed URL" });
    }
  });

  // Serve static files from the React app
  const buildPath = path.join(__dirname, "../client/build");

  const setCustomCacheControl = (res: Response, filePath: string) => {
    // For HTML files, always revalidate to get the latest version
    if (path.extname(filePath) === ".html") {
      res.setHeader("Cache-Control", "no-cache, must-revalidate");
    } else {
      // For all other static assets (JS, CSS, images), cache for a long time
      res.setHeader("Cache-Control", "public, max-age=31536000, immutable");
    }
  };

  app.use(
    express.static(buildPath, {
      setHeaders: setCustomCacheControl,
      etag: true,
    })
  );

  // Catch-all handler for React routing
  app.get("*", (req: Request, res: Response) => {
    const indexPath = path.join(buildPath, "index.html");
    res.setHeader(
      "Cache-Control",
      "no-store, no-cache, must-revalidate, proxy-revalidate"
    );
    res.sendFile(indexPath);
  });

  app.listen(PORT, () => {
    logger.info(`Server listening on port ${PORT}`);
  });
};

startServer().catch((err) => {
  logger.error("Failed to start server:", err);
});
