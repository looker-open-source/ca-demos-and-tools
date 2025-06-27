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

import { User } from "firebase/auth";
import ReconnectingWebSocket from "reconnecting-websocket";
import { ErrorEvent as RWS_ErrorEvent } from "reconnecting-websocket/dist/events";
import { trimSystemInstructions } from "./dataHelpers";
import { setupMessage, clientContentPayload } from "./multimodalSetup";
import { AudioStreamer } from "./audio/audio-streamer";
import VolMeterWorklet from "./audio/vol-meter";

export type messageLogger = (message: any) => void;
export type setClientStatus = (statuts: boolean) => void;
export type updateChatQuestionHandler = (
  question: string,
  final: boolean
) => void;
export type appendChatQuestionHandler = (question: string) => void;
export type updateChatAnswerHandler = (
  transcript?: any,
  isFinal?: boolean,
  forceNew?: boolean
) => void;
export type appendChatAnswerHandler = (chunk: any) => void;
export type systemInstruction = { [key: string]: string };
export type setCortadoLoading = (status: boolean) => void;
export type getCortadoLoading = () => boolean;
export type setCortadoTempStatus = (message: string) => void;
export type setError = (message: string | null) => void;
export type datasource = "bq" | "looker";

export class MultimodalLiveClient {
  public audioContext: AudioContext;
  public audioStreamer: AudioStreamer;
  private pythonAnalysisEnabled: boolean = false;
  private killSwitchActivated = false;
  private apiAbortController: AbortController | null = null;
  private multimodalLiveWs: ReconnectingWebSocket;
  private user: User;
  private datasource: datasource;
  private messageLogger: messageLogger;
  private setClientStatus: setClientStatus;
  private updateChatQuestion: updateChatQuestionHandler;
  private appendChatQuestion: appendChatQuestionHandler;
  private updateChatAnswer: updateChatAnswerHandler;
  private appendChatAnswer: appendChatAnswerHandler;
  private systemInstruction: systemInstruction;
  private setCortadoLoading: setCortadoLoading;
  private getCortadoLoading: getCortadoLoading;
  private setCortadoTempStatus: setCortadoTempStatus;
  private setError: setError;

  constructor(
    multimodalLiveWsUrl: string,
    user: User,
    datasource: datasource,
    messageLogger: messageLogger,
    setClientStatus: setClientStatus,
    updateChatQuestion: updateChatQuestionHandler,
    appendChatQuestion: appendChatQuestionHandler,
    updateChatAnswer: updateChatAnswerHandler,
    appendChatAnswer: appendChatAnswerHandler,
    systemInstruction: systemInstruction,
    setCortadoLoading: setCortadoLoading,
    getCortadoLoading: getCortadoLoading,
    setCortadoTempStatus: setCortadoTempStatus,
    setError: setError
  ) {
    this.user = user;
    this.datasource = datasource;
    this.messageLogger = messageLogger;
    this.setClientStatus = setClientStatus;
    this.updateChatQuestion = updateChatQuestion;
    this.appendChatQuestion = appendChatQuestion;
    this.updateChatAnswer = updateChatAnswer;
    this.appendChatAnswer = appendChatAnswer;
    this.systemInstruction = systemInstruction;
    this.setCortadoLoading = setCortadoLoading;
    this.getCortadoLoading = getCortadoLoading;
    this.setCortadoTempStatus = setCortadoTempStatus;
    this.setError = setError;
    this.multimodalLiveWs = new ReconnectingWebSocket(multimodalLiveWsUrl, [], {
      connectionTimeout: 4000,
      maxRetries: Infinity,
      maxReconnectionDelay: 30000,
      // debug: true,
    });
    this.audioContext = new AudioContext({ latencyHint: "interactive" });
    this.audioStreamer = new AudioStreamer(this.audioContext);
    this.audioStreamer
      .addWorklet("pcm-player-processor", VolMeterWorklet, (ev: any) => {})
      .then(() => {
        console.log(`Successfully added worklet`);
      });

    this.multimodalLiveWs.onopen = this.multimodalLiveOnOpen.bind(this);
    this.multimodalLiveWs.onmessage = this.multimodalLiveOnMessage.bind(this);
    this.multimodalLiveWs.onerror = this.multimodalLiveOnError.bind(this);
    this.multimodalLiveWs.onclose = this.multimodalLiveOnClose.bind(this);
  }

