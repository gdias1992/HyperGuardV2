# 📋 Logging Standards

This document defines the logging architecture and standards for the project.

---

## 🎯 Objectives

- **Centralized Storage**: All logs stored in a designated `logs/` directory for easy local access.
- **Categorization**: Separation between general application flow and critical errors.
- **Maintainability**: Automated log rotation to prevent storage exhaustion.
- **Visibility**: Clear formatting with timestamps and contextual metadata.

---

## 📊 Log Levels

All logging implementations should follow standard severity levels:

| Level | Usage |
| :--- | :--- |
| `DEBUG` | Detailed diagnostic information for development/debugging. |
| `INFO` | General runtime events, startup sequences, and business logic milestones. |
| `WARN` | Potentially harmful situations or deprecated usage patterns. |
| `ERROR` | Error events that allow the application to continue running. |
| `FATAL` | Severe errors causing premature application termination. |

---

## 🖥️ Backend Logging

### 📁 Log Files

All logs should reside in `logs/` (ignored by Git).

| File | Level | Description |
| :--- | :--- | :--- |
| `app.log` | `ALL` | All application logs including runtime events, errors, access logs, and business logic. |

### ⚙️ Configuration Guidelines

Create a centralized logging configuration file:

```text
# Recommended settings (adapt to your technology)
LOG_DIR = "logs"
MAX_SIZE = 128MB per file
BACKUP_COUNT = 5 rotated files
LOG_FORMAT = "<timestamp> | <level> | <logger_name> | <message>"
CLEAR_ON_START = true/false  # Clear log files on application startup
```

### 🔄 Log Rotation

- Implement size-based or time-based rotation (128MB limit recommended).
- Retain 5 backup files per log type (≈640MB max per category).
- Prevents unbounded log growth in long-running environments.

### 📡 Access Logging (Middleware)

Intercept HTTP requests to log:
- HTTP Method and URL
- Response status code
- Request latency

```text
# Example format in app.log
2026-01-17 10:30:45 | INFO | access | GET /api/v1/items 200 45ms
2026-01-17 10:30:46 | INFO | access | POST /api/v1/items 201 120ms
```

### 🚨 Exception Handling

Implement global exception handlers to capture unhandled errors:
- Log full stack traces to `app.log` (with ERROR level)
- Include contextual information (request URL, user context if applicable)
- Return appropriate error responses to clients

```text
# Example format in app.log
2026-01-17 10:31:00 | ERROR | app | Unhandled exception in /api/v1/items/999
<Stack Trace>
```

### 📝 Usage Pattern

```text
# Pseudocode - adapt to your language/framework
logger = getLogger("module_name")

function getItemById(id):
    logger.info("Fetching item with ID: " + id)
    // ... business logic
    logger.error("Item not found: " + id)
```

---

## 🔒 Security & Privacy

- **No PII**: User environment variables or sensitive inputs are never logged.
- **Masking**: Sensitive config values (e.g., `database_password`, API keys) must be filtered from logs.
- **Local Only**: All logs remain on the local machine; no external transmission unless explicitly configured.

---

## 📁 Directory Structure (Template)

```text
<project_root>/
├── logs/                      # Log files (Git-ignored)
│   └── app.log                # All application logs (events, errors, access)
└── <src>/
    └── <core>/
        └── <logging_config>   # Logging configuration
```

---

## 🧹 Maintenance

- **Log Rotation**: Automatic via size-based rotation (128MB × 5 files = 640MB max per log type).
- **Manual Cleanup**: Safe to delete contents of `logs/` directory at any time.
- **Git Ignore**: The `logs/` directory must be excluded from version control.

