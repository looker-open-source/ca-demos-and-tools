# Prism (Core Backend)

This directory contains the Core Backend for the Prism application.
It is designed as a standalone Python package following strict architectural and
stylistic guidelines.

## Project Overview

### Architecture
We use a **Modern Layered Architecture** to ensure clean separation of concerns:

### Architecture: Modular Monolith (API Facade)
We use a **Strict Modular Monolith** pattern to enforce a clean separation between the Frontend (UI) and Backend (Core). This prepares the application for a future split into microservices without immediate operational overhead.

1.  **Shared Schemas** (`src/prism/common/schemas/`):
    *   **The Contract**: Pure Pydantic models with ZERO dependencies on services or repositories. shared by both UI and Server.
2.  **API Facade** (`src/prism/client/`):
    *   **The Boundary**: The UI **MUST ONLY** import from `prism.client` and `prism.common.schemas`.
    *   **Forbidden**: The UI **MUST NOT** import `prism.server.services` or `prism.server.repositories` directly.
    *   **Dependency Injection**: The Client implementation **MUST** use `FastDepends` (`@inject` and `Depends`) to manage service dependencies. Manual wiring of Services and Repositories is forbidden in the Client layer.
3.  **Core Services** (`src/prism/server/services/`):
    *   **The Brains**: Pure business logic, unaware of the UI or HTTP.
4.  **Repositories** (`src/prism/server/repositories/`):
    *   **Data Access**: Database interactions.

### Enforcement
*   **Architecture Tests**: CI enforces these boundaries via `tests/test_architecture.py`. Any direct import from UI to Server Services will fail the build.

---

> [!NOTE]
> This file contains instructions and rules for the **AI Agent (Gemini)** working on this codebase. 
> For general developer instructions (setup, running, testing, configuration), see [README.md](README.md).

---

## Development Principles (MANDATORY)

**All contributors and agents must adhere to the following rules without
exception.**

### 1. Testing Strategy

*   **Mandatory Tests**: You MUST write unit tests for *all* new features.
*   **Validate First**: Run `./scripts/run_tests.sh` to ensure all tests pass *before* requesting review or proceeding to the next task.
    *   **NO BLAZE**: Do NOT use `blaze test` or `blaze build`. This project uses standard Python tools managed via scripts.
*   **PostgreSQL Required**: Tests strictly require a local PostgreSQL instance (use `./scripts/setup_postgres.sh`).
*   **Virtual Env**: Tests must ALWAYS be run inside the virtual environment
    (`source ~/prism_venv/bin/activate`). The provided scripts handle this
    automatically.

### 2. Coding Standards

*   **Google Python Style**: Adhere strictly to Google Python Best Practices.
*   **Auto-Formatting**: You MUST run `pyformat --in_place {FILE_PATH}` whenever you modify a Python file.
*   **Imports**:
    *   Place all imports at the top of the file.
    *   **Import Modules Only**: Use `import os` instead of `from os import path`.
*   **Logging**:
    *   Use the standard `logging` module for ALL output.
    *   **FORBIDDEN**: Do NOT use `print()` statements.
    *   **Lazy Logging**: Use lazy logging (e.g., `logging.info("Msg %s", arg)`)
        instead of f-strings or concatenation.
*   **Professional Tone**:
    *   **NO EMOJIS**: Emojis are strictly forbidden in code, comments, and commit messages.
    *   **Human-Like Style**: Write code that mimics a senior engineer. Avoid
        robotic, repetitive, or overly verbose comments. Focus on clarity,
        conciseness, and maintainability.
*   **User Consultation**:
    *   Consult the user for feedback or input if there are ever complicated decisions, unexpected outputs, or persistent errors.
    *   Consult the user for feedback or input if there are ever complicated decisions, unexpected outputs, or persistent errors.

### 2a. Backend Stability & UI-Driven Changes
*   **Explicit Approval**: If the UI implementation requires *any* changes to the `prism.server` (Schemas, Services, Repositories, or Models), you **MUST** pause and present a proposal to the Agent Owner first.
*   **Proposal Requirements**:
    1.  **Explanation**: Why is the change necessary? (e.g., "Missing field in Schema", "N+1 query issue").
    2.  **Alternatives**: What are the other options? (e.g., "Calculate in UI", "Two separate calls").
    3.  **Confirmation**: You may only proceed after explicit user confirmation.

