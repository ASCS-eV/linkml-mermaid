"""Shared fixtures for linkml_mermaid package tests.

All fixtures use the self-contained test_schema.yaml — no dependency on
any downstream schema.  This makes the package tests portable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from linkml_mermaid import SchemaReader, StateDiagramConfig

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def test_schema_path() -> Path:
    return FIXTURES_DIR / "test_schema.yaml"


@pytest.fixture
def reader(test_schema_path: Path) -> SchemaReader:
    return SchemaReader(test_schema_path)


@pytest.fixture
def sample_states() -> list[dict]:
    """Three traffic-light states as plain dicts — the format that
    mapping functions must accept alongside Pydantic objects."""
    return [
        {
            "id": "RED",
            "display_name": "Red",
            "is_initial": True,
            "is_terminal": False,
            "color": "Red",
        },
        {
            "id": "YELLOW",
            "display_name": "Yellow",
            "is_initial": False,
            "is_terminal": False,
            "color": "Yellow",
        },
        {
            "id": "GREEN",
            "display_name": "Green",
            "is_initial": False,
            "is_terminal": False,
            "color": "Green",
        },
    ]


@pytest.fixture
def sample_transitions() -> list[dict]:
    return [
        {
            "name": "Go",
            "from_state": "RED",
            "to_state": "GREEN",
            "default_actor": "[Timer]",
            "guards": ["TIMER_EXPIRED"],
        },
        {
            "name": "Caution",
            "from_state": "GREEN",
            "to_state": "YELLOW",
            "default_actor": "[Timer]",
            "guards": [],
        },
        {
            "name": "Stop",
            "from_state": "YELLOW",
            "to_state": "RED",
            "default_actor": "[Timer]",
            "guards": [],
        },
    ]


@pytest.fixture
def sample_guards() -> list[dict]:
    return [
        {
            "id": "TIMER_EXPIRED",
            "display_name": "{Timer expired}",
            "description": "Minimum phase duration has elapsed",
        },
        {
            "id": "SENSOR_TRIGGERED",
            "display_name": "{Sensor triggered}",
            "description": "Vehicle or pedestrian sensor activated",
        },
    ]


@pytest.fixture
def traffic_config() -> StateDiagramConfig:
    """Config that maps test schema slots to Mermaid concepts."""
    return StateDiagramConfig(
        state_id_slot="id",
        state_label_slot="display_name",
        state_initial_slot="is_initial",
        state_terminal_slot="is_terminal",
        state_enum_name="TrafficLightState",
        transition_from_slot="from_state",
        transition_to_slot="to_state",
        transition_label_slot="name",
        transition_actor_slot="default_actor",
        transition_guards_slot="guards",
        guard_id_slot="id",
        guard_label_slot="display_name",
    )
