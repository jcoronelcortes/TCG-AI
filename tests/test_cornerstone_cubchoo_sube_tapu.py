"""Colisión Cubchoo ↔ muro inmune: el veto anti-Cubchoo mataba el pivote al muro.

Escenario (autopsia `cornerstone_cubchoo`, jul 2026; fixture capturado del
self-play, turno 22):

    NOSOTROS                                  RIVAL
    activo  Teal Mask Ogerpon ex, 6 energias  activo  Cornerstone Mask Ogerpon ex
            (coste de retirada 1)                     210/210
    banca   Hydrapple ex 4e, Ogerpon ex 4e,
            Meowth ex, Meganium, **Tapu Bulu 4e**

*Cornerstone Stance* anula el daño de los ataques de Pokémon **con Habilidad**:
Teal Mask Ogerpon ex (Teal Dance) le hace **0**. El único cuerpo de la banca que
lo toca es **Tapu Bulu** — sin Habilidad, sin recuadro ex — y está **cargado a 4**,
justo su coste de *Wood Hammer* (220, noquea al muro de 210). El activo se retira
por **1**. La jugada es evidente: retirar y subir a Tapu.

El agente **atacaba por 0** y cerraba el turno.

Causa — una **colisión entre dos reglas de matchup**, la clase que la matriz de
matchups se construyó para detectar. El mazo es mixto (Cornerstone + Cubchoo), así
que `op_is_cubchoo_deck` es True y disparaba el veto anti-Cubchoo de la rama
RETREAT (memoria "Anti-Cubchoo: no retirada-pivote, conservar energía"): contra un
mazo que descarta energía, retirar un activo con energía encima destruye recurso
invertido, así que se PASA. Ese veto ya tenía cuatro excepciones
(`_cubchoo_lock_stuck`, `_cc_cashes_dead_body`, `_suicide_swap_win_promote`,
`active_ko_likely`) pero **no** la del muro.

Y el argumento del veto no aplica aquí: la energía de un cuerpo que hace **cero**
al activo rival no es recurso invertido, es recurso **muerto** — y la retirada es
la única vía para convertirlo en daño.

Arreglo: `_ex_stuck_promo_ready` exime el veto. Ese flag ya distingue las dos
inmunidades (`op_has_ex_immune_active` + nuestros ex, u `op_has_ability_immune_active`
+ nuestros cuerpos con Habilidad) y además exige que en la banca haya un atacante
que SÍ le pegue al muro (`_dmg_vs_wall > 0`), así que no abre la puerta a pivotes
pelados.

Medición (250 partidas instrumentadas): con el muro delante, Tapu ≥4 en banca y
la retirada LEGAL, subíamos a Tapu solo el **13.7%** de las veces en las derrotas
por premios (36% en las ganadas). El mismo escenario contra Crustle — muro
equivalente **sin** Cubchoo en el mazo — daba **82.6-100%**, que es lo que puso el
foco en la colisión. En 167 de 169 de esos menús el activo era Teal Mask Ogerpon
ex y el turno se cerraba atacando por 0 (67 veces).

Gate diferencial n=1000: **cornerstone_cubchoo +5.4 puntos** (77.6% vs 72.2%,
≈2.8σ). Validación triple: espejo 51.7% [48.6-54.8] (sin regresión general),
crustle_kangaskhan −1.1, iron_thorns +1.5, comfey −1.8 (todos ruido). No puede
filtrar a otros matchups: `cornerstone_cubchoo` es el ÚNICO mazo de
`deck/rivales/` con Cubchoo, así que el gate `op_is_cubchoo_deck` no dispara en
ningún otro.
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
from parcheo import instalar

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "cornerstone_cubchoo_sube_tapu_no_ataca_por_0.json")

TAPU = m.Tapu_Bulu
OGERPON = m.Teal_Mask_Ogerpon_ex
CORNERSTONE = 117               # Cornerstone Mask Ogerpon ex (ABILITY_IMMUNE_IDS)


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
    m._grass_attaches_this_turn = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _obs(**mut):
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    yo = o["current"]["yourIndex"]
    if "energia_tapu" in mut:
        for b in o["current"]["players"][yo]["bench"]:
            if b and b["id"] == TAPU:
                b["energies"] = b["energies"][:mut["energia_tapu"]]
    return o


def _tipo(obs, eleccion):
    return obs["select"]["option"][eleccion[0]]["type"]


def _scores(obs):
    """Score de cada opcion del menu, espiando `_debug_log_decision`."""
    visto = {}
    orig = m._debug_log_decision

    def espia(context, select, scores, obs_, my_index, top_n=3):
        visto["scores"] = list(scores)
        return orig(context, select, scores, obs_, my_index, top_n)

    _restaurar_espia = instalar("_debug_log_decision", espia)
    prev = m.DEBUG_DECISIONS
    m.DEBUG_DECISIONS = True
    try:
        m.agent(obs)
    finally:
        m._debug_log_decision = orig
        m.DEBUG_DECISIONS = prev
    return visto["scores"]


# ---------------------------------------------------------------------------
# 1. El escenario: sin él, el test no mide nada
# ---------------------------------------------------------------------------

def test_el_fixture_es_el_escenario_del_muro():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    rival = o["current"]["players"][1 - yo]

    assert rival["active"][0]["id"] == CORNERSTONE
    assert mio["active"][0]["id"] == OGERPON              # tiene Habilidad -> hace 0
    assert OGERPON in m.OUR_ABILITY_IDS
    assert CORNERSTONE in m.ABILITY_IMMUNE_IDS
    # Tapu Bulu: sin Habilidad y sin recuadro ex -> SI le pega, y esta LISTO.
    tapu = next(b for b in mio["bench"] if b and b["id"] == TAPU)
    assert len(tapu["energies"]) >= m.ATTACK_ENERGY_REQ[TAPU]
    assert TAPU not in m.OUR_ABILITY_IDS and TAPU not in m.OUR_EX_IDS
    # ...y la retirada del activo es legal y barata.
    assert m.RETREAT_COST[OGERPON] == 1
    tipos = {opt["type"] for opt in o["select"]["option"]}
    assert int(m.OptionType.RETREAT) in tipos
    assert int(m.OptionType.ATTACK) in tipos


# ---------------------------------------------------------------------------
# 2. La decisión
# ---------------------------------------------------------------------------

def test_retira_para_subir_a_tapu_en_vez_de_atacar_por_cero():
    obs = _obs()
    assert _tipo(obs, m.agent(obs)) == int(m.OptionType.RETREAT)


def test_el_veto_anti_cubchoo_ya_no_mata_la_retirada():
    """El fallo era un VETO (score −1), no una derrota por puntos."""
    obs = _obs()
    scores = _scores(obs)
    idx_ret = next(i for i, opt in enumerate(obs["select"]["option"])
                   if opt["type"] == int(m.OptionType.RETREAT))
    idx_atk = next(i for i, opt in enumerate(obs["select"]["option"])
                   if opt["type"] == int(m.OptionType.ATTACK))
    assert scores[idx_ret] > 0, scores
    assert scores[idx_ret] > scores[idx_atk], scores


def _flags_de_agent(obs, nombres):
    """Lee variables LOCALES de `agent()` al retornar.

    `op_is_cubchoo_deck` (como `op_kang_ko_target`) es local, no global: leerlo
    con `m.<flag>` da el valor que dejó el reset del test, no el de la decisión.
    """
    capt = {}

    def tr(frame, ev, arg):
        if frame.f_code.co_name != "agent":
            return None
        if ev == "return":
            for k in nombres:
                if k in frame.f_locals:
                    capt[k] = frame.f_locals[k]
        return tr

    sys.settrace(tr)
    try:
        m.agent(obs)
    finally:
        sys.settrace(None)
    return capt


def test_el_matchup_cubchoo_esta_activo_de_verdad():
    """Si `op_is_cubchoo_deck` fuera False el veto no existiría y los tests de
    arriba pasarían sin probar la exención. El Cubchoo se detecta por el
    DESCARTE rival, que es donde está en este fixture."""
    obs = _obs()
    yo = obs["current"]["yourIndex"]
    descarte = obs["current"]["players"][1 - yo]["discard"]
    assert any(m.card_table[c["id"]].name.startswith("Cubchoo") for c in descarte)

    flags = _flags_de_agent(obs, ("op_is_cubchoo_deck", "_ex_stuck_promo_ready"))
    assert flags.get("op_is_cubchoo_deck") is True, flags
    assert flags.get("_ex_stuck_promo_ready") is True, flags


# ---------------------------------------------------------------------------
# 3. Lo que NO se rompe: la exención exige un atacante REAL contra el muro
# ---------------------------------------------------------------------------

def test_sin_tapu_cargado_el_veto_anti_cubchoo_sigue_en_pie():
    """Con el Tapu por debajo de su coste de ataque no hay pivote al muro que
    justificar, así que vuelve la conducta anti-Cubchoo: conservar la energía."""
    obs = _obs(energia_tapu=1)
    scores = _scores(obs)
    idx_ret = next(i for i, opt in enumerate(obs["select"]["option"])
                   if opt["type"] == int(m.OptionType.RETREAT))
    assert scores[idx_ret] <= 0, scores
    assert _tipo(obs, m.agent(obs)) != int(m.OptionType.RETREAT)
