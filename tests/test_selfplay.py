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


def test_partida_vs_bot_rival(instancias):
    # El bot generico pilota el mazo rival cosechado: la partida termina y
    # NADIE pierde por forfeit (todas las elecciones del bot son legales).
    a, _ = instancias
    ruta = ROOT / "deck" / "rivales" / "crustle_kangaskhan.csv"
    if not ruta.exists():
        pytest.skip("mazo rival no cosechado (utils/cosechar_deck_rival.py)")
    from utils.bot_rival import BotRival
    r = sp.jugar_partida(a, BotRival(), deck1=sp.leer_deck(ruta))
    assert r["ganador"] in (0, 1), f"partida sin ganador: {r}"
    assert not str(r["result"]).startswith("error"), (
        f"forfeit inesperado: {r}")


def test_wilson_95():
    lo, hi = sp.wilson_95(50, 100)
    assert lo < 0.5 < hi
    assert 0.40 < lo < 0.45 and 0.55 < hi < 0.60
    assert sp.wilson_95(0, 0) == (0.0, 1.0)
    lo0, _ = sp.wilson_95(0, 20)
    assert lo0 == 0.0


# --------------------------------------------------------------------------
# Diferencial de premios: la metrica de RESOLUCION
# --------------------------------------------------------------------------
# El winrate contra el bot generico esta saturado (>93% ponderado), asi que no
# puede arbitrar un cambio. Los premios si graduan: una derrota 4-6 y una 0-6
# son la misma linea en el marcador y muy distinta cosa.

def test_la_partida_reporta_premios_tomados(instancias):
    a, b = instancias
    r = sp.jugar_partida(a, b)
    p = r["premios_tomados"]
    assert p[0] is not None and p[1] is not None, (
        "los premios deben poder leerse del tablero final")
    assert 0 <= p[0] <= 6 and 0 <= p[1] <= 6
    # Se ganan 6 premios como maximo, y el ganador no puede haber cobrado
    # menos que el perdedor.
    if r["ganador"] is not None:
        assert p[r["ganador"]] >= p[1 - r["ganador"]]


def test_el_pico_no_se_toma_de_battle_start(instancias):
    """Regresion del bug que hacia el diferencial identicamente 0.

    `battle_start` devuelve el tablero ANTES de repartir premios: los dos
    montones valen 0 ahi. Tomandolo como inicial, `tomados` salia 0 en todas
    las partidas y todos los matchups marcaban +0.00. El pico se descubre
    durante la partida.
    """
    assert sp._premios_tomados([0, 0], [4, 5]) == [None, None], (
        "sin pico valido no se debe inventar un 0: es 'no medido'")
    assert sp._premios_tomados([6, 6], [4, 5]) == [2, 1]
    # El monton solo baja; un final por encima del pico no puede dar negativo.
    assert sp._premios_tomados([6, 6], [6, 6]) == [0, 0]


def test_el_torneo_agrega_premios_por_agente(instancias):
    a, b = instancias
    stats = sp.torneo(a, b, 2)
    assert stats["partidas_con_premios"] == 2
    pc, pb, dif = sp.premios_por_partida(stats)
    assert pc is not None and pb is not None
    assert abs(dif - (pc - pb)) < 1e-9
    # En el espejo ambos lados son el mismo agente: el diferencial no puede
    # ser sistematico, solo ruido de dos partidas.
    assert 0 <= pc <= 6 and 0 <= pb <= 6
