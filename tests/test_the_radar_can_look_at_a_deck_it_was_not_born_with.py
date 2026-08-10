"""The collision radar had `deck/opponents` written into its body.

For three months the radar could only see the 19 synthetic decks. That was fine
while the question was "do two sibling matchups disagree", because a canonical
situation needs a deck whose engine is known. It stopped being fine the night
the question became "which REAL list is the one where the situation collapses":
the tool built for exactly that question could not be pointed at the lists.

These tests pin the flag that fixed it, and they pin it in both directions,
because a `--opponents` that silently falls back to the default is worse than no
flag at all -- it answers the old question while the report says it answered the
new one.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RADAR = ROOT / "utils" / "collision_radar.py"


def run_radar(*args):
    return subprocess.run(
        [sys.executable, str(RADAR), *args],
        cwd=str(ROOT), capture_output=True, text=True, timeout=600,
    )


def test_the_default_is_still_the_synthetic_decks():
    """Nobody's existing command line changes meaning."""
    done = run_radar("--games", "1", "--only", "cornerstone_cubchoo")
    assert done.returncode == 0, done.stderr
    assert "cornerstone_cubchoo" in done.stdout


def test_it_measures_a_folder_it_is_pointed_at():
    """Sensitivity: the real lists are reachable, and they are what it names."""
    real = ROOT / "deck" / "real_opponents"
    if not real.is_dir():
        pytest.skip("there is no deck/real_opponents in this checkout")
    alguno = next((p.stem for p in sorted(real.glob("*.csv"))
                   if p.stem != "pesos"), None)
    if alguno is None:
        pytest.skip("deck/real_opponents has no deck")
    done = run_radar("--games", "1", "--opponents", "deck/real_opponents",
                     "--only", alguno)
    assert done.returncode == 0, done.stderr
    assert alguno in done.stdout


def test_an_auxiliary_csv_is_skipped_and_not_read_as_a_deck():
    """`pesos.csv` lives in that folder and is not 60 ids.

    Reading it as a deck crashes AFTER every good matchup has been played,
    which is the most expensive moment to discover it.
    """
    real = ROOT / "deck" / "real_opponents"
    if not (real / "pesos.csv").is_file():
        pytest.skip("this corpus carries no pesos.csv")
    done = run_radar("--games", "1", "--opponents", "deck/real_opponents",
                     "--only", "pesos")
    assert done.returncode == 2
    assert "no deck to measure" in done.stdout + done.stderr


def test_a_folder_that_is_not_there_fails_loudly():
    """Specificity: a typo in the path must not quietly measure the default."""
    done = run_radar("--games", "1", "--opponents", "deck/no_such_folder")
    assert done.returncode == 2
    assert "no_such_folder" in done.stdout + done.stderr
    assert "COLLISION RADAR" not in done.stdout
