"""Tests for GUI presentation helpers."""

from __future__ import annotations

import pytest

from src.gui import (
    _feature_card_classes,
    _feature_detail_markdown,
    _feature_toggle_visible,
    state,
)
from src.models.feature import FEATURE_DETAILS, INITIAL_FEATURES, Feature


def _feature(
    status: str,
    pirate_state: str = "Disabled",
    defender_state: str = "Active",
    feature_id: int = 99,
) -> Feature:
    return Feature(
        id=feature_id,
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


def test_faceit_not_installed_card_border_is_red() -> None:
    feature = _feature("Not Installed", defender_state="N/A", feature_id=9)

    assert "border-red-500" in _feature_card_classes(feature)


def test_faceit_not_installed_hides_toggle() -> None:
    feature = _feature("Not Installed", defender_state="N/A", feature_id=9)

    assert _feature_toggle_visible(feature) is False


def test_hidden_toggle_feature_hides_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    feature = _feature("Disabled", feature_id=7)
    monkeypatch.setattr(state, "hidden_toggle_feature_ids", {7})

    assert _feature_toggle_visible(feature) is False


def test_all_initial_features_have_detail_content() -> None:
    assert {feature.id for feature in INITIAL_FEATURES} == set(FEATURE_DETAILS)


def test_feature_detail_markdown_has_required_sections() -> None:
    feature = INITIAL_FEATURES[2]

    markdown = _feature_detail_markdown(feature)

    assert "## 🧪 Feature Explanation" in markdown
    assert "## 📡 Hardware/Software Verification" in markdown
    assert "## 🔧 Manual Enablement" in markdown
    assert "## 🛠️ Manual Disablement" in markdown
    assert "Win32_DeviceGuard" in markdown