### 3. Strict Typing

*   **Explicit Typing**: All function signatures (inputs and outputs) must have explicit type hints.
*   **Native Type Hints**: Use built-in types (`list`, `dict`, `tuple`, `set`) instead of `typing` equivalents (`List`, `Dict`, etc.).
    *   Use `X | None` instead of `Optional[X]`.
    *   Use `list[str]` instead of `List[str]`.
*   **Pydantic Models**: For any non-trivial data structure, you must define and use a `Pydantic BaseModel` subclass (Schema).
    *   **NO GENERIC DICTS**: Do NOT use `dict[str, Any]` for "configs" or complex objects. Always define a structured Pydantic model. Data bags are forbidden.
    *   *Exception*: Simple mappings (e.g. `dict[str, int]`) are allowed.

### 4. Linting (Task Completion)
*   **Final Step**: You do NOT need to run linting during the development process. Only run `hg lint -v --whole -w {FILE_PATH}` as the very last step before completing your task.
*   **Cleanliness**: Ensure the codebase remains lint-free only after the final verification.

### 5. Database Migrations (MANDATORY)
*   **Alembic**: You MUST use Alembic for any database schema changes.
*   **NO DIRECT SQL**: Manually altering the database (e.g. via `psql` CLI) is strictly forbidden.
*   **Workflow**:
    1.  Modify SQLAlchemy models.
    2.  Generate a migration script: `alembic revision --autogenerate -m "Description"`.
    3.  Review the generated script in `alembic/versions/`.
    4.  Apply the migration: `./scripts/migrate.sh` (or `alembic upgrade head`).

---

## Prism UI Design System

The "Prism" UI is built with a clear and consistent design philosophy. All
new components and pages should adhere to these principles to maintain a
cohesive and high-quality user experience.

*   **Framework:** The UI is built with **Dash** and styled using **Dash Mantine Components (DMC)**.
    *   We use DMC (Mantine) because it provides rich, modern React components wrapped in Python, avoiding the need for manual CSS classes associated with Bulma.
    *   **Strict Typing:** The UI enforces strict type safety using Pydantic and custom decorators.
    *   **Documentation:** For components using `dash-mantine-components` (DMC), refer to `dmc_llm.txt` for documentation and component properties.
*   **Theme:** The application uses a **Light Mode** and **Google Appearance** 
    aesthetic. The background should be clean white or light gray, with high 
    contrast text.
*   **Typography:** The font is **Inter**, served via Google Fonts.
*   **Iconography:** All icons are from the **Bootstrap Icons** library or native **Dash Icons**.

## UI Directory Structure

To maintain a clean separation of concerns, the UI codebase MUST follow this structure:

```
src/prism/ui/
├── app.py                # Entry point (Layout skeleton only).
│                         # - Initializes Dash app (MUST set pages_folder="").
│                         # - Calls pages.register_all_pages() after app init.
│                         # - Wraps everything in MantineProvider/NotificationsProvider.
├── assets/               # CSS/Images (Auto-served by Dash).
├── components/           # Reusable UI widgets (Stateless).
│   ├── buttons.py        # - Custom styled buttons.
│   └── tables.py         # - Shared data tables.
├── pages/                # Distinct page layouts.
│   │                     # - ONLY contains Layout code (UI structure).
│   │                     # - NO business logic or complex callbacks here.
│   ├── home.py
│   └── playground.py     # - Example: The "Ad-hoc Testing" page.
├── callbacks/            # Logic (separated from layout).
│   │                     # - Contains all @callback definitions.
│   │                     # - Calls server services.
│   │                     # - Returns updates to UI/Stores.
│   └── playground_callbacks.py
└── models/               # UI-specific Pydantic models (State definitions).
    │                     # - Defines the shape of data in dcc.Store.
    └── ui_state.py
```

