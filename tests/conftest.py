"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from src.config import settings


@pytest.fixture(autouse=True)
def _reset_dry_run() -> Iterator[None]:
    """Default each test to dry-run off; individual tests opt in."""
    original = settings.dry_run
    settings.dry_run = False
    yield
    settings.dry_run = original