  public setVolume(volumePercent: number) {
    const gainValue = volumePercent / 100;
    if (this.audioStreamer.gainNode) {
      this.audioStreamer.gainNode.gain.value = gainValue;
    }
  }

  public isAudioPlaying(): boolean {
    return this.audioStreamer.isAudioPlaying;
  }

  public setPythonAnalysisEnabled(enabled: boolean): void {
    this.pythonAnalysisEnabled = enabled;
  }

  /******************************************************************************************
   *                           MULTIMODAL LIVE API WEBSOCKET                                *
   *----------------------------------------------------------------------------------------*
   * This section handles the multimodal live API WebSocket connections. It manages the     *
   * client connection, forwards setup and data messages, and logs connection events.       *
   *                                                                                        *
   * Example tasks:                                                                         *
   *   - Receiving setup message from the client for system instructions config             *
   *   - Forwarding messages to the multimodal API                                          *
   *   - Handling connection open/close and errors                                          *
   ******************************************************************************************/

  // send data to Multimodal Live API WebSocket
  public send(message: any) {
    if (this.multimodalLiveWs.readyState === WebSocket.OPEN) {
      this.multimodalLiveWs.send(JSON.stringify(message));
    } else {
      const errorMessage = `Multimodal Live WebSocket is not open.
  Attempting to reconnect...`;
      console.error(errorMessage);
      this.messageLogger(errorMessage);
    }
  }

  public close() {
    this.multimodalLiveWs.close();
  }

  // Cancel cortado API mid flight and clear audio
  public cancelCortado() {
    this.killSwitchActivated = true;
    if (this.apiAbortController) {
      this.apiAbortController.abort();
    }
    this.audioStreamer.postMessage({ type: "clearQueue" });
    this.messageLogger("Request cancelled");
    console.log(
      "Cortado API call cancelled by user: streaming cancelled and audio queue cleared."
    );
  }

  private multimodalLiveOnOpen() {
    const message = "Multimodal Live WebSocket connected";
    console.log(message);
    this.messageLogger(message);
    // set the system instructions from secret
    const sessionStart = setupMessage(this.datasource);
    sessionStart.setup.systemInstruction.parts[0].text =
      this.systemInstruction[
        `gemini_multimodal_cymbal_pets_${this.datasource}`
      ];
    this.multimodalLiveWs.send(JSON.stringify(sessionStart));
  }

  private async multimodalLiveOnMessage(event: MessageEvent) {
    let message: any;

    if (typeof event.data === "string") {
      try {
        message = JSON.parse(event.data);
      } catch (e) {
        console.error("Error parsing text message", e);
        return;
      }
    } else if (event.data instanceof Blob) {
      const reader = new FileReader();
      reader.onload = async () => {
        try {
          message = JSON.parse(reader.result as string);
          await this.handleMultimodalLiveMessage(message);
        } catch (e) {
          console.error("Error parsing binary message", e);
        }
      };
      reader.readAsText(event.data);
      return;
    } else {
      console.error("Unsupported message format");
      return;
    }
    await this.handleMultimodalLiveMessage(message);
  }

  private multimodalLiveOnError(event: RWS_ErrorEvent) {
    console.error("Multimodal Live WebSocket error", event);
  }

  private multimodalLiveOnClose() {
    const message = "Multimodal Live WebSocket closed";
    console.log(message);
    this.messageLogger(message);
    this.setClientStatus(false);
  }

