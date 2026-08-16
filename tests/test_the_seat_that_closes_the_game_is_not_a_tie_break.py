"""A un premio de ganar, el asiento se decidia por trescientos puntos de adorno.

Escenario (`records/registro_013_pasos_156_hasta_174.json`, ultimo menu --
episodio 93579160 vs una lista de Alakazam, turno 13, PERDIDA; el fixture es esa
promocion forzada):

    NOSOTROS (1 premio)                    RIVAL (1 premio)
    activo  -- acaban de noquearlo         activo  Alakazam **140**/140, 1 energia
    banca   Meowth ex 0e
            **Meganium 2e** (un Grass
              fisico, x2 Wild Growth)
            Meowth ex 0e
            Fezandipiti ex 0e
            Dipplin 2e
    mano    Lana's Aid, Boss's Orders, Dawn, Chikorita,
            3x Teal Mask Ogerpon ex, 2x Ultra Ball   (NI UN Grass)
    descarte  nueve Basic Grass Energy

Su Alakazam vale UN premio y nuestro monton es de uno: ese cuerpo ES el resto de
nuestra cuenta. El Meganium esta a UNA carta de Solar Beam -- lleva un Grass
fisico, que bajo su propio Wild Growth son dos de los cuatro que cuesta -- y la
Lana's Aid de la mano saca ese Grass del descarte, que es la ruta (b) de
`_promote_setup_ko_attacker`. Sus 140 entierran al Alakazam de 140: la promocion
resuelve al final de SU turno, el nuestro va primero, y ese noqueo se lleva el
ultimo premio antes de que su respuesta exista.

QUE ENCONTRO ESTE TABLERO, y no es la eleccion. El selector nombra al Meganium y
el arbol de hoy lo sube -- desde `9e0b8ac`, "el frente lo toma el cuerpo que
puede atacar". Lo que encontro es DE QUE DEPENDIA esa eleccion:

    Meganium        9500 (finalizador) + 350 de desempate generico  = 9850
    Fezandipiti ex  9450 (`PROMO_LAST_STAND`) + 100                 = 9550

Trescientos puntos. El desempate que los produce ordena "a cuantas cargas estas"
y "cuantos premios cuestas" y esta acotado a 0..450 justamente porque es un
adorno: su propio comentario dice que se queda "far below any decisive rule". La
jugada que gana la partida se estaba decidiendo dentro de esa banda.

Y `PROMO_KO_BONUS` ya tiene escrito por que eso no vale, para el cuerpo que
noquea HOY: va +20000 "so that it is a GUARANTEE and does not depend on the
knocker scoring higher base than the tank". El finalizador a una carga de
distancia, en nuestro propio match point, es esa misma jugada un turno antes y no
tenia ninguna garantia. Peor: los tres descuentos que vienen despues pueden
hundirlo, y los tres son argumentos sobre sobrevivir a una respuesta que no va a
llegar -- el peaje del Tera (-500, que dejaria a un Teal Mask Ogerpon ex
finalizador en 9000, POR DEBAJO del last stand), el doomed de match point (-6000,
cuya exencion pregunta por `_promo_kos_op`, la energia de HOY, que es justo lo que
este cuerpo aun no tiene) y el frente entre los que noquean (-1200).

`THE_SEAT_THAT_CLOSES_THE_GAME_IS_A_GUARANTEE` lo sube a `PROMO_CLOSER_SEAT`
(15000) y lo exime de los tres.

LO QUE ESTE TEST NO PUEDE DECIR, y hay que leerlo antes que nada: la ELECCION no
cambia en este tablero. Con la bandera quitada el Meganium sigue ganando, por
300. El censo (`utils/census_the_seat_that_closes_the_game.py`) es el que dice
cuanto vale esto: **1 de 7** promociones forzadas del corpus local es este
tablero y su margen es 300 (dentro de la banda del adorno); **0 flips** sobre las
3 580 decisiones del corpus congelado; **0 de 584** promociones en 500 partidas
de self-play vs alakazam_1. Es decir: no rompe nada y no lo mide ningun winrate.
Lo que se adopta es la garantia, no un punto de victoria.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
import ptcg.turn.options.card as cardmod
from golden_corpus import reset_agent
from ptcg.cards.scoring import (PROMO_CLOSER_SEAT, PROMO_KO_BONUS,
                                PROMO_LAST_STAND)

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_our_match_point_the_seat_that_closes_the_game_step174.json")

MEGANIUM = m.Meganium
MEOWTH = m.Meowth_ex
FEZ = m.Fezandipiti_ex
DIPPLIN = m.Dipplin
ALAKAZAM = 743

# La cota superior del desempate generico de supervivientes en
# `ptcg/turn/options/card.py`: `300 - 100 * pasos` (pasos >= 0) mas 150 si el
# cuerpo cuesta un premio. Un margen que quepa aqui es un margen decidido por
# adornos, que es exactamente lo que este tablero denuncia.
TIE_BREAK_BAND = 450


@pytest.fixture(autouse=True)
def reset_main_state():
    reset_agent(m)
    yield
    reset_agent(m)
    cardmod.THE_SEAT_THAT_CLOSES_THE_GAME_IS_A_GUARANTEE = True


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _bench_index(obs, card_id):
    """El indice del menu cuya opcion apunta a `card_id` en nuestra banca."""
    cur = obs["current"]
    bench = cur["players"][cur["yourIndex"]]["bench"]
    for i, opt in enumerate(obs["select"]["option"]):
        body = bench[opt["index"]]
        if body and body["id"] == card_id:
            return i
    raise AssertionError(f"{card_id} no esta en este menu")


def _scores(obs, flag=True):
    """La puntuacion de cada opcion, espiando `score_option`.

    Es la unica funcion por la que pasa cada opcion con el contexto ya
    construido, asi que lo que se lee aqui es lo que el scorer vio.
    """
    out = []
    original = m.score_option

    def spy(ctx, option, score):
        result = original(ctx, option, score)
        out.append(result)
        return result

    prev = cardmod.THE_SEAT_THAT_CLOSES_THE_GAME_IS_A_GUARANTEE
    cardmod.THE_SEAT_THAT_CLOSES_THE_GAME_IS_A_GUARANTEE = flag
    m.score_option = spy
    try:
        m.agent(obs)
    finally:
        m.score_option = original
        cardmod.THE_SEAT_THAT_CLOSES_THE_GAME_IS_A_GUARANTEE = prev
    return out


# ---------------------------------------------------------------------------
# 1. El escenario: sin esto el test no mide nada
# ---------------------------------------------------------------------------

def test_the_fixture_is_our_match_point_with_one_reachable_finisher():
    obs = _obs()
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    # Promocion FORZADA: el puesto activo esta vacio y el menu solo ofrece banca.
    assert mine["active"] == []
    assert {opt["type"] for opt in obs["select"]["option"]} == {int(m.OptionType.CARD)}

    # Nuestro match point: un premio, y su activo lo paga entero.
    assert len(mine["prize"]) == 1
    assert theirs["active"][0]["id"] == ALAKAZAM
    assert theirs["active"][0]["hp"] == 140

    # El Meganium esta a UNA carga de Solar Beam y nadie mas lleva energia util.
    meganium = next(b for b in mine["bench"] if b and b["id"] == MEGANIUM)
    assert len(meganium["energies"]) == 2
    assert m.ATTACK_ENERGY_REQ[MEGANIUM] == 4

    # Y la carga no esta en la mano: lo unico que la alcanza es la Lana's Aid
    # sobre el descarte, que es la ruta (b) de `_promote_setup_ko_attacker`.
    assert all(c["id"] != m.Basic_Grass_Energy for c in mine["hand"])
    assert any(c["id"] == m.Lanas_Aid for c in mine["hand"])
    assert sum(1 for c in mine["discard"]
               if c["id"] == m.Basic_Grass_Energy) >= 1


# ---------------------------------------------------------------------------
# 2. La decision, y de que depende
# ---------------------------------------------------------------------------

def test_it_promotes_the_meganium_that_takes_the_last_prize():
    obs = _obs()
    assert m.agent(obs) == [_bench_index(obs, MEGANIUM)]


def test_without_the_rule_the_game_hangs_on_a_generic_tie_break():
    """El control: con la bandera quitada la eleccion es la misma y el margen
    cabe entero dentro del desempate de adornos. Esto es lo que se corrige."""
    obs = _obs()
    scores = _scores(obs, flag=False)
    finisher = scores[_bench_index(obs, MEGANIUM)]
    rival = max(scores[_bench_index(obs, other)] for other in (MEOWTH, FEZ, DIPPLIN))
    assert finisher > rival, scores          # la eleccion ya era la correcta...
    assert 0 < finisher - rival <= TIE_BREAK_BAND, scores   # ...y por nada


def test_with_the_rule_the_seat_stops_depending_on_decorations():
    obs = _obs()
    scores = _scores(obs, flag=True)
    finisher = scores[_bench_index(obs, MEGANIUM)]
    rival = max(scores[_bench_index(obs, other)] for other in (MEOWTH, FEZ, DIPPLIN))
    assert finisher >= PROMO_CLOSER_SEAT, scores
    assert finisher - rival > TIE_BREAK_BAND, scores


# ---------------------------------------------------------------------------
# 3. La banda: la aritmetica es la especificacion
# ---------------------------------------------------------------------------

def test_the_closer_seat_clears_every_rung_it_has_to_outrank():
    """POR ENCIMA de todo lo que discute el asiento en esta cadena.

    El peldaño mas alto que compite es el last stand (9450) y encima de el
    todavia puede sumar el desempate de supervivientes (<=450); y por debajo
    quedan los tres descuentos de los que la regla exime al finalizador (-500
    Tera, -6000 doomed de match point, -1200 frente). Con la exencion puesta la
    suma no hace falta, pero la banda tiene que aguantar sin ella.
    """
    assert PROMO_CLOSER_SEAT > PROMO_LAST_STAND + TIE_BREAK_BAND


def test_the_body_that_knocks_out_today_still_has_the_last_word():
    """POR DEBAJO del que noquea HOY.

    Si `_promo_ko_wins_the_game` es cierto, CUALQUIER noqueo del activo rival
    vale el monton entero: el cuerpo que ya puede hacerlo cierra la partida sin
    depender ni de la carga ni del robo, asi que su +20000 no se toca.
    """
    assert PROMO_CLOSER_SEAT < PROMO_KO_BONUS
