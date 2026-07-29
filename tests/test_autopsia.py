"""Tests de la autopsia v2 (paso 5 plan jul 2026): clasificador del MODO de
derrota. La convencion de premios es la del resto de utils/autopsia.py: una
entrada None en prize es un premio que a ese jugador AUN LE FALTA cobrar."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from autopsia import clasificar_derrota


def _obs_final(op_prize_restantes, mi_activo, mi_banca, mi_deck):
    """Observacion terminal minima para el clasificador (asiento 0)."""
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
    # El rival aun tenia premios pendientes: la causa es quedarse sin Pokemon.
    obs = _obs_final(op_prize_restantes=3,
                     mi_activo=None, mi_banca=[None, None], mi_deck=20)
    assert clasificar_derrota(obs, asiento=0, resultado="pierde") == "bench_out"


def test_derrota_por_deckout():
    obs = _obs_final(op_prize_restantes=3,
                     mi_activo={"id": 920}, mi_banca=[], mi_deck=0)
    assert clasificar_derrota(obs, asiento=0, resultado="pierde") == "deckout"


def test_bench_out_gana_a_deckout():
    # Tablero vacio Y mazo a 0 con premios pendientes: el KO que barrio el
    # tablero es la causa proxima.
    obs = _obs_final(op_prize_restantes=1,
                     mi_activo=None, mi_banca=[], mi_deck=0)
    assert clasificar_derrota(obs, asiento=0, resultado="pierde") == "bench_out"


def test_premios_domina_a_deckout():
    # Rival completo sus premios en una partida que ademas nos dejo a 0 de
    # mazo: la derrota es por premios (el deck-out nunca llego a ejecutarse).
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
