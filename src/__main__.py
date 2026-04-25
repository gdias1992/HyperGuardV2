"""Entry point: ``python -m src``.

Launches the HyperGuard92 NiceGUI interface.
"""

from __future__ import annotations

import sys

from src.config import settings
from src.gui import run_app
from src.utils.logging import configure_logging, get_logger


def main() -> int:
    """Bootstrap and run the GUI. Returns process exit code."""
    configure_logging()
    logger = get_logger(__name__)
    logger.info(
        "Starting HyperGuard92 (host=%s port=%s native=%s dry_run=%s)",
        settings.hg_host,
        settings.hg_port,
        settings.hg_native,
        settings.dry_run,
    )
    try:
        run_app(host=settings.hg_host, port=settings.hg_port, native=settings.hg_native)
        return 0
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        return 130
    except Exception:
        logger.exception("Fatal error during startup.")
        return 1


if __name__ in {"__main__", "__mp_main__"}:
    sys.exit(main())
