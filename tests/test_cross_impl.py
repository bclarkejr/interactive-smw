import json
import shutil
import subprocess
import pytest
from smw.config.groups import PlayerPicks
from smw.score.rules import score_player
from tests.conftest import FIXTURES

VECTORS = json.loads((FIXTURES / "scoring_vectors.json").read_text())

@pytest.mark.parametrize("case", VECTORS, ids=[c["name"] for c in VECTORS])
def test_python_scoring_matches_vector(case):
    picks = PlayerPicks("v", tuple(case["ranked"]), tuple(case["dark_horses"]))
    assert score_player(picks, case["finish"]) == case["expected"]

@pytest.mark.skipif(shutil.which("node") is None,
                    reason="node required for the client-side half of §12.2's "
                           "shared vector — install node; do not delete this test")
def test_js_scoring_matches_vector():
    result = subprocess.run(
        ["node", str(FIXTURES.parent / "run_js_vectors.mjs")],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