  private async handleMultimodalLiveMessage(message: any) {
    let logMessage = "";

    if (message.setupComplete !== undefined) {
      logMessage = `Setup complete`;
      console.log(logMessage);
      this.messageLogger(logMessage);
      this.setClientStatus(true);
    }

    // Handle interrupt by stopping audio and clear FIFO queue
    else if (message.serverContent && message.serverContent.interrupted) {
      logMessage = `Received interrupt`;
      console.log(logMessage);
      this.messageLogger(logMessage);

      // clear audio queue
      this.audioStreamer.postMessage({ type: "clearQueue" });
    }

    // Process an audio response from Gemini
    else if (
      message.serverContent &&
      message.serverContent.modelTurn &&
      Array.isArray(message.serverContent.modelTurn.parts)
    ) {
      for (const part of message.serverContent.modelTurn.parts) {
        if (
          part.inlineData &&
          part.inlineData.mimeType &&
          part.inlineData.mimeType.startsWith("audio/pcm")
        ) {
          // logMessage = `Received audio response. MIME type: ${part.inlineData.mimeType}, Data length: ${part.inlineData.data.length} characters`;
          // console.log(logMessage);
          this.messageLogger("Received audio response");

          const base64 = part.inlineData.data;
          // Decode Base64 string to binary.
          const binaryString = atob(base64);
          const len = binaryString.length;
          const bytes = new Uint8Array(len);
          for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
          }
          this.audioStreamer.addPCM16(bytes);
        }
      }

      // If a tool call for ask_question is received
    } else if (
      message.toolCall &&
      message.toolCall.functionCalls &&
      message.toolCall.functionCalls[0].name === "ask_question"
    ) {
      if (this.getCortadoLoading()) {
        console.log(
          `Ignore new toolCall as cortado request already in flight: ${message.toolCall.functionCalls[0].args.question}`
        );
        return;
      }

      await this.handleToolCall(message);

      // If tool call was cancelled
    } else if (message.toolCallCancellation) {
      this.messageLogger(`Request cancelled`);
      console.log(JSON.stringify(message));

      // inputTranscription
    } else if (
      message.serverContent &&
      message.serverContent.inputTranscription
    ) {
      const inputTranscription = message.serverContent.inputTranscription;
      this.appendChatQuestion(inputTranscription.text);

      // outputTranscription
    } else if (
      message.serverContent &&
      message.serverContent.outputTranscription
    ) {
      const outputTranscription = message.serverContent.outputTranscription;
      this.updateChatAnswer(
        outputTranscription.text,
        outputTranscription.finished
      );

      // Gemini's done generating
    } else if (
      message.serverContent &&
      message.serverContent.generationComplete
    ) {
      logMessage = `Generation complete`;
      console.log(logMessage);
      this.messageLogger(logMessage);

      // Gemini's turn finished
    } else if (message.serverContent && message.serverContent.turnComplete) {
      logMessage = `Turn complete. Usage metadata: ${JSON.stringify(
        message.usageMetadata
      )}`;
      console.log("Turn complete");
      this.audioStreamer.complete();
      this.messageLogger(logMessage);

      // Warning that Gemini will soon disconnect
    } else if (message.goAway && message.goAway.timeLeft) {
      logMessage = `Time left before connection termination: ${message.goAway.timeLeft}`;
      console.log(logMessage);
      this.messageLogger(logMessage);

      // Otherwise, pass the message back to the provided handler
    } else {
      console.log(`Unhandled message:`);
      console.log(JSON.stringify(message));
    }
  }

  private async handleToolCall(message: any) {
    // Reset kill switch state at start.
    this.killSwitchActivated = false;
    this.apiAbortController = null;

    const { question, datasource } = message.toolCall.functionCalls[0].args;
    const fullSystemInstructionYAML =
      this.systemInstruction[
        `cortado_cymbalpets_multimodal_${this.datasource}`
      ];
    const dynamicSystemInstructionYAML = trimSystemInstructions(
      fullSystemInstructionYAML,
      datasource,
      this.datasource
    );
    const datasourceReferences =
      this.datasource === "bq"
        ? { bq: { table_references: datasource } }
        : {
            looker: {
              explore_references: {
                lookml_model: datasource.lookml_model,
                explore: datasource.explore,
              },
            },
          };

    const logMessage = `Received request: ${question}
  Datasource References: ${JSON.stringify(datasource)}`;
    console.log(logMessage);
    this.messageLogger(logMessage);
    this.updateChatQuestion(question, true);
    this.setCortadoLoading(true);
    this.setError(null);
    this.setCortadoTempStatus("Analyzing question");
    const finalAnswerParts: string[] = [];

    try {
      this.apiAbortController = new AbortController();

      const response = await fetch(`/api/data?pageId=multimodal`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: [{ userMessage: { text: question } }],
          systemInstruction: dynamicSystemInstructionYAML,
          datasourceReferences,
          pythonAnalysisEnabled: this.pythonAnalysisEnabled,
          email: this.user.email,
        }),
        signal: this.apiAbortController.signal,
      });
      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let result = "";

      while (true) {
        if (this.killSwitchActivated) {
          console.log("Kill switch activated during API streaming.");
          break;
        }

        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        result += chunk;

        // Process each JSON line
        const lines = result.split("\n");

        for (let i = 0; i < lines.length - 1; i++) {
          try {
            const parsedData = JSON.parse(lines[i]);
            console.log(
              `[${parsedData.timestamp}] Received streaming results.`,
              parsedData.systemMessage
            );

            const { chunkAnswer, isFinal } = this.handleChunk(parsedData);
            if (isFinal) {
              finalAnswerParts.push(chunkAnswer);
            }
          } catch (err) {
            console.error("Error parsing streamed JSON:", err, lines[i]);
          }
        }

        // Keep the last (possibly incomplete) chunk.
        result = lines[lines.length - 1];
      }
    } catch (err: any) {
      if (err.name === "AbortError") {
        console.log("Fetch aborted by kill switch.");
      } else {
        this.setError(`Error calling Conversational Analytics API`);
        console.error(err);
      }
    } finally {
      // Handle final response and tool call for summarization

      if (!this.killSwitchActivated) {
        const finalAnswer =
          finalAnswerParts.length > 0
            ? finalAnswerParts[finalAnswerParts.length - 1]
            : "";
        console.log("Final answer:", finalAnswer);

        // Send the response for summary (add context here if you want to respond in a different language)
        const clientContentMessage = clientContentPayload(
          `Use this response to answer the corresponding question: "${finalAnswer}"`
        );
        this.send(clientContentMessage);
      }

      this.setCortadoLoading(false);
    }
  }

  private handleChunk(parsedData: any): {
    chunkAnswer: string;
    isFinal: boolean;
  } {
    let chunkAnswer = "";
    let isFinal = false;

    // Determine the case for this chunk.
    let caseKey: "final" | "intermediate" | "error" | "default" = "default";
    if (parsedData.systemMessage) {
      if (
        parsedData.systemMessage.text &&
        Array.isArray(parsedData.systemMessage.text.parts)
      ) {
        caseKey = "final";
      } else if (
        parsedData.systemMessage.schema ||
        parsedData.systemMessage.data ||
        parsedData.systemMessage.chart ||
        parsedData.systemMessage.analysis
      ) {
        caseKey = "intermediate";
      }
    } else if (parsedData.error && parsedData.error.message) {
      caseKey = "error";
    }

    // Handle based on caseKey
    switch (caseKey) {
      case "final":
        chunkAnswer = parsedData.systemMessage.text.parts.join(" ");
        isFinal = true;
        this.messageLogger(`Final Answer: ${chunkAnswer.slice(0, 50)}...`);
        this.updateChatAnswer(chunkAnswer, true, true);
        break;

      case "intermediate":
        const generatedSql =
          "data" in parsedData.systemMessage &&
          "generatedSql" in parsedData.systemMessage.data;
        const dataResult =
          "data" in parsedData.systemMessage &&
          "result" in parsedData.systemMessage.data &&
          "data" in parsedData.systemMessage.data.result;
        const analysisProgressEvent =
          "analysis" in parsedData.systemMessage &&
          "progressEvent" in parsedData.systemMessage.analysis;
        const chartQuery =
          "chart" in parsedData.systemMessage &&
          "query" in parsedData.systemMessage.chart &&
          "instructions" in parsedData.systemMessage.chart.query;

        if (generatedSql) {
          this.messageLogger(
            `Generated SQL: ${parsedData.systemMessage.data.generatedSql.slice(
              0,
              50
            )}...`
          );
        } else if (dataResult) {
          this.messageLogger(`Received results`);
        } else if (analysisProgressEvent) {
          this.messageLogger(
            `Progress event ${JSON.stringify(
              parsedData.systemMessage.analysis.progressEvent
            ).slice(0, 50)}...}`
          );
        } else if (chartQuery) {
          this.messageLogger(
            `Chart query instructions: ${parsedData.systemMessage.chart.query.instructions}`
          );
        }
        this.appendChatAnswer(parsedData);
        break;

      case "error":
        chunkAnswer = parsedData.error.message;
        isFinal = true;
        break;

      default:
        this.appendChatAnswer(parsedData);
        break;
    }
    return { chunkAnswer, isFinal };
  }
}
