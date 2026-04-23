---
applyTo: '**'
---

# 🧪 Testing & Validation Standards

## ✅ Quality Assurance Requirement
The assistant **must** validate all newly added or edited code before considering a task complete. This involves running tests, performing manual API calls, or inspecting frontend outputs to ensure correctness and prevent regressions.

## 📡 Backend & API Testing
- **Mandatory Check**: Every new or modified API endpoint must be verified with at least one successful request and relevant error cases.

- **Methodology**: 
  - Use `curl` in the terminal to hit local endpoints.

## 🖥️ Frontend Testing
- **Visual & Functional Validation**: For UI changes, verify that the integrated components render without errors.
- **Methodology**:
  - **Required**: Use the **Playwright MCP tool** (`mcp_microsoft_pla_browser`) to simulate the user experience. This is the mandatory method for validating UI changes and interactive features.
  - **Optional/Situational**: Use `curl` or `fetch_webpage` to retrieve HTML content from the local development server and verify the presence of expected elements or text when browser simulation is not strictly necessary.
  - Check for console errors or build warnings in the terminal when running the Vite dev server.

## 📝 Reporting
- Always include a summary of the testing performed in the final response to the user, confirming that the changes have been verified.
