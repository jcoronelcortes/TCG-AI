"""Both seats of the permutation probe were our own list.

`over_games` called `battle_start(list(deck), list(deck))`. Every figure this
probe has ever published --- the 0.63-0.67 % of order-dependent decisions that
three night plans quote as the known level --- was measured with our deck
facing itself.

The triage of 10 August is what surfaced it. Of 1 603 order-dependent decisions
over 2 000 games, 73 were the ATTACK-vs-RETREAT fork the plans single out as
strategic, and the opposing active in them was Hydrapple ex, Tapu Bulu, Applin,
Dipplin --- our own cards, because in a mirror there is nothing else it could
be.

Measured at 60 games per condition once `--opponent` existed:

    mirror                 0.66 %      (reproduces the historical figure)
    crustle_wall_9         4.93 %
    alakazam_1             5.32 %
    marnie_grimmsnarl_1    6.18 %

Seven to nine times more often, consistent across three archetypes. The mirror
is the outlier, and it is the configuration the headline was measured in.

These tests pin the flag and, deliberately, pin the DEFAULT too: the mirror has
to stay the default, because it is what the published numbers mean and a
silently changed default makes the next one incomparable with them.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "utils" / "permutation_probe.py"


def run_probe(*args):
    return subprocess.run(
        [sys.executable, str(PROBE), *args],
        cwd=str(ROOT), capture_output=True, text=True, timeout=900,
    )


def test_the_default_is_still_the_mirror_and_says_so():
    """The published 0.63-0.67 % has to keep meaning what it meant."""
    done = run_probe("--games", "2")
    assert done.returncode in (0, 1), done.stderr
    assert "mirror" in done.stdout, "el espejo dejo de anunciarse como tal"


def test_it_can_be_pointed_at_a_real_list():
    real = ROOT / "deck" / "real_opponents" / "crustle_wall_9.csv"
    if not real.is_file():
        pytest.skip("this corpus has no crustle_wall_9")
    done = run_probe("--games", "2", "--opponent", str(real))
    assert done.returncode in (0, 1), done.stderr
    assert "crustle_wall_9" in done.stdout, \
        "no dice contra que juega: un numero sin su condicion"
    assert "mirror" not in done.stdout


def test_a_deck_that_is_not_there_fails_instead_of_falling_back():
    """Specificity, and the one that matters most here.

    A typo in the path must NOT quietly measure the mirror. That would report
    the low number under a real deck's name, which is worse than crashing:
    it is the shape of finding that gets believed.
    """
    done = run_probe("--games", "1", "--opponent", "deck/no_such_deck.csv")
    assert done.returncode != 0
    assert "decisions compared" not in done.stdout
