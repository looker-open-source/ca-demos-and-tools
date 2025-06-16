import { FunctionDeclaration, SchemaType } from "@google/generative-ai";
import { datasource } from "utils/MultimodalLiveClient";

// https://ai.google.dev/gemini-api/docs/multimodal-live
const askQuestionToolBQ: FunctionDeclaration = {
  name: "ask_question",
  description:
    "Answers a data analysis question about the given tables in BigQuery by returning a natural language response and/or a visualization.",
  parameters: {
    type: SchemaType.OBJECT,
    properties: {
      question: {
        type: SchemaType.STRING,
        description: "The user's question for data analysis.",
      },
      datasource: {
        type: SchemaType.ARRAY,
        description: "An array of BigQuery table references.",
        items: {
          type: SchemaType.OBJECT,
          properties: {
            projectId: {
              type: SchemaType.STRING,
              description: "The BigQuery project ID.",
            },
            datasetId: {
              type: SchemaType.STRING,
              description: "The BigQuery dataset ID.",
            },
            tableId: {
              type: SchemaType.STRING,
              description: "The BigQuery table ID.",
            },
          },
          required: ["projectId", "datasetId", "tableId"],
        },
      },
    },
    required: ["question", "datasource"],
  },
};

const askQuestionToolLooker: FunctionDeclaration = {
  name: "ask_question",
  description:
    "Answers a data analysis question about the given Looker explore by returning a natural language response and/or a visualization.",
  parameters: {
    type: SchemaType.OBJECT,
    properties: {
      question: {
        type: SchemaType.STRING,
        description: "The user's question for data analysis.",
      },
      datasource: {
        type: SchemaType.OBJECT,
        description:
          "An object containing the LookML model and Explore details for Looker.",
        properties: {
          lookml_model: {
            type: SchemaType.STRING,
            description: "The LookML model name.",
          },
          explore: {
            type: SchemaType.STRING,
            description: "The LookML Explore name.",
          },
        },
        required: ["lookml_model", "explore"],
      },
    },
    required: ["question", "datasource"],
  },
};

export const setupMessage = (datasource: datasource) => {
  let askQuestionTool;
  if (datasource === "bq") {
    askQuestionTool = askQuestionToolBQ;
  } else if (datasource === "looker") {
    askQuestionTool = askQuestionToolLooker;
  } else {
    throw new Error(`Invalid datasource specified: ${datasource}`);
  }
  return {
    setup: {
      model: `projects/${process.env.REACT_APP_FIREBASE_PROJECT_ID}/locations/us-central1/publishers/google/models/gemini-2.0-flash-live-preview-04-09`,
      inputAudioTranscription: {},
      outputAudioTranscription: {},
      generationConfig: {
        responseModalities: "AUDIO",
        speechConfig: {
          voiceConfig: { prebuiltVoiceConfig: { voiceName: "Fenrir" } }, // choose from https://cloud.google.com/vertex-ai/generative-ai/docs/live-api#voice-settings
          languageCode: "en-US", // choose from https://ai.google.dev/api/generate-content#SpeechConfig
        },
      },
      realtimeInputConfig: {
        automaticActivityDetection: {
          silenceDurationMs: 900, // modify this param to change minimum duration of non-speech before end-of-speech is committed https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/multimodal-live#automaticactivitydetection
        },
      },
      systemInstruction: {
        parts: [
          {
            text: "stub", // dynamically set
          },
        ],
      },
      tools: [
        {
          functionDeclarations: [askQuestionTool],
        },
      ],
    },
  };
};

export const clientContentPayload = (text: string) => {
  const clientContentMessage = {
    clientContent: {
      turns: [
        {
          role: "user",
          parts: [{ text }],
        },
      ],
      turnComplete: true,
    },
  };
  return clientContentMessage;
};

export const audioPayload = (base64Audio: string) => {
  const audioPcmPayload = {
    realtimeInput: {
      mediaChunks: [
        {
          mimeType: "audio/pcm;rate=16000",
          data: base64Audio,
        },
      ],
    },
  };
  return audioPcmPayload;
};
