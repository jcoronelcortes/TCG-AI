"""Tests of autopsy v2 (step 5 of the jul 2026 plan): the loss MODE
classifier. The prize convention is the one used in the rest of utils/autopsia.py: a
None entry in prize is a prize that player has STILL to take."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from autopsia import clasificar_derrota


def _obs_final(op_prize_restantes, mi_activo, mi_banca, mi_deck):
    """A minimal terminal observation for the classifier (seat 0)."""
    yo = {
        "active": [mi_activo] if mi_activo else [None],
        "bench": mi_banca,
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


def test_derrota_por_premios():
    obs = _obs_final(op_prize_restantes=0,
                     mi_activo={"id": 920}, mi_banca=[{"id": 92}], mi_deck=20)
    assert clasificar_derrota(obs, asiento=0, resultado="pierde") == "premios"


def test_derrota_por_bench_out():
    # The opponent still had prizes pending: the cause is running out of Pokemon.
    obs = _obs_final(op_prize_restantes=3,
                     mi_activo=None, mi_banca=[None, None], mi_deck=20)
    assert clasificar_derrota(obs, asiento=0, resultado="pierde") == "bench_out"


def test_derrota_por_deckout():
    obs = _obs_final(op_prize_restantes=3,
                     mi_activo={"id": 920}, mi_banca=[], mi_deck=0)
    assert clasificar_derrota(obs, asiento=0, resultado="pierde") == "deckout"


def test_bench_out_gana_a_deckout():
    # An empty board AND the deck at 0 with prizes pending: the KO that swept the
    # board is the proximate cause.
    obs = _obs_final(op_prize_restantes=1,
                     mi_activo=None, mi_banca=[], mi_deck=0)
    assert clasificar_derrota(obs, asiento=0, resultado="pierde") == "bench_out"


def test_premios_domina_a_deckout():
    # The opponent completed their prizes in a game that also left us at 0
    # deck: the loss is on prizes (the deck-out never got to happen).
    obs = _obs_final(op_prize_restantes=0,
                     mi_activo={"id": 920}, mi_banca=[], mi_deck=0)
    assert clasificar_derrota(obs, asiento=0, resultado="pierde") == "premios"


def test_limite_se_clasifica_directo():
    obs = _obs_final(op_prize_restantes=2,
                     mi_activo={"id": 920}, mi_banca=[], mi_deck=10)
    assert clasificar_derrota(obs, asiento=0, resultado="limite") == "limite"


def test_observacion_rota_no_lanza():
    assert clasificar_derrota({}, asiento=0, resultado="pierde") == "desconocido"
    assert clasificar_derrota(None, asiento=0, resultado="pierde") == "desconocido"
