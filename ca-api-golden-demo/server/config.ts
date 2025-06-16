import dotenv from "dotenv";
import { SecretManagerServiceClient } from "@google-cloud/secret-manager";
import logger from "./logger";

dotenv.config();

interface UserMessage {
  userMessage: {
    text?: string;
  };
}

interface SystemMessage {
  error?: any;
  timestamp: string;
  systemMessage: {
    schema?: any;
    data?: any;
    analysis?: any;
    chart?: any;
    text?: string;
  };
}

export type Messages = SystemMessage | UserMessage;

export interface BqTableReference {
  bq: {
    table_references: {
      projectId: string;
      datasetId: string;
      tableId: string;
    }[];
  };
}

export interface LookerExploreReference {
  looker: {
    explore_references: {
      looker_instance_uri: string;
      lookml_model: string;
      explore: string;
    };
    credentials: {
      oauth: {
        secret: {
          client_id: string;
          client_secret: string;
        };
      };
    };
  };
}

export interface LookerStudioReference {
  studio: {
    datasource_ids: string;
  };
}

interface AppConfig {
  [pageId: string]: {
    datasourceReferences:
      | BqTableReference
      | LookerExploreReference
      | LookerStudioReference;
  };
}

export type DatasourceReferences =
  | BqTableReference
  | LookerExploreReference
  | LookerStudioReference;

export interface DatasourceConfig {
  datasourceReferences: DatasourceReferences;
}

export const appDatasourceReferences: AppConfig = {
  // this is a placeholder - multimodal's datasourceReferences tables are set dynamically at query time
  multimodal: {
    datasourceReferences: {
      bq: {
        table_references: [
          {
            projectId: "not-in-use",
            datasetId: "not-in-use",
            tableId: "not-in-use",
          },
        ],
      },
    },
  },

  openaq: {
    datasourceReferences: {
      bq: {
        table_references: [
          {
            projectId: "bigquery-public-data",
            datasetId: "openaq",
            tableId: "global_air_quality",
          },
        ],
      },
    },
  },

  thelook: {
    datasourceReferences: {
      bq: {
        table_references: [
          {
            projectId: "gemini-looker-demo-dataset",
            datasetId: "thelook_ecommerce",
            tableId: "events",
          },
        ],
      },
    },
  },

  cymbalpets: {
    datasourceReferences: {
      looker: {
        explore_references: {
          looker_instance_uri: "stub", // dynamically set
          lookml_model: "cymbal_pets",
          explore: "order_items",
        },
        credentials: {
          oauth: {
            secret: {
              client_id: "stub", // dynamically set
              client_secret: "stub", // dynamically set
            },
          },
        },
      },
    },
  },

  cymbalpets_branded: {
    datasourceReferences: {
      looker: {
        explore_references: {
          looker_instance_uri: "stub", // dynamically set
          lookml_model: "cymbal_pets",
          explore: "order_items",
        },
        credentials: {
          oauth: {
            secret: {
              client_id: "stub", // dynamically set
              client_secret: "stub", // dynamically set
            },
          },
        },
      },
    },
  },

  cymbalpets_embed_business_pulse: {
    datasourceReferences: {
      looker: {
        explore_references: {
          looker_instance_uri: "stub", // dynamically set
          lookml_model: "cymbal_pets",
          explore: "order_items", // business pulse uses order_items explore
        },
        credentials: {
          oauth: {
            secret: {
              client_id: "stub", // dynamically set
              client_secret: "stub", // dynamically set
            },
          },
        },
      },
    },
  },

  cymbalpets_embed_supplier_metrics: {
    datasourceReferences: {
      looker: {
        explore_references: {
          looker_instance_uri: "stub", // dynamically set
          lookml_model: "cymbal_pets",
          explore: "purchases", // supplier metrics uses purchases explore
        },
        credentials: {
          oauth: {
            secret: {
              client_id: "stub", // dynamically set
              client_secret: "stub", // dynamically set
            },
          },
        },
      },
    },
  },
};

