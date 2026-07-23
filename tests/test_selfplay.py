"""Smoke test del harness de self-play (utils/selfplay.py).

Rapido a proposito (2 partidas, ~0.1s): valida que el driver juega partidas
COMPLETAS con dos instancias independientes de main.py y que la estadistica
basica es coherente. Las evaluaciones reales se corren a mano:

    python utils/selfplay.py --partidas 200 --base HEAD~1
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils import selfplay as sp


@pytest.fixture(scope="module")
def instancias():
    a = sp.cargar_agente(ROOT / "main.py", "smoke_agente_a")
    b = sp.cargar_agente(ROOT / "main.py", "smoke_agente_b")
    return a, b


def test_partida_completa_espejo(instancias):
    a, b = instancias
    r = sp.jugar_partida(a, b)
    assert r["ganador"] in (0, 1), f"partida sin ganador: {r}"
    assert r["result"] == r["ganador"], "sin forfeits en el espejo"
    assert 0 < r["pasos"] < sp.MAX_PASOS
    assert r["primer_jugador"] in (0, 1)


def test_torneo_minimo_alterna_asientos(instancias):
    a, b = instancias
    stats = sp.torneo(a, b, 2)
    assert stats["candidato"] + stats["base"] + stats["limites"] == 2
    # una partida con el candidato en cada asiento
    assert stats["cand_j0"][1] + stats["limites"] >= 1 or stats["cand_j0"][1] == 1
    assert stats["cand_j0"][1] + stats["cand_j1"][1] + stats["limites"] == 2
    assert stats["errores_candidato"] == 0 and stats["errores_base"] == 0


def test_wilson_95():
    lo, hi = sp.wilson_95(50, 100)
    assert lo < 0.5 < hi
    assert 0.40 < lo < 0.45 and 0.55 < hi < 0.60
    assert sp.wilson_95(0, 0) == (0.0, 1.0)
    lo0, _ = sp.wilson_95(0, 20)
    assert lo0 == 0.0
