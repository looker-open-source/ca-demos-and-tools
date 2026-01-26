PRISM: CONVERSATIONAL ANALYTICS EVALUATION PLATFORM

VISION AND EXECUTIVE SUMMARY
Prism is a specialized evaluation platform designed to bridge the reliability gap in Generative Business Intelligence (BI). While Generative AI agents generate SQL and data insights probabilistically, enterprise users require deterministic accuracy. Prism enforces a rigorous evaluation framework using atomic, verifiable criteria rather than monolithic "golden responses."

Phase 1 Focus: An Open-Source (OSS) targeted solution for Agent Owners to bootstrap evaluations iteratively. It enables ad-hoc testing, criteria-based validation, and deep trace analysis for Looker and BigQuery-based agents.

SYSTEM ARCHITECTURE
Prism is built as a modern, decoupled web application.

Frontend
The user interface is built using Dash, providing a responsive and data-driven experience. It adheres to a "URL as Source of Truth" pattern, ensuring that every filter state, test session, and execution trace remains bookmarkable and shareable across teams.

Backend
The server follows a layered architecture to ensure clean separation between the API contract, business logic, and data persistence:
- API Layer: Handles request validation and response serialization.
- Logic Layer: Orchestrates agent interactions and runs the evaluation engine.
- Data Layer: Manages the relational persistence of test suites and historical execution data.

DATA DOMAIN MODEL
The core of Prism is its conceptual representation of the evaluation lifecycle.

Core Entities:
- Agent: The configuration of the Gemini Data Analytics (GDA) agent, including its datasources and specialized instructions.
- Test Suite: A curated collection of testing inputs for a specific domain or agent.
- Test Case: A specific user prompt or question used to validate agent behavior.
- Criterion: An atomic validation rule attached to a Test Case. Supported types include SQL Query Match, Chart Type Verification, and Row Count validation.
- Test Session: A point-in-time execution of a Test Suite. It captures an immutable snapshot of the agent's full context to ensure reproducibility.
- Execution: A single attempt of a Test Case within a Session, containing the agent's output, a full execution trace, and criteria results.

DATA RELATIONSHIPS OVERVIEW

Configuration Flow:
Agent (1)  ----<  Test Session (N)
Test Suite (1) ----< Test Case (N) ----< Criterion (N)

Execution Flow:
Test Session (1) ----< Execution (N)
Test Case (1) ----< Execution (N)
Execution (1) ----< Criterion Result (N)

[ SCHEMA DIAGRAM ]
+-----------+       +----------------+       +-------------+
|   AGENT   |-------|  TEST SESSION  |-------|  EXECUTION  |
+-----------+       +-------+--------+       +------+------+
                            |                       |
                            |                +------+------+
                    +-------+--------+       | CRITERION   |
                    |   TEST SUITE   |       |   RESULT    |
                    +-------+--------+       +------+------+
                            |                       |
                    +-------+--------+              |
                    |   TEST CASE    |--------------+
                    +-------+--------+
                            |
                    +-------+--------+
                    |   CRITERION    |
                    +----------------+

CORE CAPABILITIES

1. Iterative Bootstrapping
Users can begin testing immediately without a pre-existing "Golden Dataset." By running ad-hoc questions and flagging successful outcomes, users build their ground truth library "as they go."

2. Rich Criterion Library
Supports complex validation beyond simple text comparisons:
- Query Assertions: Verify SQL structure and specific query logic.
- Data Assertions: Validate the accuracy and shape of the resulting dataset.
- Performance: Enforce duration standards for production readiness.

3. Curation and Suggestions
The system proactively suggests validation criteria based on successful agent outputs. Owners can review and promote these suggestions to the permanent Test Suite, automating the creation of regression tests.

4. Forensic Trace Analysis
Enables deep inspection of an agent's reasoning path, including internal thoughts, tool calls, and generated queries, to quickly identify the root cause of logic failures.

TECHNOLOGY STACK
- Languages: Python
- Frontend: Dash (React-based)
- Styling: Google Design aesthetic
- Database: SQL-based persistence
- Validation: Pydantic
- Integration: Gemini Data Analytics API