```

## UI State Management: URL as the Source of Truth

For any page that uses controls (like filters, tabs, or sort orders) to alter
the data displayed, the URL's query string (`?key=value`) **must** be treated as
the single source of truth. This ensures the UI is bookmarkable, shareable, and
behaves predictably on refresh.

This is achieved using a mandatory **Three-Callback Pattern**:
1.  **UI -> URL (`update_url_from_filters`)** (Inputs -> `url.search`, `prevent_initial_call=True`)
2.  **URL -> UI (`sync_filters_to_url`)** (`url.search` -> Input values)
3.  **URL -> Data (`update_page_content`)** (`url.search` -> Page content)

## UI Architecture & Mandatory Patterns

### 1. Typed State Management
*   **No Loose Dicts:** Deeply nested dictionaries in `dcc.Store` are FORBIDDEN.
*   **Pydantic Stores:** All Store data MUST be defined as a `Pydantic BaseModel`.
    ```python
    class MyState(BaseModel):
        active_id: int
        is_open: bool
    ```

### 2. Typed Callbacks (`@typed_callback`)
*   **Mandatory Decorator:** All callbacks must use the `@typed_callback` decorator (to be implemented in `utils.py`).
*   **Type Hints:** Callback arguments must have type hints.
*   **Auto-Validation:** The decorator automatically validates inputs against their Pydantic schemas and serializes outputs.

### 3. Safe ID Management (`class Ids`)
*   **No String Literals:** Hardcoding ID strings like `"my-button"` is FORBIDDEN.
*   **Namespaced Classes:** Each page/component must define a private `Ids` class.
    ```python
    class _Ids:
        class Sidebar:
            BTN = "sidebar-btn"
        class Content:
            TABLE = "content-table"
    ```

### 4. Component Property Enums (`class CP`)

### 4. Component Property Enums (`class CP`)
*   **No Attribute Strings:** Hardcoding property names like `"n_clicks"` or `"value"` is FORBIDDEN.
*   **Common Enum:** Use the shared `ComponentProperty` enum (aliased as `CP`).
    ```python
    Input(_Ids.BUTTON, CP.N_CLICKS)
    ```

### 5. Service Layer Isolation
*   **No Direct DB Access:** The UI code must NEVER query the database directly.
*   **Service Delegation:** The UI accepts user input, validates it, and calls `prism.server.services`.
*   **Session Management:** Use `get_db_session()` helper to pass sessions to services.

### 6. Container vs Presentational Components
*   **Presentational (`src/prism/ui/components/`)**: Pure UI functions. They take arguments (e.g., `data: list[Run]`) and return Layout. They **NEVER** use `@callback` or import `services`.
*   **Container (`src/prism/ui/pages/`)**: The "Brains". They handle the `@callbacks`, calling `services`, and passing data to Presentational components.

### 7. Global Error Handling
*   **Decorator:** Use `@handle_errors` on callbacks to catch exceptions.
*   **User Feedback:** Always return a user-friendly `dmc.Notification` toast on error, never fail silently.

### 8. Verification Protocol
*   **Manual Verification**: All UI changes MUST be validated by the user. ALWAYS pause after implementation and wait for the user to verify functionality.
*   **Browser Tool Usage**: DO NOT use the browser tool for verification unless explicitly instructed by the user. This is a strict rule following user feedback.
### 9. Deferred Page Registration
To avoid initialization order issues and allow imports at the top of `app.py`, all pages MUST use the deferred registration pattern.
*   **No Top-Level Registration**: `dash.register_page()` MUST NOT be called at the top level of a module.
*   **`register_page()` Function**: Each page module MUST define a `register_page()` function at the BOTTOM of the file.
*   **Explicit Layout**: The `register_page()` function MUST pass `layout=layout` explicitly.
    ```python
    def register_page():
      dash.register_page(__name__, path="/my-path", layout=layout)
    ```
*   **Centralized Loading**: `app.py` MUST set `pages_folder=""` and call `pages.register_all_pages()` to trigger registration.

### Core Design Principles (C.R.A.P.):
*   **Contrast:** Create a strong visual hierarchy using size, weight, and 
    color. Primary actions should be immediately obvious (e.g., solid blue 
    buttons), while secondary actions should be subtle (e.g., flat, 
    shadowless "Cancel" buttons).
*   **Repetition:** Repeat visual elements to create unity. Use consistent
    fonts, colors, and component structures throughout the application.
*   **Alignment:** Nothing should be placed arbitrarily. Use strong alignment
    to create a clean, organized look. Align inputs and labels precisely.
*   **Proximity:** Group related items together. Use whitespace effectively
    to separate distinct sections and group related fields (e.g., Project ID
    and Location side-by-side).
