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
