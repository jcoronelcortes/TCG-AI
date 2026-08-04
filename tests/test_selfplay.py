"""Smoke test of the self-play harness (utils/selfplay.py).

Deliberately fast (2 games, ~0.1s): it validates that the driver plays COMPLETE
games with two independent instances of main.py and that the basic
statistics are coherent. The real evaluations are run by hand:

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
    a = sp.load_agent(ROOT / "main.py", "smoke_agente_a")
    b = sp.load_agent(ROOT / "main.py", "smoke_agente_b")
    return a, b


def test_a_full_mirror_game(instancias):
    a, b = instancias
    r = sp.play_game(a, b)
    assert r["ganador"] in (0, 1), f"partida sin ganador: {r}"
    assert r["result"] == r["ganador"], "sin forfeits en el espejo"
    assert 0 < r["pasos"] < sp.MAX_STEPS
    assert r["primer_jugador"] in (0, 1)


def test_torneo_minimo_alterna_asientos(instancias):
    a, b = instancias
    stats = sp.torneo(a, b, 2)
    assert stats["candidato"] + stats["base"] + stats["limites"] == 2
    # one game with the candidate in each seat
    assert stats["cand_j0"][1] + stats["limites"] >= 1 or stats["cand_j0"][1] == 1
    assert stats["cand_j0"][1] + stats["cand_j1"][1] + stats["limites"] == 2
    assert stats["errores_candidato"] == 0 and stats["errores_base"] == 0


def test_a_game_against_the_generic_bot(instancias):
    # The generic bot pilots the harvested opposing deck: the game finishes and
    # NOBODY loses by forfeit (every choice of the bot is legal).
    a, _ = instancias
    path = ROOT / "deck" / "rivales" / "crustle_kangaskhan.csv"
    if not path.exists():
        pytest.skip("mazo rival no cosechado (utils/harvest_opponent_deck.py)")
    from utils.opponent_bot import BotRival
    r = sp.play_game(a, BotRival(), deck1=sp.read_deck(path))
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
# The prize differential: the RESOLUTION metric
# --------------------------------------------------------------------------
# The winrate against the generic bot is saturated (>93% weighted), so it
# cannot arbitrate a change. The prizes do grade it: a 4-6 loss and a 0-6 one
# are the same line on the scoreboard and a very different thing.

def test_the_game_reports_the_prizes_taken(instancias):
    a, b = instancias
    r = sp.play_game(a, b)
    p = r["premios_tomados"]
    assert p[0] is not None and p[1] is not None, (
        "los premios deben poder leerse del tablero final")
    assert 0 <= p[0] <= 6 and 0 <= p[1] <= 6
    # At most 6 prizes are won, and the winner cannot have taken
    # fewer than the loser.
    if r["ganador"] is not None:
        assert p[r["ganador"]] >= p[1 - r["ganador"]]


def test_el_pico_no_se_toma_de_battle_start(instancias):
    """Regression of the bug that made the differential identically 0.

    `battle_start` returns the board BEFORE the prizes are dealt: both
    piles are 0 there. Taking that as the initial value, `tomados` came out 0 in every
    game and every matchup marked +0.00. The peak is discovered
    during the game.
    """
    assert sp._prizes_taken([0, 0], [4, 5]) == [None, None], (
        "sin pico valido no se debe inventar un 0: es 'no medido'")
    assert sp._prizes_taken([6, 6], [4, 5]) == [2, 1]
    # The pile only goes down; an ending above the peak cannot give a negative.
    assert sp._prizes_taken([6, 6], [6, 6]) == [0, 0]


def test_the_tournament_aggregates_prizes_per_agent(instancias):
    a, b = instancias
    stats = sp.torneo(a, b, 2)
    assert stats["partidas_con_premios"] == 2
    pc, pb, dif = sp.prizes_per_game(stats)
    assert pc is not None and pb is not None
    assert abs(dif - (pc - pb)) < 1e-9
    # In the mirror both sides are the same agent: the differential cannot
    # be systematic, only the noise of two games.
    assert 0 <= pc <= 6 and 0 <= pb <= 6
