from datetime import date
from pathlib import Path

import pytest

from smw.config.season import Season

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def season() -> Season:
    # Small trial count keeps simulation tests fast; deterministic seed throughout.
    return Season(
        year=2026,
        window_start=date(2026, 5, 1),
        window_end=date(2026, 9, 7),
        seed=42,
        monte_carlo_trials=2000,
    )

from smw.config.groups import Group, PlayerPicks


def _picks(username: str, ranked: list[str], dark: list[str]) -> PlayerPicks:
    return PlayerPicks(username=username, ranked=tuple(ranked), dark_horses=tuple(dark))


@pytest.fixture
def group() -> Group:
    # Films are generic titles M01..M18 so tests control the finish order exactly.
    return Group(
        group_id="testers",
        display_name="Test League",
        players={
            "alice": _picks("alice",
                            [f"M{i:02d}" for i in range(1, 11)], ["M15", "M16", "M17"]),
            "bob": _picks("bob",
                          [f"M{i:02d}" for i in range(10, 0, -1)], ["M15", "M18", "M14"]),
            "carol": _picks("carol",
                            ["M02", "M01", "M03", "M05", "M04", "M06", "M08", "M07", "M10", "M09"],
                            ["M11", "M12", "M13"]),
        },
    )
