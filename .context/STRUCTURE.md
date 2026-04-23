# 🏗️ Project Structure

> **Directory-focused guide** for Python scripts, CLI tools, and automation executables, emphasizing modularity, testability, and clear entry points.

---

## 🎯 Design Principles

| Principle | Description |
| :--- | :--- |
| **Separation of Concerns** | Keep the entry point (`__main__.py`) and argument parsing (`cli.py`) separate from business logic. |
| **Service Layer** | Complex operations are encapsulated in service classes or functions. |
| **Configuration** | Use centralized configuration via environment variables or config files. |
| **Testability** | Structure enables unit testing without invoking the CLI stack or external I/O directly. |

---

## 🗺️ Directory Structure

```text
├── src/                       # Source code root (often named after the package)
│   ├── __init__.py            # Marks the directory as a Python package
│   ├── __main__.py            # Main entry point (run with `python -m src`)
│   ├── cli.py                 # Command-line argument parsing and setup
│   ├── config.py              # Configuration schemas and management
│   ├── services/              # Core business logic and orchestration
│   │   ├── __init__.py
│   │   ├── vbs_service.py     # Windows VBS management logic
│   │   └── feature_service.py # Individual feature management
│   ├── models/                # Domain data structures (dataclasses/Pydantic)
│   │   ├── __init__.py
│   │   └── security_state.py  # VBS security state models
│   └── utils/                 # Shared helpers and utilities
│       ├── __init__.py
│       ├── logging.py         # Logging setup and formatters
│       └── registry_ops.py    # Windows Registry operations utility
├── logs/                      # Log files (git-ignored, per LOGGING.md)
│   └── app.log                # Primary application log file
├── tests/                     # Test suite
│   ├── __init__.py
│   ├── conftest.py            # Pytest fixtures and test configurations
│   └── services/              # Service layer tests
│       └── __init__.py
├── pyproject.toml             # Project metadata, dependencies, and tooling configs
├── requirements.txt           # Generated dependencies list
├── .env                       # Environment variables (git-ignored)
├── .env.example               # Template for environment variables
└── README.md                  # Project documentation and CLI usage instructions
```

---

## 📁 Key Directories

### `src/`
The root module of the executable.
- **`__main__.py`**: Contains the standard `if __name__ == "__main__":` block. Avoid placing business logic here. It should import `cli.py` to parse arguments and execute the application.
- **`cli.py`**: Handles user input using `argparse`, `click`, or `typer`.
- **`config.py`**: Centralized configuration management using `pydantic-settings` or built-in `dataclasses` reading from the environment.

### `src/services/`
The orchestrators of your script. Instead of giant scripts in one file, divide the workload into logical services (e.g., managing physical security features, hypervisor settings).

### `src/models/`
Domain data structures. Use `dataclasses` or Pydantic `BaseModel` for in-memory data representations and state tracking.

### `src/utils/`
Stateless utility functions that can be reused across services. For this project, Windows Registry manipulations and WMI queries are good candidates.
