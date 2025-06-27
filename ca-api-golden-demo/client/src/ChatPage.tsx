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

import React, { useState, useCallback, useRef, useEffect } from "react";
import { useParams } from "react-router-dom";
import Visualization from "./components/Visualization";
import Table, { parseCsv } from "./components/Table";
import TypewriterText from "./components/TypewriterText";
import { useUser } from "./UserContext";
import {
  constructLookerUrl,
  transformDataQnAResponse,
} from "./utils/dataHelpers";
import { suggestions } from "./utils/suggestions";

import "./styles/ChatPage.css";
import "./styles/Table.css";
import "./styles/Visualization.css";
import animations from "./styles/Animation.module.css";

interface ChatPageProps {
  variant?: "default" | "branded";
  dashboardId?: string;
  systemInstructionOverride?: string;
}

const LOCAL_STORAGE_KEY_PREFIX = "chatMessages-";

function ChatPage({
  variant = "default",
  dashboardId,
  systemInstructionOverride,
}: ChatPageProps) {
  const params = useParams<{ pageId: string }>();
  const pageId = params.pageId;
  const datasetKey = dashboardId ? `${pageId}_${dashboardId}` : pageId;
  const storageKey = `${LOCAL_STORAGE_KEY_PREFIX}${pageId}`;

  const chatEndRef = useRef<HTMLDivElement>(null); // Ref for auto-scrolling
  const abortControllerRef = useRef<AbortController | null>(null);
  const killSwitchRef = useRef(false);

  const [error, setError] = useState<string | null>(null); // Error message from api
  // This is used for multi-turn questions, passing message history back to API
  const [messages, setMessages] = useState<Array<any>>(() => {
    const storedMessages = localStorage.getItem(storageKey);
    return storedMessages ? JSON.parse(storedMessages) : [];
  }); // Load state from localStorage on component mount and store chat messages array per chat page
  const [renderedMessages, setRenderedMessages] = useState<Array<any>>([]); // Rendered messages for UI
  const [question, setQuestion] = useState<string>(""); // Question input by user
  const [tempStatus, setTempStatus] = useState(""); // Current step in streaming response
  const [loading, setLoading] = useState<boolean>(false); // Awaiting results from api
  const [showSuggestions, setShowSuggestions] = useState<boolean>(false); // Show suggestion chips if no message history
  const [pythonAnalysisEnabled, setPythonAnalysisEnabled] = useState(false); // enable or disable python analysis option
  const [systemInstruction, setSystemInstruction] = useState(""); // system instructions for cortado per datasource

  const { user } = useUser();

  // remove all messages that contain temp status to display
  const filteredMessages = renderedMessages.filter(
    (message) => !(message.data && message.data.ignoreMessage)
  );

  // For multi-turn message history, do not send message blocks that result in error
  // This will remove all messages sent that:
  // 1. do not have a response (500 error from internal server)
  // 2. resulted in API error
  const filterMessages = (messages: any[]) => {
    interface MessageBlock {
      header: any;
      systemMessages: any[];
    }

    const blocks: MessageBlock[] = [];
    let currentBlock: MessageBlock | null = null;

    for (const msg of messages) {
      if ("userMessage" in msg) {
        if (currentBlock && currentBlock.systemMessages.length > 0) {
          blocks.push(currentBlock);
        }
        // Start a new block with this userMessage as header.
        currentBlock = { header: msg, systemMessages: [] };
      } else if (currentBlock) {
        currentBlock.systemMessages.push(msg);
      }
    }
    if (currentBlock && currentBlock.systemMessages.length > 0) {
      blocks.push(currentBlock);
    }

    // Remove blocks that contain any error and flatten blocks (keeping only one header per block)
    return blocks
      .filter((block) => !block.systemMessages.some((m) => "error" in m))
      .flatMap((block) => [block.header, ...block.systemMessages]);
  };

  const fetchData = useCallback(
    async (question: string) => {
      setLoading(true);
      setTempStatus("Analyzing question");
      setError(null);

      killSwitchRef.current = false;
      const controller = new AbortController();
      abortControllerRef.current = controller;

      const newQuestion = { userMessage: { text: question } };
      const cleanMessages = filterMessages(messages);
      const cleanMessagesToSend = [...cleanMessages, newQuestion]; // remove errors and questions with no responses
      setMessages([...messages, newQuestion]); // contains all messages including errors

      try {
        const response = await fetch(`/api/data?pageId=${datasetKey}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            messages: cleanMessagesToSend,
            systemInstruction,
            pythonAnalysisEnabled,
            email: user!.email,
          }),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let result = "";

        const processStream = async () => {
          while (true) {
            const { value, done } = await reader!.read();
            if (done) break;

            // Decode the chunk
            const chunk = decoder.decode(value, { stream: true });
            result += chunk;

            // Process each JSON line
            const lines = result.split("\n");

            for (let i = 0; i < lines.length - 1; i++) {
              try {
                const parsedData = JSON.parse(lines[i]);
                console.log("Streaming data:", parsedData);
                const transformedData = transformDataQnAResponse([parsedData]);
                console.log("Transformed data:", transformedData);

                setMessages((messages) => [...messages, parsedData]);

                if (transformedData!.schemaResultDatasources) {
                  setTempStatus("Schema Resolved");
                  continue;
                }
                if (
                  transformedData!.generatedSQL ||
                  transformedData!.generatedLookerQuery
                ) {
                  setTempStatus("Running query");
                }
                if (transformedData!.data) {
                  setTempStatus("Generating visualization");
                }
                if (transformedData!.analysisQuestion) {
                  setTempStatus("Running code interpreter");
                }
                if (transformedData!.chartQueryInstructions) {
                  setTempStatus(
                    transformedData!.chartQueryInstructions.substring(0, 120) +
                      "..."
                  );
                  continue;
                }
                if (transformedData!.vegaConfig) {
                  setTempStatus("");
                }
                if (
                  transformedData!.ignoreMessage ||
                  transformedData!.questionReceived
                ) {
                  continue;
                }

                // Append to the messages state incrementally
                setRenderedMessages((prevMessages) => [
                  ...prevMessages,
                  { type: "response", data: transformedData },
                ]);
              } catch (err) {
                console.error("Error parsing streamed JSON:", err, lines[i]);
              }
            }

            // Keep the last chunk in case it's incomplete
            result = lines[lines.length - 1];
          }
        };

        await processStream();
      } catch (error: any) {
        if (error.name === "AbortError") {
          console.log("Fetch aborted by user");
        } else {
          console.error("Error fetching data:", error);
          setError(`An error occurred while fetching data: ${error}`);
        }
      } finally {
        setLoading(false);
      }
    },
    [user, datasetKey, systemInstruction, messages, pythonAnalysisEnabled]
  );

  // Fetch the system instruction from the backend endpoint only if no override is provided
  // Override used for cymbalpets_embed to send dashboard filters context
  useEffect(() => {
    if (pageId === "cymbalpets_embed") {
      if (systemInstructionOverride !== undefined) {
        setSystemInstruction(systemInstructionOverride);
      }
      // Early return to prevent the multiple API calls
      return;
    }

    // custom system instructions for branded versions
    const agentPageId = "cortado_" + pageId;
    fetch(`/api/system-instructions?agentPageId=${agentPageId}`)
      .then((res) => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then((data) => {
        setSystemInstruction(data.systemInstruction);
      })
      .catch((err) => {
        console.error("Error fetching system instructions:", err);
      });
  }, [pageId, variant, systemInstructionOverride]);

  // Load messages from localStorage and render on mount and when storageKey changes (navigating between chat pages)
  useEffect(() => {
    const storedMessages = localStorage.getItem(storageKey);

    // Only render values if not empty array (in string format)
    if (storedMessages && storedMessages !== "[]") {
      setMessages(JSON.parse(storedMessages));
      setRenderedMessages([]); // clean state first to handle variant switches

      JSON.parse(storedMessages).forEach((message: any) => {
        if (message.userMessage) {
          setRenderedMessages((prevMessages) => [
            ...prevMessages,
            { type: "question", text: message.userMessage.text },
          ]);
        }
        if (message.systemMessage) {
          const transformedData = transformDataQnAResponse([message]);
          setRenderedMessages((prevMessages) => [
            ...prevMessages,
            { type: "response", data: transformedData },
          ]);
        }
      });
    } else {
      setMessages([]);
      setRenderedMessages([]);
    }
  }, [storageKey]);

  // Save messages to localStorage whenever messages changes
  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(messages));
    const hasMessages = messages.length > 0;
    setShowSuggestions(!hasMessages); // Only show chips if no messages
  }, [messages, storageKey]);

  // Auto-scroll to the bottom whenever rendered messages or chat page location changes
  useEffect(() => {
    setTimeout(() => {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 0); // Need delay here for scroll to work
  }, [renderedMessages, pageId]);

  const queryHasSortingFromCurrent = (messages: any) => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const message = messages[i];

      // Stop if we hit a question message
      if (message.type === "question") {
        break;
      }

      if (message.type === "response") {
        if (message.data && message.data.generatedSQL) {
          // Check for 'order by' for SQL
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

  const clearChat = () => {
    killSwitchRef.current = true;
    abortControllerRef.current?.abort();
    setMessages([]);
    setRenderedMessages([]);
    setShowSuggestions(true);
    localStorage.removeItem(storageKey);
  };

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setQuestion(event.target.value);
  };

  const handleSuggestionClick = async (suggestion: string) => {
    setRenderedMessages((prevMessages) => [
      ...prevMessages,
      { type: "question", text: suggestion },
    ]);
    await fetchData(suggestion);
  };

  const handlePythonAnalysisClick = () => {
    setPythonAnalysisEnabled(!pythonAnalysisEnabled);
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (question.trim() === "") return; // Prevent empty questions

    // Add user's question to rendered messages
    setRenderedMessages((prevMessages) => [
      ...prevMessages,
      { type: "question", text: question },
    ]);

    setQuestion(""); // Clear the question input after sending

    await fetchData(question); // Fetch the response
  };

  const headingText =
    variant === "branded"
      ? "Conversational Analytics"
      : suggestions.find((q) => q.dataset === pageId)?.formattedName +
        " Data Demo";

  return (
    <div className="chat-page-container">
      <div className="chat-window">
        <div className="sub-header">
          <h1>{headingText}</h1>
          {filteredMessages.length > 0 && (
            <button
              type="button"
              onClick={clearChat}
              className={`new-conversation-button ${
                variant === "branded" ? "branded" : ""
              }`}
            >
              + New Conversation
            </button>
          )}
        </div>
        {filteredMessages.map((message, index) => {
          const showAvatar =
            index === 0 || filteredMessages[index - 1].type !== message.type;

          const shouldDisableSort =
            (message.data?.data || message.data?.analysisProgressCsv) &&
            queryHasSortingFromCurrent(filteredMessages.slice(0, index));

          return (
            <div key={index} className={`message ${message.type}`}>
              {/* User question */}
              {message.type === "question" && (
                <>
                  {/* User Avatar */}
                  {showAvatar && user?.photoURL && (
                    <img
                      src={user.photoURL}
                      alt="User Avatar"
                      className="user-avatar"
                      referrerPolicy="no-referrer"
                    />
                  )}
                  <div style={{ marginLeft: showAvatar ? 0 : "48px" }}></div>
                  <div
                    className={`message-box ${
                      variant === "branded" ? "branded" : ""
                    }`}
                  >
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
                      src={`${
                        variant === "branded"
                          ? "/cymbalpets.png"
                          : "/gemini.png"
                      }`}
                      alt="Agent Avatar"
                      className="agent-avatar"
                    />
                  )}
                  <div style={{ marginLeft: showAvatar ? 0 : "48px" }}></div>
                  <div className="message-box">
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
                        className={`${animations.collapsibleSection} ${
                          variant === "default" ? animations.defaultVariant : ""
                        }`}
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
                                className={
                                  variant === "default"
                                    ? "grayscale-filter"
                                    : ""
                                }
                              />
                            </a>
                          )}
                        </summary>
                        <pre className="code">
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
                        <div style={{ paddingBottom: "20px" }} />
                        <Table
                          data={message.data.data}
                          shouldSort={!shouldDisableSort}
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
                        <div style={{ paddingBottom: "20px" }} />
                        <Table
                          data={parseCsv(message.data.analysisProgressCsv)}
                          shouldSort={!shouldDisableSort}
                        />
                      </>
                    )}

                    {message.data.analysisProgressVegaChart && (
                      <div className="vega-chart">
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
                        <pre className="code">
                          {message.data.analysisProgressCode}
                        </pre>
                      </details>
                    )}

                    {/* Advanced Python Analysis fields end */}

                    {message.data.vegaConfig && (
                      <div className="vega-chart">
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
        {loading && (
          <div className="loading">
            <div className={animations.dotPulse} />
            <p
              key={tempStatus}
              style={{ marginLeft: "25px" }}
              className={`${animations.fadeInAnimate} ${animations.fadeInDelay} ${animations.fadeIn}`}
            >
              {tempStatus}
            </p>
          </div>
        )}
        {error && <div className="error-message">{error}</div>}
        <div ref={chatEndRef} />{" "}
        {/* Invisible element at the bottom to scroll to */}
      </div>

      {showSuggestions && (
        <div className="suggestions-container">
          <div className="suggestion-question"> What questions can I ask?</div>
          <div className="suggestion-chips-container">
            {suggestions
              .filter((q) => q.dataset === datasetKey)[0]
              .questions.map((suggestion, index) => (
                <button
                  key={index}
                  className="suggestion-chip"
                  onClick={() => handleSuggestionClick(suggestion)}
                >
                  {suggestion}
                </button>
              ))}
          </div>
        </div>
      )}

      <div className="form-actions">
        <form onSubmit={handleSubmit} className="chat-form">
          <div className="input-container">
            <input
              className="input-text"
              type="text"
              id="question"
              value={question}
              onChange={handleInputChange}
              placeholder="Ask a question"
            />
            <button
              type="submit"
              className={!(question.trim() === "") ? "show" : ""}
            >
              {!(question.trim() === "") ? (
                <img
                  src="/send_spark_black.png"
                  alt="Send"
                  style={{ width: "30px", height: "30px" }}
                />
              ) : null}
            </button>
          </div>
        </form>

        <div className="options">
          <div className="options-left"></div>
          {/* add more tickbox-container for each option */}
          <div className="options-right">
            <div
              className="tickbox-container"
              title="Enable this to generate and execute Python code in a secure environment"
            >
              <label className="tickmark-label-left">
                <span className="tick-label-text">Enable Code Interpreter</span>
                <div
                  className={`tick-mark ${
                    pythonAnalysisEnabled ? "checked" : ""
                  }`}
                  onClick={handlePythonAnalysisClick}
                  role="checkbox"
                  aria-checked={pythonAnalysisEnabled}
                >
                  {pythonAnalysisEnabled && (
                    <span className="checkmark">✓</span>
                  )}
                </div>
              </label>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ChatPage;
