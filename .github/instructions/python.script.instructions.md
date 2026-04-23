---
applyTo: '**'
---
# 🐍 Clean Python Scripts & CLI Applications — Best Practices & Standards

> Guidelines for writing clean, maintainable, and production-ready Python scripts and command-line applications.

---

## 🎯 Core Principles

| Principle | Description |
| :--- | :--- |
| **Modular Design** | Keep `main()` thin. Business logic lives in dedicated modules. |
| **Service Layer** | Complex operations go through service classes/functions. |
| **Configuration** | Use environment variables or config files. Never hardcode settings. |
| **Type Safety** | Use exhaustive type hints on all function signatures and variables. |
| **Structured Logging** | Use the `logging` module with proper levels and formatting. |
| **KISS** | Keep It Simple, Stupid. Favor simplicity over cleverness. |
| **DRY** | Don't Repeat Yourself. Extract reusable logic. |
| **SRP** | Single Responsibility. One component, one job. |
| **Explicit > Implicit** | Code should be obvious, not clever. |

---

## 🏷️ Naming Conventions

| Type | Convention | Example |
| :--- | :--- | :--- |
| Modules/Files | snake_case | `data_processor.py`, `file_handler.py` |
| Classes | PascalCase | `DataProcessor`, `ConfigManager` |
| Functions/Methods | snake_case | `process_file`, `validate_input` |
| Variables | snake_case | `input_path`, `processed_items` |
| Constants | SCREAMING_SNAKE_CASE | `MAX_RETRIES`, `DEFAULT_TIMEOUT` |
| Private Members | _snake_case | `_internal_state`, `_validate` |
| CLI Commands | kebab-case | `process-files`, `run-analysis` |

---

## 🏗️ Script Entry Point Patterns

### Keep Main Thin

```python
# ❌ Too much logic in main
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)

    results = []
    for item in data:
        if item["status"] == "active":
            processed = item["value"] * 2
            results.append(processed)

    with open("output.json", "w") as f:
        json.dump(results, f)

    print(f"Processed {len(results)} items")


# ✅ Delegate to service layer
def main() -> None:
    args = parse_arguments()
    config = load_config(args.config)
    
    setup_logging(config.log_level)
    
    processor = DataProcessor(config)
    result = processor.run(args.input, args.output)
    
    logger.info("Processing complete", extra={"items": result.count})


if __name__ == "__main__":
    main()
```

### Use Guard Clause for Entry Point

```python
# ✅ Standard entry point pattern
import sys
from pathlib import Path


def main() -> int:
    """Main entry point. Returns exit code."""
    try:
        args = parse_arguments()
        config = Config.from_env()
        
        app = Application(config)
        app.run(args)
        
        return 0
    except AppError as e:
        logger.error(e.message)
        return e.exit_code
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.exception("Unexpected error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

---

## 📦 Project Structure

### Recommended Layout

```
project/
├── src/
│   ├── __init__.py
│   ├── __main__.py          # Entry point: python -m src
│   ├── cli.py                # Argument parsing
│   ├── config.py             # Configuration management
│   ├── services/
│   │   ├── __init__.py
│   │   ├── processor.py
│   │   └── exporter.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── data.py
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       └── file_ops.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_processor.py
├── pyproject.toml
├── .env.example
└── README.md
```

### `__main__.py` Pattern

```python
# src/__main__.py
"""Allow running as: python -m src"""
from src.cli import main

if __name__ == "__main__":
    main()
```

---

## 🎛️ CLI Argument Parsing

### Using argparse

```python
import argparse
from pathlib import Path


