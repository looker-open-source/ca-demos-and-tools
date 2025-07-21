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

import React, { useEffect, useState, useRef } from "react";
import { useLocation } from "react-router-dom";
import Visualization from "./components/Visualization";
import Table, { parseCsv } from "./components/Table";
import TypewriterText from "./components/TypewriterText";
import { useUser } from "./UserContext";
import {
  constructLookerUrl,
  transformDataQnAResponse,
} from "./utils/dataHelpers";
import { clientContentPayload, audioPayload } from "utils/multimodalSetup";
import { datasource, MultimodalLiveClient } from "utils/MultimodalLiveClient";
import { useLiveAudioStream } from "utils/audio/useLiveAudioStream";

import "./styles/ChatPage.css";
import "./styles/Table.css";
import "./styles/Visualization.css";
import multimodalStyles from "./styles/Multimodal.module.css";
import animations from "./styles/Animation.module.css";

interface LogEntry {
  message: string;
  count: number;
}

interface Message {
  type: "response" | "question";
  text?: string;
  data?: any;
  final?: boolean;
}

const Multimodal: React.FC = () => {
  const { search } = useLocation();
  const queryParams = new URLSearchParams(search);
  const rawDs = queryParams.get("datasource");
  const datasource: datasource =
    rawDs === "bq" || rawDs === "looker" ? rawDs : "looker";
  const pageId = "multimodal";

  const [chatTitle, setChatTitle] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState<string>("");
  const [cortadoTempStatus, setCortadoTempStatus] = useState("");
  const [cortadoLoading, setCortadoLoading] = useState<boolean>(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logsMinimized, setLogsMinimized] = useState(false);
  const [clientStatus, setClientStatus] = useState<boolean>(false);
  const [pythonAnalysisEnabled, setPythonAnalysisEnabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [systemInstruction, setSystemInstruction] = useState({});
  const [volume, setVolume] = useState(100);
  const [audioPlaying, setAudioPlaying] = useState(false);

  const messagesRef = useRef<Message[]>([]);
  const clientRef = useRef<MultimodalLiveClient | null>(null);
  const cortadoLoadingRef = useRef(cortadoLoading);

  const { user } = useUser();

  const getCortadoLoading = () => cortadoLoadingRef.current;

  const logMessage = (msg: any) => {
    setLogs((prevLogs) => {
      // If there is a previous log and it's the same message, increment count.
      if (
        prevLogs.length > 0 &&
        prevLogs[prevLogs.length - 1].message === msg
      ) {
        const updatedLogs = [...prevLogs];
        updatedLogs[updatedLogs.length - 1] = {
          ...updatedLogs[updatedLogs.length - 1],
          count: updatedLogs[updatedLogs.length - 1].count + 1,
        };
        return updatedLogs;
      }
      // Otherwise, add a new log entry with count 1.
      return [...prevLogs, { message: msg, count: 1 }];
    });
  };

  // Output audio transcription continuously sends text that needs to be concatenated until finished status is included
  const updateChatAnswer = (
    transcript?: string,
    isFinal?: boolean,
    forceNew?: boolean
  ) => {
    if (transcript === undefined) {
      return;
    }

    setMessages((prevMessages) => {
      const lastIdx = prevMessages.length - 1;
      const lastMsg = prevMessages[lastIdx];

      // 1) If forceNew, then append a new message.
      if (forceNew) {
        return [
          ...prevMessages,
          {
            type: "response",
            data: { text: transcript },
            final: true,
          },
        ];
      }

      // 2) If there is no messages OR last is not a response, append a new one.
      const shouldStartNew =
        prevMessages.length === 0 || lastMsg.type !== "response";
      if (shouldStartNew) {
        return [
          ...prevMessages,
          {
            type: "response",
            data: { text: transcript },
            final: false,
          },
        ];
      }

      // From here on we know: prevMessages is non-empty AND lastMsg.type === "response"

      // 3) If the last message was already marked final, do nothing.
      if (lastMsg.final) {
        return prevMessages;
      }

      // 4) If the last message was a response and isFinal is true, mark it final.
      if (isFinal) {
        const updated = [...prevMessages];
        updated[lastIdx] = { ...lastMsg, final: true };
        return updated;
      }

      // 5) Otherwise the last message was not final, so concatenate the latest transcript.
      const updated = [...prevMessages];
      updated[lastIdx] = {
        ...lastMsg,
        data: { text: lastMsg.data.text + transcript },
        final: false,
      };
      return updated;
    });
  };

  // This callback is used to update the messages state with streaming results for ask question tool
  const appendChatAnswer = (parsedData: any) => {
    const transformedData = transformDataQnAResponse([parsedData]);

    if (transformedData!.schemaResultDatasources) {
      setCortadoTempStatus("Schema Resolved");
      return;
    }
    if (
      transformedData!.generatedSQL ||
      transformedData!.generatedLookerQuery
    ) {
      setCortadoTempStatus("Running query");
    }
    if (transformedData!.name) {
      const dataTitle = transformedData!.name
        .split("_")
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
      setChatTitle(dataTitle);
    }
    if (transformedData!.data) {
      setCortadoTempStatus("Generating visualization");
    }
    if (transformedData!.analysisQuestion) {
      setCortadoTempStatus("Running code interpreter");
    }
    if (transformedData!.chartQueryInstructions) {
      setCortadoTempStatus(
        transformedData!.chartQueryInstructions.substring(0, 120) + "..."
      );
      return;
    }
    if (transformedData!.vegaConfig) {
      setCortadoTempStatus("");
    }
    if (transformedData!.ignoreMessage || transformedData!.questionReceived) {
      return;
    }
    // Append to the messages state incrementally
    setMessages((prevMessages) => [
      ...prevMessages,
      { type: "response", data: transformedData },
    ]);
  };

  // This callback is used to handle:
  // 1. text submissions from input, and
  // 2. update the question from the ask question tool
  const updateChatQuestion = (question: string, final: boolean) => {
    const prevMessages = messagesRef.current;
    // If there are no messages or the last message is not a question or not marked as final, append a new one.
    if (
      prevMessages.length === 0 ||
      prevMessages[prevMessages.length - 1].type !== "question" ||
      prevMessages[prevMessages.length - 1].final
    ) {
      setMessages([
        ...prevMessages,
        { type: "question", text: question, final },
      ]);
    } else {
      // Otherwise, update the last message with user's question
      const updatedMessages = [...prevMessages];
      updatedMessages[updatedMessages.length - 1] = {
        ...updatedMessages[updatedMessages.length - 1],
        text: question,
        final,
      };
      setMessages(updatedMessages);
    }
  };

  // This callback is used to append the messages state with input audio transcriptions from user's microphone
  const appendChatQuestion = (question: any) => {
    setMessages((prevMessages) => [
      ...prevMessages,
      { type: "question", text: question },
    ]);
  };

  const queryHasSortingFromCurrent = (messages: Message[]) => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const message = messages[i];

      // Stop if we hit a question message
      if (message.type === "question") {
        break;
      }

      if (message.type === "response") {
        // Check for 'order by' for SQL
        if (message.data && message.data.generatedSQL) {
          if (/order\s+by/i.test(message.data.generatedSQL)) {
            return true;
          }
        }

        // Check for 'sorts' for Looker
        if (message.data && message.data.generatedLookerQuery) {
          const lookerQueryStr = JSON.stringify(
            message.data.generatedLookerQuery
          );
          if (/"sorts"/i.test(lookerQueryStr)) {
            return true;
          }
        }
      }
    }
    return false;
  };

  // Send continuous audio data to Gemini API in chunks
  const { streaming, startStreaming, stopStreaming } = useLiveAudioStream(
    (base64Chunk: string) => {
      if (clientRef.current) {
        const payload = audioPayload(base64Chunk);
        // console.log("Sending live audio chunk:", payload);
        clientRef.current.send(payload);
      }
    }
  );

  // Initialize the MultimodalLiveClient
  useEffect(() => {
    if (Object.keys(systemInstruction).length === 0) return; // Wait until systemInstruction is set
    if (clientRef.current) return; // Prevent re-initializing if the client already exists

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const multimodalLiveWsUrl =
      process.env.REACT_APP_WS_MULTIMODAL_LIVE_URL ||
      `${protocol}//${window.location.host}/ws/multimodal`;

    const client = new MultimodalLiveClient(
      multimodalLiveWsUrl,
      user!,
      datasource,
      logMessage,
      setClientStatus,
      updateChatQuestion,
      appendChatQuestion,
      updateChatAnswer,
      appendChatAnswer,
      systemInstruction,
      setCortadoLoading,
      getCortadoLoading,
      setCortadoTempStatus,
      setError
    );
    clientRef.current = client;
    client.setVolume(volume);
  }, [user, systemInstruction, datasource, volume]);

  useEffect(() => {
    clientRef.current = null; // clear out the old client first when datasource changes so it can reload with new system instructions

    // Fetch the system instruction for both gemini and cortado from the backend endpoint
    const agentPageId = [
      `cortado_cymbalpets_multimodal_${datasource}`,
      `gemini_multimodal_cymbal_pets_${datasource}`,
    ];
    const fetchSystemInstructions = async () => {
      try {
        // Map over the array of pageIds and create an array of fetch promises.
        const results = await Promise.all(
          agentPageId.map(async (agentPageId) => {
            const res = await fetch(
              `/api/system-instructions?agentPageId=${agentPageId}`
            );
            if (!res.ok) {
              throw new Error(`HTTP error! status: ${res.status}`);
            }
            const data = await res.json();
            return { agentPageId, systemInstruction: data.systemInstruction };
          })
        );

        // Transform the array of results into an object keyed by agentPageId
        const instructionsObj = results.reduce<Record<string, string>>(
          (acc, { agentPageId, systemInstruction }) => {
            acc[agentPageId] = systemInstruction;
            return acc;
          },
          {}
        );

        setSystemInstruction(instructionsObj);
      } catch (err) {
        console.error("Error fetching system instructions:", err);
      }
    };

    fetchSystemInstructions();
  }, [pageId, datasource]);

  useEffect(() => {
    if (clientRef.current) {
      clientRef.current.setPythonAnalysisEnabled(pythonAnalysisEnabled);
    }
  }, [pythonAnalysisEnabled]);

  useEffect(() => {
    cortadoLoadingRef.current = cortadoLoading;
  }, [cortadoLoading]);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  // Poll the client for audio status every 500ms.
  useEffect(() => {
    const intervalId = setInterval(() => {
      if (clientRef.current) {
        if (
          audioPlaying &&
          audioPlaying !== clientRef.current.isAudioPlaying()
        ) {
          logMessage("Audio complete");
        }
        setAudioPlaying(clientRef.current.isAudioPlaying());
      }
    }, 500);

    return () => clearInterval(intervalId);
  }, [audioPlaying]);

  const cancelCortado = () => {
    if (clientRef.current) {
      clientRef.current.cancelCortado();
    }
  };

  const handlePythonAnalysisClick = () => {
    setPythonAnalysisEnabled(!pythonAnalysisEnabled);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && clientRef.current) {
      const msg = clientContentPayload(input);
      clientRef.current.send(msg);
      updateChatQuestion(input.trim(), false);
      setInput("");
    }
  };

  const clearChat = () => {
    setMessages([]);
    setInput("");
    setCortadoTempStatus("");
    setCortadoLoading(false);
    setLogs([]);
    setError(null);
    setChatTitle("Untitled");
  };

  const toggleStreaming = async () => {
    let message = "";
    if (!streaming) {
      startStreaming();
      if (clientRef.current) {
        await clientRef.current.audioContext.resume();
      }
      message = "Streaming live audio";
      console.log(message);
      logMessage(message);
    } else {
      stopStreaming();
      message = "Stopped streaming live audio";
      console.log(message);
      logMessage(message);
    }
  };

  // Handler for volume slider
  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newVolume = Number(e.target.value);
    setVolume(newVolume);
    if (clientRef.current) {
      clientRef.current.setVolume(newVolume);
    }
  };

  return (
    <div className={multimodalStyles.chatPageContainer}>
      <div className={multimodalStyles.innerHeader}>
        <h1>{chatTitle}</h1>
        {messages.length > 0 && (
          <button
            type="button"
            onClick={clearChat}
            className={multimodalStyles.newConversationButton}
          >
            + New Conversation
          </button>
        )}
      </div>

      {/* Left Panel for Chat Content */}
      <div
        className={multimodalStyles.leftPanel}
        style={{
          marginRight: logsMinimized ? "30px" : "300px",
        }}
      >
        <div className={multimodalStyles.chatWindow}>
          {messages.map((message, index) => {
            const showAvatar =
              index === 0 || messages[index - 1].type !== message.type;

            const shouldDisableSort =
              (message.data?.data || message.data?.analysisProgressCsv) &&
              queryHasSortingFromCurrent(messages.slice(0, index));

            return (
              <div
                key={index}
                className={`${multimodalStyles.message} ${
                  multimodalStyles[message.type]
                }`}
              >
                {/* User question */}
                {message.type === "question" && (
                  <>
                    {/* User Avatar */}
                    {showAvatar && user?.photoURL && (
                      <img
                        src={user.photoURL}
                        alt="User Avatar"
                        className={multimodalStyles.userAvatar}
                        referrerPolicy="no-referrer"
                      />
                    )}
                    <div style={{ marginLeft: showAvatar ? 0 : "48px" }}></div>
                    <div className={multimodalStyles["message-box"]}>
                      <p>{message.text}</p>
                    </div>
                  </>
                )}

                {/* API response */}
                {message.type === "response" && message.data && (
                  <>
                    {/* Agent Avatar */}
                    {showAvatar && (
                      <img
                        src="/cymbalpets_paw.png"
                        alt="Agent Avatar"
                        className={multimodalStyles.agentAvatar}
                      />
                    )}
                    <div style={{ marginLeft: showAvatar ? 0 : "48px" }}></div>
                    <div className={multimodalStyles["message-box"]}>
                      {message.data.questionReceived && (
                        <p>Analyzing question</p>
                      )}

                      {message.data.text && (
                        <TypewriterText
                          text={message.data.text}
                          containerClassName={animations.text}
                        />
                      )}

                      {message.data.errorMessage && (
                        <div className="error-message">
                          <p>{message.data.errorMessage}</p>
                        </div>
                      )}

                      {message.data.derivedQuestion && (
                        <TypewriterText
                          text={message.data.derivedQuestion}
                          containerClassName={animations.text}
                          delayMultiplier={0.01}
                        />
                      )}

                      {(message.data.generatedSQL ||
                        message.data.generatedLookerQuery) && (
                        <details
                          className={animations.collapsibleSection}
                          open={false}
                        >
                          <summary>
                            Query generated.
                            {message.data.generatedLookerQuery && (
                              <a
                                href={constructLookerUrl(
                                  message.data.generatedLookerQuery
                                )}
                                target="_blank"
                                rel="noreferrer"
                                className="exploreLink"
                                title="Open in Explore"
                              >
                                <img
                                  src="/looker_explore.png"
                                  alt="Open in Explore"
                                />
                              </a>
                            )}
                          </summary>
                          <pre className={multimodalStyles.code}>
                            {message.data.generatedSQL}
                            {message.data.generatedLookerQuery &&
                              JSON.stringify(
                                message.data.generatedLookerQuery,
                                null,
                                2
                              )}
                          </pre>
                        </details>
                      )}

                      {message.data.data && (
                        <>
                          <summary>Here are the results:</summary>
                          <div style={{ paddingBottom: "32px" }} />
                          <Table
                            data={message.data.data}
                            shouldSort={!shouldDisableSort}
                            variant="branded"
                          />
                        </>
                      )}

                      {/* Advanced Python Analysis fields start */}

                      {message.data.analysisQuestion && (
                        <TypewriterText
                          text={message.data.analysisQuestion}
                          containerClassName={animations.text}
                          delayMultiplier={0.01}
                        />
                      )}

                      {message.data.analysisProgressText && (
                        <div className="text">
                          <p>{message.data.analysisProgressText}</p>
                        </div>
                      )}

                      {message.data.analysisProgressCsv && (
                        <>
                          <summary>Here are the results:</summary>
                          <div style={{ paddingBottom: "32px" }} />
                          <Table
                            data={parseCsv(message.data.analysisProgressCsv)}
                            shouldSort={!shouldDisableSort}
                            variant="branded"
                          />
                        </>
                      )}

                      {message.data.analysisProgressVegaChart && (
                        <div className="vega-chart branded">
                          <Visualization
                            spec={JSON.parse(
                              message.data.analysisProgressVegaChart
                            )}
                          />
                        </div>
                      )}

                      {message.data.analysisProgressCode && (
                        <details
                          className={animations.collapsibleSection}
                          open={false}
                        >
                          <summary>Code generated:</summary>
                          <pre className={multimodalStyles.code}>
                            {message.data.analysisProgressCode}
                          </pre>
                        </details>
                      )}

                      {/* Advanced Python Analysis fields end */}

                      {message.data.vegaConfig && (
                        <div className="vega-chart branded">
                          <span className="vega-chart-title">
                            {message.data.vegaConfig.title}
                          </span>
                          <Visualization spec={message.data.vegaConfig} />
                        </div>
                      )}
                    </div>
                  </>
                )}
              </div>
            );
          })}
          {cortadoLoading && (
            <div className="loading">
              <div className={animations.dotPulse} />
              <p
                key={cortadoTempStatus}
                style={{ marginLeft: "25px" }}
                className={`${animations.fadeInAnimate} ${animations.fadeInDelay} ${animations.fadeIn}`}
              >
                {cortadoTempStatus}
              </p>
            </div>
          )}
          {error && <div className="error-message">{error}</div>}
        </div>

        <div className={multimodalStyles.myChatContainer}>
          {/* Top Row: Input, Send Button, Mic Icon */}
          <div className={multimodalStyles.topRow}>
            <form onSubmit={handleSubmit} className={multimodalStyles.topForm}>
              <input
                className={multimodalStyles.topInput}
                type="text"
                placeholder="Ask a question"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={streaming} // disable if mic is hot
              />
              <button
                type="submit"
                className={multimodalStyles.sendButton}
                disabled={streaming || !input.trim()}
                title="Send"
              >
                <img
                  src="/send_spark_white.png"
                  alt="Send"
                  style={{ width: "25px", height: "25px" }}
                />
              </button>
            </form>
            {/* Large Mic Icon */}
            <div
              className={`${multimodalStyles.micContainer} ${
                streaming ? multimodalStyles.listening : ""
              }`}
              onClick={toggleStreaming}
            >
              <img
                src={streaming ? "/mic_active.png" : "/mic_inactive.png"}
                alt="Microphone"
                className={multimodalStyles.micIcon}
              />
            </div>

            {/* Stop Cortado and Audio Button Container */}
            <div
              className={multimodalStyles.stopCortadoContainer}
              onClick={cancelCortado}
              style={{
                opacity: cortadoLoading || audioPlaying ? 1 : 0,
                pointerEvents: cortadoLoading || audioPlaying ? "auto" : "none",
                transition: "opacity 0.5s ease-in-out",
              }}
            >
              <img
                src="/stop_circle.png"
                alt="Stop"
                className={multimodalStyles.stopCortadoIcon}
              />
            </div>
          </div>

          {/* Python analysis + Status + Volume slider in one row */}
          <div className={multimodalStyles.settingsRow}>
            {/* Python Analysis */}
            <div className={multimodalStyles.pythonSection}>
              <label
                className={multimodalStyles.tickboxLabel}
                title="Enable this to generate and execute Python code in a secure environment"
              >
                <input
                  type="checkbox"
                  className={multimodalStyles.customCheckbox}
                  checked={pythonAnalysisEnabled}
                  onChange={handlePythonAnalysisClick}
                />
                <span>Enable Code Interpreter</span>
              </label>
            </div>

            <div className={multimodalStyles.statusAndVolume}>
              <p className={multimodalStyles.status}>
                {"Status: "}
                <span
                  className={
                    clientStatus
                      ? multimodalStyles.statusConnected
                      : multimodalStyles.statusDisconnected
                  }
                >
                  {clientStatus ? "Connected" : "Disconnected"}
                </span>
              </p>

              {/* Volume */}
              <div className={multimodalStyles.volumeSection}>
                <label htmlFor="volume-slider">Volume: </label>
                <input
                  id="volume-slider"
                  type="range"
                  min="0"
                  max="100"
                  value={volume}
                  onChange={handleVolumeChange}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right Panel for Logs */}
      <div
        className={`${multimodalStyles.rightPanel} ${
          logsMinimized ? multimodalStyles.minimized : ""
        }`}
      >
        <div
          className={`${multimodalStyles.rightPanelHeader} ${
            logsMinimized ? multimodalStyles.minimized : ""
          }`}
        >
          <span
            className={multimodalStyles.minimizeIcon}
            onClick={() => setLogsMinimized((prev) => !prev)}
          >
            {logsMinimized ? "◀" : "▶ Stream"}
          </span>
        </div>
        <div className={multimodalStyles.logsContainer}>
          {!logsMinimized &&
            logs.map((log, idx) => (
              <div key={idx} className={multimodalStyles.logMessage}>
                {log.message}
                {log.count > 1 && (
                  <span className={multimodalStyles.logCounter}>
                    {log.count}
                  </span>
                )}
              </div>
            ))}
        </div>
      </div>
    </div>
  );
};

export default Multimodal;
