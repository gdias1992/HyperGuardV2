# 🤖 Project Instructions

## 🌿 Git & Workflow
- **Branch Naming**: The agent must **always suggest a branch name** when starting a new task, feature, or bugfix. This must follow the conventions in `.github/instructions/git.instructions.md` (e.g., `feature/new-button` or `fix/header-alignment`).
- **Commit Messages**: After changing, creating, or modifying files, the agent must **always suggest a commit message** following the Conventional Commits specification as detailed in `.github/instructions/git.instructions.md`.
- **No Direct Commits**: The agent is **NEVER** allowed to automatically run `git add`, `git commit`, `git push`, or any other commands that modify staged files or repository state. The user will perform these actions manually.

## 📁 .templates/ Directory
The contents of the `.templates/` directory are **TEMPLATES ONLY**.
AI assistants are strictly forbidden from:
- Utilizing files within the `.templates/` folder as active project context.
- Treating documents in that folder as applicable to the active codebase.
