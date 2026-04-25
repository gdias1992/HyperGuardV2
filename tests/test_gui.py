"""Tests for GUI presentation helpers."""

from __future__ import annotations

from src.gui import _feature_card_classes
from src.models.feature import Feature


def _feature(
    status: str,
    pirate_state: str = "Disabled",
    defender_state: str = "Active",
) -> Feature:
    return Feature(
        id=99,
        name="Example",
        pirate_state=pirate_state,
        defender_state=defender_state,
        scope="Test",
        status=status,
        locked=False,
        desc="Example feature",
    )


def test_feature_card_border_is_red_for_pirate_state() -> None:
    assert "border-red-500" in _feature_card_classes(_feature("Disabled"))


def test_feature_card_border_is_green_for_defender_state() -> None:
    assert "border-emerald-500" in _feature_card_classes(_feature("Active"))
