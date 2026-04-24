# 🤖 AI Agent Instructions (AGENTS.md)

This file provides system instructions and necessary context to AI agents (like GitHub Copilot, Cline, or Windsurf) working within this repository.
The goal is to ensure consistent, high-quality contributions that align with project standards and conventions.

## 🏢 Project Context
*   **Project Name:** HyperGuard92
*   **Purpose:** This application is a modern graphical interface for managing Windows 11 Virtualization-Based Security (VBS) features. It natively implements the logic previously handled by `VBS_1.6.2.cmd`, allowing users to easily toggle security features via a Python-based GUI/CLI.
*   **Key Technologies:** Python 3.14, pywin32, Pydantic, Ruff, pytest.
*   **Architecture:** Modular Python Script following a service-oriented structure with clear separation between CLI interface, business logic (vbs_service), and utility functions (registry_ops).

## 📚 Core Documentation
To fully grasp the setup, architecture, and design, refer to the following critical files:
*   [**README.md**](README.md): High-level project description, tech stack overview, and setup procedures.
*   [**STRUCTURE.md**](.context/STRUCTURE.md): Directory structure and architectural patterns.
*   [**TECHNOLOGIES.md**](.context/TECHNOLOGIES.md): Detailed specification of all major libraries, frameworks, and tools used.
*   [**CODING.md**](.context/CODING.md): Core coding principles, naming conventions, and specific programming patterns.
*   [**LOGGING.md**](.context/LOGGING.md): Centralized logging architecture, log levels, formatting, and file rotation criteria.
*   *Maintenance Policy*: Any core project document must be updated whenever changes occur in the project's scope, architecture, or tools.

## 📜 Standard Operating Procedures (SOPs)
All specialized rules are stored in the `.github/instructions/` directory. AI agents **must** adhere strictly to them:
*   **Coding Standards**: Follow `python.script.instructions.md`.
*   [**Testing & Validation**](.github/instructions/agent.instructions.md): Mandatory unit testing for logic and state changes.
*   [**Git & Workflow Standards**](.github/instructions/git.instructions.md): Conventional Commits, PR policy, Branching strategy. (Agents must *suggest* commit messages, but never commit or push directly).


## 🛠️ General Instructions
*   **Language Typings:** Use strict Python type hints. Avoid `Any`. Use Pydantic models for configuration and state.
*   **Windows API:** Use `pywin32` for registry and system-level operations. Avoid calling external PowerShell/CMD scripts if native Python solutions exist.
*   **Command Line Tooling:** Use `pytest` for testing and `ruff` for linting/formatting.
*   **Security:** Ensure all registry operations are performed safely and validated against known good states.

## ✅ Task Validation
Before concluding any implementation task:
1.  Start the development server locally using the project's configured run command.
2.  Use tools (like `mcp_microsoft_pla_browser` / Playwright) to validate that the application functions and renders without errors.
3.  For API changes, verify endpoints with at least one successful request and relevant error cases (e.g., using `curl`).
4.  Check the terminal output for errors, warnings, or failed tests.

## 📝 Documentation Style Guide
When creating or editing project documentation, agents **must** follow the established visual pattern used across existing documents:

*   **Emojis in headings:** Every `##` section heading must start with a relevant emoji (e.g., `## 🎯 Purpose`, `## 🏗️ Architecture`).
*   **Mermaid diagrams:** When illustrating architecture, flows, or decision trees, use Mermaid `flowchart` diagrams following these rules:
    *   **Direction:** Use `flowchart LR` (left-to-right) for request/data flows and `flowchart TD` (top-down) for decision trees or hierarchies.
    *   **Subgraphs:** Group related nodes inside named `subgraph` blocks. Titles must include an emoji prefix (e.g., `subgraph Barramento ["🔌 LIA Barramento API"]`).
    *   **Node labels:** Include emojis for quick visual scanning (e.g., `🔐 Basic Auth`, `🌐 Controller`, `🔀 Router`, `🧩 Service`).
    *   **Node shapes:** Use rounded rectangles `["..."]` for components, decision diamonds `{"..."}` for routers/switches, cylinders `[("...")]` for external databases/APIs, and triple-circle `((("...")))` for actors.
    *   **Edge labels:** Use `-- "label" -->` for description. Keep labels short (2-5 words). Avoid nested quotes.
    *   **Dashed edges:** Use `-.->` or `-.-|"label"|` for optional/conditional paths (e.g., exception catches).
    *   **Color palette:** Every diagram must define `classDef` classes using the project color scheme:
        *   **Bot/Client:** `fill:#E1F5FE, stroke:#3498DB` (light blue)
        *   **Core/Internal:** `fill:#FDFEFE, stroke:#85C1E9` (white-blue)
        *   **Facades/Providers:** `fill:#E8DAEF, stroke:#5B2C6F` (purple)
        *   **Stub/Success:** `fill:#D5F5E3, stroke:#27AE60` (green)
        *   **External Systems:** `fill:#FDEDEC, stroke:#E74C3C` (red)
        *   **Config/Handlers:** `fill:#FCF3CF, stroke:#D4AC0D` (yellow)
        *   **New/Placeholder:** `fill:#D6EAF8, stroke:#2E86C1, stroke-dasharray:5 5` (dashed blue)
        *   **Error:** `fill:#FDEDEC, stroke:#E74C3C` (red)
    *   **Apply styles:** Always assign `classDef` classes to nodes via `:::className` syntax (e.g., `Controller["🌐 Controller"]:::core`). Never leave nodes unstyled.
    *   **Reference:** See the diagrams in `README.md` and [CODING.md](.context/CODING.md) as canonical examples.
*   **Tone:** Professional but approachable. Use concise, action-oriented language. Avoid overly formal or academic phrasing.
*   **Tables:** Use Markdown tables for comparisons, checklists, and reference data. Keep columns concise.
*   **Code blocks:** Always specify the language tag (e.g., ` ```csharp `, ` ```json `, ` ```bash `).
*   **Consistency:** Match the structure and vocabulary of existing documentation. Do not introduce new visual conventions without updating all existing docs to match.
