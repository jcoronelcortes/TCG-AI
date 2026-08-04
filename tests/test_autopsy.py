"""Tests of autopsy v2 (step 5 of the jul 2026 plan): the loss MODE
classifier. The prize convention is the one used in the rest of utils/autopsy.py: a
None entry in prize is a prize that player has STILL to take."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from autopsy import clasificar_derrota


def _obs_final(op_prize_restantes, my_active, my_bench, mi_deck):
    """A minimal terminal observation for the classifier (seat 0)."""
    yo = {
        "active": [my_active] if my_active else [None],
        "bench": my_bench,
        "deckCount": mi_deck,
        "prize": [None] * 6,
    }
    op = {
        "active": [{"id": 37}],
        "bench": [],
        "deckCount": 30,
        "prize": [None] * op_prize_restantes + [{"id": 1}] * (6 - op_prize_restantes),
    }
    return {"current": {"players": [yo, op], "yourIndex": 0, "result": 1}}


def test_loss_on_prizes():
    obs = _obs_final(op_prize_restantes=0,
                     my_active={"id": 920}, my_bench=[{"id": 92}], mi_deck=20)
    assert clasificar_derrota(obs, asiento=0, result="pierde") == "premios"


def test_loss_by_bench_out():
    # The opponent still had prizes pending: the cause is running out of Pokemon.
    obs = _obs_final(op_prize_restantes=3,
                     my_active=None, my_bench=[None, None], mi_deck=20)
    assert clasificar_derrota(obs, asiento=0, result="pierde") == "bench_out"


def test_loss_by_deckout():
    obs = _obs_final(op_prize_restantes=3,
                     my_active={"id": 920}, my_bench=[], mi_deck=0)
    assert clasificar_derrota(obs, asiento=0, result="pierde") == "deckout"


def test_bench_out_gana_a_deckout():
    # An empty board AND the deck at 0 with prizes pending: the KO that swept the
    # board is the proximate cause.
    obs = _obs_final(op_prize_restantes=1,
                     my_active=None, my_bench=[], mi_deck=0)
    assert clasificar_derrota(obs, asiento=0, result="pierde") == "bench_out"


def test_prizes_dominates_deckout():
    # The opponent completed their prizes in a game that also left us at 0
    # deck: the loss is on prizes (the deck-out never got to happen).
    obs = _obs_final(op_prize_restantes=0,
                     my_active={"id": 920}, my_bench=[], mi_deck=0)
    assert clasificar_derrota(obs, asiento=0, result="pierde") == "premios"


def test_the_boundary_is_classified_outright():
    obs = _obs_final(op_prize_restantes=2,
                     my_active={"id": 920}, my_bench=[], mi_deck=10)
    assert clasificar_derrota(obs, asiento=0, result="limite") == "limite"


def test_a_broken_observation_does_not_raise():
    assert clasificar_derrota({}, asiento=0, result="pierde") == "desconocido"
    assert clasificar_derrota(None, asiento=0, result="pierde") == "desconocido"