export const multimodalLookerDatasourceReferences: {
  [explore: string]: LookerExploreReference;
} = {
  order_items: {
    looker: {
      explore_references: {
        looker_instance_uri: "stub", // dynamically set
        lookml_model: "cymbal_pets",
        explore: "order_items",
      },
      credentials: {
        oauth: {
          secret: {
            client_id: "stub", // dynamically set
            client_secret: "stub", // dynamically set
          },
        },
      },
    },
  },
  purchases: {
    looker: {
      explore_references: {
        looker_instance_uri: "stub", // dynamically set
        lookml_model: "cymbal_pets",
        explore: "purchases",
      },
      credentials: {
        oauth: {
          secret: {
            client_id: "stub", // dynamically set
            client_secret: "stub", // dynamically set
          },
        },
      },
    },
  },
};

const secretsClient = new SecretManagerServiceClient();

async function getSecret(apiSecretName: string) {
  try {
    const [version] = await secretsClient.accessSecretVersion({
      name: `projects/${process.env.GCP_PROJECT_NAME}/secrets/${apiSecretName}/versions/latest`,
    });

    const payload = version.payload?.data?.toString();

    if (!payload) {
      throw new Error("Secret not found in Secret Manager.");
    }

    return payload;
  } catch (error) {
    logger.error("Error retrieving secret from Secret Manager:", error);
    throw error;
  }
}

export const loadDatasource = (pageId: string): DatasourceConfig => {
  // Ensure a configuration exists for the provided pageId.
  if (!appDatasourceReferences[pageId]) {
    throw new Error(
      `Datasource configuration for pageId '${pageId}' not found.`
    );
  }
  return {
    datasourceReferences: appDatasourceReferences[pageId].datasourceReferences,
  };
};

// Helper function to look up multimodal Looker configuration
export const getMultimodalLookerDatasource = (
  selectedExplore: string | undefined
) => {
  if (
    selectedExplore &&
    multimodalLookerDatasourceReferences[selectedExplore]
  ) {
    return multimodalLookerDatasourceReferences[selectedExplore];
  }
  console.error(
    "Invalid or missing Looker explore. Falling back to default 'order_items'."
  );
  return multimodalLookerDatasourceReferences.order_items;
};

// Retrieves (and caches) the system instruction for a given pageId.
export async function getSystemInstruction(
  agentPageId: string
): Promise<string> {
  const secretKey = `SYSTEM_INSTRUCTION_${agentPageId.toUpperCase()}`;
  return await getSecret(secretKey);
}

// Retrieves array of emails, e.g. ["abc@google.com","def@google.com", ...]
// (This isn’t for security – just to limit access)
export async function checkAllowedEmail(pageId: string) {
  const secretKey = `ALLOWLIST_${pageId.toUpperCase()}`;
  return await getSecret(secretKey);
}

// Retrieve env variable or production secet value
export async function getEnvOrSecret(secretName: string): Promise<string> {
  if (process.env.NODE_ENV !== "production" && process.env[secretName]) {
    return process.env[secretName] as string;
  }
  return await getSecret(secretName);
}

// for multimodal live
export const loadBidiUrl = (): string => {
  const host = "us-central1-aiplatform.googleapis.com";
  return `wss://${host}/ws/google.cloud.aiplatform.v1beta1.LlmBidiService/BidiGenerateContent`;
};

// for looker dashboard embed
export const generateLookerEmbedUrl = (dashboardId: string): string => {
  const lookerHost = process.env.LOOKER_INSTANCE_URI;
  const embedDomain = process.env.LOOKER_EMBED_DOMAIN;

  if (!lookerHost || !embedDomain) {
    throw new Error("Embed configuration not set.");
  }

  const privateUrl = `${lookerHost}/embed/dashboards/${dashboardId}?embed_domain=${embedDomain}&allow_login_screen=true&sdk=2`;
  return privateUrl;
};
