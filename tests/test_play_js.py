import shutil
import subprocess

import pytest

from tests.conftest import FIXTURES


@pytest.mark.skipif(shutil.which("node") is None,
                    reason="node required for the client-side play-along tests — "
                           "install node; do not delete this test")
def test_play_view_composition_and_join_validation():
    result = subprocess.run(
        ["node", "--test", str(FIXTURES.parent / "play_view.test.mjs"),
         str(FIXTURES.parent / "join_validate.test.mjs")],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