def parse_arguments() -> argparse.Namespace:
    """Parse and validate command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="myapp",
        description="Process data files efficiently.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input data.json --output results.csv
  %(prog)s -i data.json -o results.csv --verbose
        """,
    )

    parser.add_argument(
        "-i", "--input",
        type=Path,
        required=True,
        help="Input file path",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("output.json"),
        help="Output file path (default: output.json)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making changes",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.input.exists():
        parser.error(f"Input file does not exist: {args.input}")

    return args
```

### Using Click (Alternative)

```python
import click
from pathlib import Path


@click.command()
@click.option(
    "-i", "--input",
    "input_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Input file path",
)
@click.option(
    "-o", "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=Path("output.json"),
    help="Output file path",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.option("--dry-run", is_flag=True, help="Run without making changes")
def main(
    input_path: Path,
    output_path: Path,
    verbose: bool,
    dry_run: bool,
) -> None:
    """Process data files efficiently."""
    config = Config(verbose=verbose, dry_run=dry_run)
    processor = DataProcessor(config)
    processor.run(input_path, output_path)


if __name__ == "__main__":
    main()
```

### Subcommands Pattern

```python
import argparse


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser with subcommands."""
    parser = argparse.ArgumentParser(prog="myapp")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Process command
    process_parser = subparsers.add_parser("process", help="Process files")
    process_parser.add_argument("--input", "-i", required=True)
    process_parser.add_argument("--output", "-o", required=True)
    process_parser.set_defaults(func=cmd_process)

    # Export command
    export_parser = subparsers.add_parser("export", help="Export data")
    export_parser.add_argument("--format", choices=["json", "csv"], default="json")
    export_parser.set_defaults(func=cmd_export)

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate files")
    validate_parser.add_argument("files", nargs="+")
    validate_parser.set_defaults(func=cmd_validate)

    return parser


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()
    args.func(args)
```

---

## ⚙️ Configuration Management

### Environment Variables with Pydantic

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Required settings
    database_url: str = Field(..., description="Database connection URL")

    # Optional with defaults
    debug: bool = Field(False, description="Enable debug mode")
    log_level: str = Field("INFO", description="Logging level")
    max_retries: int = Field(3, ge=1, le=10, description="Max retry attempts")
    timeout_seconds: float = Field(30.0, gt=0, description="Operation timeout")

    # Nested/computed
    @property
    def is_production(self) -> bool:
        return not self.debug


# ✅ Usage
config = Config()  # Loads from environment/.env
print(config.database_url)
```

### Simple Config with dataclasses

```python
from dataclasses import dataclass, field
from pathlib import Path
import os


@dataclass(frozen=True)
class Config:
    """Immutable application configuration."""

    input_dir: Path
    output_dir: Path
    log_level: str = "INFO"
    max_workers: int = 4
    dry_run: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            input_dir=Path(os.environ.get("INPUT_DIR", "./input")),
            output_dir=Path(os.environ.get("OUTPUT_DIR", "./output")),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            max_workers=int(os.environ.get("MAX_WORKERS", "4")),
            dry_run=os.environ.get("DRY_RUN", "").lower() == "true",
        )

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "Config":
        """Create config from parsed arguments."""
        return cls(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            log_level=args.log_level,
            dry_run=args.dry_run,
        )
```

### YAML/TOML Configuration Files

```python
from pathlib import Path
from dataclasses import dataclass
import tomllib  # Python 3.11+


@dataclass
class DatabaseConfig:
    host: str
    port: int
    name: str


@dataclass
class Config:
    database: DatabaseConfig
    debug: bool
    log_level: str

    @classmethod
    def from_toml(cls, path: Path) -> "Config":
        """Load configuration from TOML file."""
        with open(path, "rb") as f:
            data = tomllib.load(f)

        return cls(
            database=DatabaseConfig(**data["database"]),
            debug=data.get("debug", False),
            log_level=data.get("log_level", "INFO"),
        )


# config.toml
# [database]
# host = "localhost"
# port = 5432
# name = "myapp"
#
# debug = false
# log_level = "INFO"
```

### `.env` File Best Practices

```bash
# .env.example — Commit this file to version control
# Copy to .env and fill in actual values

# Required settings (no defaults)
DATABASE_URL=
SECRET_KEY=

# Optional settings (with defaults shown)
DEBUG=false
LOG_LEVEL=INFO
MAX_WORKERS=4
```

**Security Rules:**

| Rule | Description |
| :--- | :--- |
| **Never commit `.env`** | Add `.env` to `.gitignore`. Only commit `.env.example`. |
| **No secrets in logs** | Never log sensitive values like API keys or passwords. |
| **Use `.env.example`** | Document all variables with placeholder or default values. |
| **Validate early** | Fail fast on missing required variables at startup. |
| **Environment-specific** | Use `.env.development`, `.env.production` for different contexts. |

**Loading Pattern:**

```python
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore unknown variables
    )

    # Required (no default = must be set)
    database_url: str
    secret_key: str

    # Optional with defaults
    debug: bool = False
    log_level: str = "INFO"


def load_config() -> Config:
    """Load and validate configuration."""
    env_file = Path(".env")
    if not env_file.exists():
        raise ConfigurationError(
            "Missing .env file. Copy .env.example to .env and configure."
        )
    return Config()
```

**.gitignore entries:**

```gitignore
# Environment files
.env
.env.local
.env.*.local

# Keep the example
!.env.example
```

---

## 📝 Logging

### Setup Structured Logging

```python
import logging
import sys
from pathlib import Path
from typing import Literal


def setup_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    json_format: bool = False,
) -> logging.Logger:
    """Configure application logging."""
    logger = logging.getLogger()
    logger.setLevel(level)

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if json_format:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# ✅ Usage in modules
logger = logging.getLogger(__name__)


def process_item(item_id: int) -> None:
    logger.debug("Processing item", extra={"item_id": item_id})
    try:
        # ... processing logic
        logger.info("Item processed successfully", extra={"item_id": item_id})
    except ValueError as e:
        logger.warning("Invalid item data", extra={"item_id": item_id, "error": str(e)})
    except Exception as e:
        logger.exception("Failed to process item", extra={"item_id": item_id})
        raise
```

### JSON Formatter for Production

```python
import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Format log records as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in (
                    "name", "msg", "args", "levelname", "levelno",
                    "pathname", "filename", "module", "lineno",
                    "funcName", "created", "msecs", "relativeCreated",
                    "thread", "threadName", "processName", "process",
                    "message", "exc_info", "exc_text", "stack_info",
                ):
                    log_data[key] = value

        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)
```

---

## 🚨 Error Handling

### Custom Exception Classes

```python
from dataclasses import dataclass


@dataclass
class AppError(Exception):
    """Base application exception."""

    message: str
    exit_code: int = 1

    def __str__(self) -> str:
        return self.message


class ConfigurationError(AppError):
    """Invalid or missing configuration."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, exit_code=2)


class InputValidationError(AppError):
    """Invalid input data."""

    def __init__(self, message: str, field: str | None = None) -> None:
        self.field = field
        super().__init__(message=message, exit_code=3)


class FileProcessingError(AppError):
    """Error during file processing."""

    def __init__(self, message: str, file_path: str | None = None) -> None:
        self.file_path = file_path
        super().__init__(message=message, exit_code=4)


class ExternalServiceError(AppError):
    """Error communicating with external service."""

    def __init__(self, message: str, service: str, retry_after: int | None = None) -> None:
        self.service = service
        self.retry_after = retry_after
        super().__init__(message=message, exit_code=5)
```

### Error Handling Pattern

```python
import sys
import logging

logger = logging.getLogger(__name__)


def main() -> int:
    """Main entry point with structured error handling."""
    try:
        args = parse_arguments()
        config = Config.from_env()
        setup_logging(config.log_level)

        processor = DataProcessor(config)
        processor.run(args.input, args.output)

        logger.info("Completed successfully")
        return 0

    except ConfigurationError as e:
        logger.error(f"Configuration error: {e.message}")
        return e.exit_code

    except InputValidationError as e:
        logger.error(f"Validation error: {e.message}")
        if e.field:
            logger.error(f"  Field: {e.field}")
        return e.exit_code

    except FileProcessingError as e:
        logger.error(f"Processing error: {e.message}")
        if e.file_path:
            logger.error(f"  File: {e.file_path}")
        return e.exit_code

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 130

    except Exception as e:
        logger.exception("Unexpected error occurred")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

---

## 📦 Service Layer Pattern

### Service Class Structure

```python
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of processing operation."""

    processed_count: int
    skipped_count: int
    error_count: int
    output_path: Path


class DataProcessor:
    """Service for processing data files."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._validator = DataValidator()
        self._exporter = DataExporter(config.output_format)

    def run(self, input_path: Path, output_path: Path) -> ProcessingResult:
        """Process input file and write results."""
        logger.info("Starting processing", extra={"input": str(input_path)})

        data = self._load_data(input_path)
        validated = self._validate_data(data)
        processed = self._process_items(validated)

        if not self._config.dry_run:
            self._exporter.export(processed, output_path)

        return ProcessingResult(
            processed_count=len(processed),
            skipped_count=len(data) - len(validated),
            error_count=0,
            output_path=output_path,
        )

    def _load_data(self, path: Path) -> list[dict]:
        """Load data from input file."""
        logger.debug("Loading data", extra={"path": str(path)})
        # Implementation...

    def _validate_data(self, data: list[dict]) -> list[dict]:
        """Filter and validate data items."""
        return [item for item in data if self._validator.is_valid(item)]

    def _process_items(self, items: list[dict]) -> list[dict]:
        """Apply transformations to items."""
        return [self._transform(item) for item in items]

    def _transform(self, item: dict) -> dict:
        """Transform a single item."""
        # Implementation...
```

### Dependency Injection (Manual)

```python
from dataclasses import dataclass


@dataclass
class Dependencies:
    """Container for application dependencies."""

    config: Config
    logger: logging.Logger
    file_handler: FileHandler
    data_processor: DataProcessor
    exporter: Exporter


def create_dependencies(config: Config) -> Dependencies:
    """Wire up application dependencies."""
    logger = setup_logging(config.log_level)
    file_handler = FileHandler(config)
    exporter = Exporter(config.output_format)
    data_processor = DataProcessor(
        config=config,
        file_handler=file_handler,
        exporter=exporter,
    )

    return Dependencies(
        config=config,
        logger=logger,
        file_handler=file_handler,
        data_processor=data_processor,
        exporter=exporter,
    )


def main() -> int:
    config = Config.from_env()
    deps = create_dependencies(config)

    result = deps.data_processor.run(args.input, args.output)
    return 0
```

---

## 🔄 File Operations

### Safe File Handling

```python
from pathlib import Path
from contextlib import contextmanager
from tempfile import NamedTemporaryFile
import shutil


def read_json(path: Path) -> dict:
    """Read JSON file with proper error handling."""
    if not path.exists():
        raise FileProcessingError(f"File not found: {path}", file_path=str(path))

    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise FileProcessingError(f"Invalid JSON: {e}", file_path=str(path))


def write_json(path: Path, data: dict, indent: int = 2) -> None:
    """Write JSON file atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file first, then rename (atomic on same filesystem)
    with NamedTemporaryFile(
        mode="w",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
        encoding="utf-8",
    ) as f:
        json.dump(data, f, indent=indent)
        temp_path = Path(f.name)

    temp_path.rename(path)


@contextmanager
def atomic_write(path: Path, mode: str = "w"):
    """Context manager for atomic file writes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")

    try:
        with open(temp_path, mode, encoding="utf-8") as f:
            yield f
        temp_path.rename(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


# ✅ Usage
with atomic_write(Path("output.json")) as f:
    json.dump(data, f)
```

### Directory Processing

```python
from pathlib import Path
from typing import Iterator
import logging

logger = logging.getLogger(__name__)


def find_files(
    directory: Path,
    pattern: str = "*.json",
    recursive: bool = True,
) -> Iterator[Path]:
    """Find files matching pattern in directory."""
    if not directory.is_dir():
        raise FileProcessingError(f"Not a directory: {directory}")

    glob_method = directory.rglob if recursive else directory.glob
    yield from glob_method(pattern)


def process_directory(
    input_dir: Path,
    output_dir: Path,
    processor: DataProcessor,
) -> dict[str, int]:
    """Process all files in a directory."""
    stats = {"processed": 0, "skipped": 0, "errors": 0}

    for input_path in find_files(input_dir, "*.json"):
        relative = input_path.relative_to(input_dir)
        output_path = output_dir / relative

        try:
            processor.process_file(input_path, output_path)
            stats["processed"] += 1
            logger.info("Processed file", extra={"file": str(relative)})
        except FileProcessingError as e:
            stats["errors"] += 1
            logger.warning("Skipped file", extra={"file": str(relative), "error": e.message})

    return stats
```

---

## 🧪 Testing Patterns

### Unit Test Structure

```python
import pytest
from pathlib import Path
from unittest.mock import Mock, patch


class TestDataProcessor:
    """Tests for DataProcessor service."""

    @pytest.fixture
    def config(self) -> Config:
        return Config(
            input_dir=Path("/tmp/input"),
            output_dir=Path("/tmp/output"),
            dry_run=False,
        )

    @pytest.fixture
    def processor(self, config: Config) -> DataProcessor:
        return DataProcessor(config)

    def test_process_valid_item(self, processor: DataProcessor) -> None:
        # Arrange
        item = {"id": 1, "value": 100}

        # Act
        result = processor._transform(item)

        # Assert
        assert result["processed"] is True
        assert result["value"] == 200

    def test_process_skips_invalid_items(self, processor: DataProcessor) -> None:
        # Arrange
        items = [
            {"id": 1, "value": 100},
            {"id": 2, "value": None},  # Invalid
            {"id": 3, "value": 50},
        ]

        # Act
        result = processor._validate_data(items)

        # Assert
        assert len(result) == 2
        assert all(item["value"] is not None for item in result)

    def test_raises_on_missing_file(self, processor: DataProcessor) -> None:
        # Arrange
        non_existent = Path("/does/not/exist.json")

        # Act & Assert
        with pytest.raises(FileProcessingError) as exc_info:
            processor.run(non_existent, Path("/tmp/out.json"))

        assert "not found" in str(exc_info.value).lower()
```

### Fixtures with tmp_path

```python
import pytest
from pathlib import Path
import json


@pytest.fixture
def sample_data() -> list[dict]:
    return [
        {"id": 1, "name": "Alice", "status": "active"},
        {"id": 2, "name": "Bob", "status": "inactive"},
    ]


@pytest.fixture
def input_file(tmp_path: Path, sample_data: list[dict]) -> Path:
    """Create a temporary input file."""
    file_path = tmp_path / "input.json"
    with open(file_path, "w") as f:
        json.dump(sample_data, f)
    return file_path


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory."""
    output = tmp_path / "output"
    output.mkdir()
    return output


def test_end_to_end_processing(
    input_file: Path,
    output_dir: Path,
    config: Config,
) -> None:
    # Arrange
    output_file = output_dir / "result.json"
    processor = DataProcessor(config)

    # Act
    result = processor.run(input_file, output_file)

    # Assert
    assert output_file.exists()
    assert result.processed_count == 2

    with open(output_file) as f:
        output_data = json.load(f)
    assert len(output_data) == 2
```

### Mocking External Dependencies

```python
from unittest.mock import Mock, patch, MagicMock
import pytest


class TestExternalService:
    """Tests involving external service calls."""

    @patch("src.services.external.requests.get")
    def test_fetches_data_successfully(self, mock_get: Mock) -> None:
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [1, 2, 3]}
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        service = ExternalService()

        # Act
        result = service.fetch_data("https://api.example.com/data")

        # Assert
        assert result == [1, 2, 3]
        mock_get.assert_called_once_with(
            "https://api.example.com/data",
            timeout=30,
        )

    @patch("src.services.external.requests.get")
    def test_handles_timeout(self, mock_get: Mock) -> None:
        # Arrange
        mock_get.side_effect = requests.Timeout("Connection timed out")
        service = ExternalService()

        # Act & Assert
        with pytest.raises(ExternalServiceError) as exc_info:
            service.fetch_data("https://api.example.com/data")

        assert "timeout" in str(exc_info.value).lower()
```

---

## 🔄 Concurrency Patterns

### ThreadPoolExecutor for I/O-Bound Tasks

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def process_files_parallel(
    files: list[Path],
    processor: DataProcessor,
    max_workers: int = 4,
) -> dict[str, int]:
    """Process multiple files in parallel."""
    stats = {"processed": 0, "errors": 0}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(processor.process_file, f): f
            for f in files
        }

        for future in as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                future.result()
                stats["processed"] += 1
            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Failed to process {file_path}: {e}")

    return stats
```

### Async I/O with asyncio

```python
import asyncio
import aiofiles
from pathlib import Path


async def read_file_async(path: Path) -> str:
    """Read file contents asynchronously."""
    async with aiofiles.open(path, mode="r") as f:
        return await f.read()


async def process_files_async(files: list[Path]) -> list[dict]:
    """Process multiple files concurrently."""
    tasks = [process_single_file(f) for f in files]
    return await asyncio.gather(*tasks, return_exceptions=True)


async def process_single_file(path: Path) -> dict:
    """Process a single file asynchronously."""
    content = await read_file_async(path)
    # Process content...
    return {"path": str(path), "size": len(content)}


def main() -> None:
    files = list(Path("./data").glob("*.txt"))
    results = asyncio.run(process_files_async(files))
```

---

## 🚫 Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad |
| :--- | :--- |
| All logic in `main()` | Hard to test, violates SRP |
| Hardcoded file paths | Breaks portability, prevents testing |
| Missing type hints | Reduces IDE support and static analysis |
| Catching bare `Exception` | Hides bugs, makes debugging difficult |
| Print instead of logging | No log levels, hard to control output |
| Global mutable state | Hidden dependencies, unpredictable behavior |
| Ignoring return codes | Makes automation and CI/CD unreliable |
| No input validation | Crashes on unexpected data |
| Synchronous I/O in async | Blocks the event loop |
| No graceful shutdown | Data corruption, zombie processes |

---

## 📝 Documentation & Style

### Docstrings (Google Style)

```python
def process_batch(
    items: list[dict],
    batch_size: int = 100,
    validate: bool = True,
) -> ProcessingResult:
    """Process items in batches with optional validation.

    Args:
        items: List of items to process. Each item must have 'id' and 'data' keys.
        batch_size: Number of items to process per batch. Defaults to 100.
        validate: Whether to validate items before processing. Defaults to True.

    Returns:
        ProcessingResult containing counts and any error information.

    Raises:
        InputValidationError: If validate=True and items contain invalid data.
        FileProcessingError: If output file cannot be written.

    Example:
        >>> result = process_batch([{"id": 1, "data": "test"}])
        >>> print(result.processed_count)
        1
    """
    ...
```

### Code Formatting & Linting

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "ARG",    # flake8-unused-arguments
    "SIM",    # flake8-simplify
    "PTH",    # flake8-use-pathlib
]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_ignores = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
```

---

## ✅ Quick Checklist

- [ ] Entry point uses `if __name__ == "__main__"`
- [ ] `main()` returns exit code and delegates logic
- [ ] CLI arguments parsed with argparse or Click
- [ ] Configuration loaded from env vars or config files
- [ ] Structured logging configured (not just print)
- [ ] Custom exceptions with meaningful exit codes
- [ ] Type hints on all function signatures
- [ ] Service layer for business logic
- [ ] File operations handle errors gracefully
- [ ] Atomic writes for output files
- [ ] Tests use pytest with fixtures
- [ ] Tests mock external dependencies
- [ ] Graceful shutdown on Ctrl+C
- [ ] Code formatted with ruff/black
- [ ] Type-checked with mypy
- [ ] README with usage examples
