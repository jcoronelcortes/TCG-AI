"""La foto de "evolucionable" no se decrementaba al EVOLUCIONAR en el turno.

Escenario (user, episodio 88909907, registro_006 pasos 76-87, turno 6 vs
Marnie's Grimmsnarl ex, GANADA):

    NOSOTROS (inicio del turno 6)                RIVAL
    activo  Teal Mask Ogerpon ex 180/210 3 {G}   activo  Grimmsnarl ex 310/320
    banca   Meowth ex, Dipplin(709), Applin 40,          banca  Morgrem, 2x Impidimp,
            Teal Mask Ogerpon ex 190/210                        Impidimp
    mano    Unfair Stamp, Night Stretcher, ...
    descarte  Dipplin(93 s16), Applin(92 s13), 2 Plantas basicas

Dentro de ESE MISMO turno el agente evoluciono su Applin de banca a Dipplin
(paso 79). En el paso 84 ya no quedaba ningun Applin en juego... y aun asi
jugo la **Night Stretcher para recuperar un Dipplin**: una Fase 1 sin nada
sobre lo que subir y que no se puede bajar a banca. Carta muerta en la mano.
Peor todavia, en el paso 86 jugo el **Unfair Stamp**, que barajo ese Dipplin
de vuelta al mazo: dos cartas gastadas para no cambiar nada del tablero.

Causa raiz -- una sola, compartida por seis decisiones distintas. La foto
`evolvable` se calculaba asi en cinco sitios de main.py:

    evolvable = field_at_turn_start if (not forest and field_at_turn_start)
                else field_counts

La intencion es correcta: sin Forest of Vitality una pre-evolucion solo puede
evolucionar si YA estaba en juego al empezar el turno (no salio este turno).
Pero la foto de inicio es un contador congelado que **nunca se decrementa**
cuando esa misma pre-evo se consume evolucionando. Tras el paso 79 decia
"Applin: 1" con cero Applin sobre la mesa, y con eso dispararon las dos ramas
que produjeron la jugada:

  * `ns->play  dipplin_applin_evolucionable` = 750 -> base 10400 (jugar la NS);
  * `ns->dipplin applin_evolucionable`       = 850 (recuperar el Dipplin),
    por encima de `ns->grass sin_planta_en_mano` = 750 (la Planta, util).

Arreglo (`_evolvable_counts`): la foto pasa a ser la INTERSECCION por especie
-- presente AHORA (`field_counts`) **y** presente al inicio del turno --, que
es exactamente el criterio que ya usaban a mano `_ub_evolve_now_search` y
`_lillie_evolve_now`. Con Forest en mesa sigue mandando la foto actual.

Con el arreglo la NS queda vetada (SCORE_VETO) y el turno juega el Unfair
Stamp con UNA CARTA MAS en la mano; si algo fuerza igualmente el menu de
recuperacion, se trae la Planta basica en vez de la evolucion muerta.

ALCANCE (medido, no estetico): la foto depurada se aplica SOLO a las dos caras
de la Night Stretcher. Aplicarla tambien a los otros cuatro sitios del mismo
idiom (Ultra Ball x2, Poke Pad, Lillie's) costo **-4.7 puntos vs
Crustle/Kangaskhan** (68.6% vs 73.3%, n=1000, fuera del IC95), asi que esos se
quedan con el idiom original. Ver la nota en `_evolvable_counts`.

Medicion del cambio que SI entra (delta dentro de la MISMA corrida, que es lo
unico pareado: el nivel absoluto del bot se mueve ~3 puntos entre corridas):
vs Crustle/Kangaskhan **+2.4** (72.5% vs 70.1%), vs Marnie +0.9 (94.7% vs
93.8%), vs Alakazam -0.4 (99.3% vs 99.7%, saturado al 99%). n=1000 cada uno.
Corpus dorado: 0 flips (el snapshot ya tenia la jugada correcta; este bug la
volteaba).
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

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_ns_no_recupera_evolucion_sin_preevo_step84.json")

APPLIN, DIPPLIN, HYDRAPPLE = m.Applin, m.Dipplin, m.Hydrapple_ex
CHIKORITA, BAYLEEF = m.Chikorita, m.Bayleef
GRASS = m.Basic_Grass_Energy
NIGHT_STRETCHER = m.Night_Stretcher
UNFAIR_STAMP = m.Unfair_Stamp


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cartas_tracking()
    m._cartas_first_scan_done = False
    m._cartas_prizes_identified = False
    m._cartas_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.meganium_in_play = False
    m.forest_in_play = False
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._ub_fez_pending = False
    m._ub_engine_pivot_turn = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _observaciones():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observaciones"])


def _por_paso(obs_list):
    return {o["step"]: o for o in obs_list}


def _carta_de_la_mano(obs, eleccion):
    o = obs["select"]["option"][eleccion[0]]
    assert o["type"] == int(m.OptionType.PLAY), o
    yo = obs["current"]["yourIndex"]
    return obs["current"]["players"][yo]["hand"][o["index"]]["id"]


def _carta_del_descarte(obs, eleccion):
    o = obs["select"]["option"][eleccion[0]]
    assert o["type"] == int(m.OptionType.CARD), o
    yo = obs["current"]["yourIndex"]
    return obs["current"]["players"][yo]["discard"][o["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. La unidad: la foto evolvable
# ---------------------------------------------------------------------------

def test_la_preevo_consumida_por_una_evolucion_deja_de_ser_evolucionable():
    """El Applin del inicio del turno ya es Dipplin: no queda nada que subir."""
    inicio = {APPLIN: 1, CHIKORITA: 1}
    ahora = {DIPPLIN: 1, CHIKORITA: 1}  # el Applin evoluciono este turno
    evolvable = m._evolvable_counts(ahora, inicio, False)
    assert evolvable.get(APPLIN, 0) == 0
    assert evolvable.get(CHIKORITA, 0) == 1


def test_la_preevo_bajada_este_turno_sigue_sin_ser_evolucionable():
    """El otro sentido del filtro (el que ya funcionaba) no se rompe."""
    evolvable = m._evolvable_counts({APPLIN: 1, CHIKORITA: 1},
                                    {CHIKORITA: 1}, False)
    assert evolvable.get(APPLIN, 0) == 0


def test_sin_foto_de_inicio_manda_la_actual():
    """Semantica preservada: foto vacia = sin dato, se usa el campo actual.

    Es como se comportaba el idiom original (`{}` es falsy) y de ahi depende
    el primer menu de cada turno, antes de que la foto se rellene."""
    evolvable = m._evolvable_counts({APPLIN: 1}, {}, False)
    assert evolvable.get(APPLIN, 0) == 1


def test_con_forest_manda_la_foto_actual():
    """Forest of Vitality levanta la restriccion: vale lo que hay AHORA."""
    evolvable = m._evolvable_counts({APPLIN: 2}, {APPLIN: 1}, True)
    assert evolvable.get(APPLIN, 0) == 2


def test_varias_copias_solo_pierde_la_que_evoluciono():
    """Con dos Applin al inicio y uno evolucionado, queda UNO evolucionable."""
    evolvable = m._evolvable_counts({APPLIN: 1, DIPPLIN: 1}, {APPLIN: 2}, False)
    assert evolvable.get(APPLIN, 0) == 1


# ---------------------------------------------------------------------------
# 2. El turno real
# ---------------------------------------------------------------------------

def test_paso84_no_se_juega_la_night_stretcher_por_una_preevo_fantasma():
    obs = _por_paso(_observaciones())
    m.agent(obs[76])                       # fija la foto de inicio (con Applin)
    eleccion = m.agent(obs[84])            # menu principal tras evolucionar
    jugada = _carta_de_la_mano(obs[84], eleccion)
    assert jugada != NIGHT_STRETCHER, (
        "la Night Stretcher recupera un Dipplin sin Applin sobre el que subir")
    assert jugada == UNFAIR_STAMP


def test_paso84_el_unfair_stamp_se_juega_con_la_mano_entera():
    """La NS ya no se cuela DELANTE del Stamp, que rehace 4 cartas y no 3."""
    obs = _por_paso(_observaciones())
    m.agent(obs[76])
    yo = obs[84]["current"]["yourIndex"]
    assert len(obs[84]["current"]["players"][yo]["hand"]) == 4
    eleccion = m.agent(obs[84])
    assert _carta_de_la_mano(obs[84], eleccion) == UNFAIR_STAMP


def test_paso85_si_se_llega_al_menu_se_recupera_la_planta_no_el_dipplin():
    """Segunda linea de defensa: el FETCH tampoco elige la evolucion muerta."""
    obs = _por_paso(_observaciones())
    m.agent(obs[76])
    m.agent(obs[84])
    eleccion = m.agent(obs[85])
    recuperada = _carta_del_descarte(obs[85], eleccion)
    assert recuperada != DIPPLIN
    assert recuperada == GRASS


def test_paso84_el_veto_no_depende_del_descarte_sino_del_campo():
    """El Applin del DESCARTE no rehabilita nada: no esta en juego."""
    obs = _por_paso(_observaciones())
    yo = obs[85]["current"]["yourIndex"]
    descarte = [c["id"] for c in obs[85]["current"]["players"][yo]["discard"]]
    assert APPLIN in descarte and DIPPLIN in descarte
    campo = obs[84]["current"]["players"][yo]
    en_juego = [c["id"] for c in campo["active"] + campo["bench"] if c]
    assert APPLIN not in en_juego
    m.agent(obs[76])
    assert _carta_de_la_mano(obs[84], m.agent(obs[84])) != NIGHT_STRETCHER
