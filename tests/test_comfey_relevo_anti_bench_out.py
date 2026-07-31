"""vs Comfey: con la BANCA VACÍA se baja un relevo, aunque el plan lo restrinja.

Escenario (autopsia `comfey`, jul 2026; fixture capturado del self-play, turno 20):

    NOSOTROS                                  RIVAL (mill)
    activo  Teal Mask Ogerpon ex              activo  Brambleghast
    banca   **VACÍA**                         banca   Brambleghast, Comfey x2,
    mano    Fezandipiti ex, Chikorita,                Bramblin
            Ultra Ball x2, Forest x2,
            Boss's Orders, Planta

El plan anti-Comfey es deliberado y está medido: contra un mazo que nos muele el
mazo, **solo se baja Teal Mask Ogerpon ex** (máx 2) — es el atacante del matchup
y todo lo demás adelgaza recursos sin avanzar el plan. Ese plan tenía una única
excepción de ARRANQUE: si no hay Ogerpon en juego ni en mano **y no hay ningún
cuerpo en juego**, se baja un starter para poder empezar.

El agujero está en ese "ningún cuerpo": `_cf_has_body` cuenta banca **o** activo.
Con la banca vacía y el activo todavía vivo la excepción NO disparaba, así que
el Fezandipiti ex (que puntuaba 22000) y el Chikorita caían a −1 y el turno se
cerraba con **cero Pokémon en banca**. Si el rival noquea al activo, es
bench-out y se acabó la partida.

Medido antes del arreglo (n=250 por mazo): el **bench-out es el 82% de nuestras
derrotas** vs comfey (14 de 17) y el 50% vs comfey_yveltal_nz (7 de 14) — 5.6% y
2.8% de todas las partidas, frente al 0.4-2% del resto de matchups —, con la
mediana en el **turno 5**.

Arreglo: `_cf_relevo_urgente` (banca vacía + carta BÁSICA) entra en la excepción
junto a `_cf_need_starter`. Es la misma forma que la excepción del contra-estadio
que ya vive en la whitelist anti-Comfey de la rama de Entrenadores: *una
whitelist de matchup describe qué cartas hacen avanzar el plan, y no puede vetar
la carta que impide perder la partida en el acto*. Y aquí ni siquiera hay coste
anti-mill que defender: bajar un cuerpo de la MANO no adelgaza el mazo ni una
carta.

Gate diferencial n=1500 por rama: **comfey 90.8% → 95.9% (+5.1)** y
**comfey_yveltal_nz 93.6% → 98.2% (+4.6)**, ambos ≈5σ. Espejo 47.3%
[44.2-50.4] y controles (crustle +3.5, hops −1.3) dentro del ruido: la regla
está tras `op_is_comfey_deck`, así que no puede dispararse en otros matchups.
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
            / "comfey_banca_vacia_baja_relevo.json")

FEZ = m.Fezandipiti_ex
CHIKORITA = m.Chikorita
OGERPON = m.Teal_Mask_Ogerpon_ex
BAYLEEF = m.Bayleef            # Fase 1: NO se banquea
DIPPLIN = m.Dipplin            # Fase 1: NO se banquea
BASICOS = (FEZ, CHIKORITA)


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


def _obs(con_banca=False, basicos_a_fase1=False):
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    if con_banca:
        # Un cuerpo cualquiera en la banca: ya NO hay urgencia de relevo.
        cuerpo = copy.deepcopy(mio["active"][0])
        cuerpo["serial"] = 59
        mio["bench"] = [cuerpo]
    if basicos_a_fase1:
        # Los dos Basicos de la mano pasan a ser Fase 1: no se banquean, asi
        # que la exencion no debe alcanzarles.
        for c, nuevo in zip([h for h in mio["hand"] if h["id"] in BASICOS],
                            (BAYLEEF, DIPPLIN)):
            c["id"] = nuevo
    return o


def _jugada(obs, eleccion):
    o = obs["select"]["option"][eleccion[0]]
    if o["type"] == int(m.OptionType.PLAY):
        yo = obs["current"]["yourIndex"]
        return ("PLAY", obs["current"]["players"][yo]["hand"][o["index"]]["id"])
    return (o["type"], None)


def _scores(obs):
    visto = {}
    orig = m._debug_log_decision
    m._debug_log_decision = lambda ctx, sel, sc, ob, mi, top_n=3: visto.setdefault(
        "s", list(sc))
    prev = m.DEBUG_DECISIONS
    m.DEBUG_DECISIONS = True
    try:
        m.agent(obs)
    finally:
        m._debug_log_decision = orig
        m.DEBUG_DECISIONS = prev
    return visto["s"]


def _flag_de_agent(obs, nombre):
    """Lee una variable LOCAL de `agent()` al retornar."""
    capt = {}

    def tr(frame, ev, arg):
        if frame.f_code.co_name != "agent":
            return None
        if ev == "return" and nombre in frame.f_locals:
            capt[nombre] = frame.f_locals[nombre]
        return tr

    sys.settrace(tr)
    try:
        m.agent(obs)
    finally:
        sys.settrace(None)
    return capt.get(nombre)


def _idx_de(obs, card_id):
    yo = obs["current"]["yourIndex"]
    mano = obs["current"]["players"][yo]["hand"]
    return next(i for i, o in enumerate(obs["select"]["option"])
                if o["type"] == int(m.OptionType.PLAY)
                and mano[o["index"]]["id"] == card_id)


# ---------------------------------------------------------------------------
# 1. El escenario
# ---------------------------------------------------------------------------

def test_el_fixture_es_banca_vacia_con_activo_vivo_y_relevo_en_mano():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]

    assert not [b for b in mio["bench"] if b]            # banca VACIA
    assert mio["active"] and mio["active"][0]            # ...pero activo VIVO
    mano = [h["id"] for h in mio["hand"]]
    assert FEZ in mano and CHIKORITA in mano             # hay relevo basico
    assert OGERPON not in mano                           # y NO es Ogerpon ex
    # `op_is_comfey_deck` es LOCAL de `agent()`, no global: leerlo con
    # `m.<flag>` daria lo que dejo el reset del test, no la decision.
    assert _flag_de_agent(o, "op_is_comfey_deck") is True


# ---------------------------------------------------------------------------
# 2. La decisión
# ---------------------------------------------------------------------------

def test_con_la_banca_vacia_se_baja_un_relevo():
    obs = _obs()
    accion, cid = _jugada(obs, m.agent(obs))
    assert accion == "PLAY", (accion, cid)
    assert cid in BASICOS, m.card_table[cid].name


def test_el_relevo_ya_no_esta_vetado():
    """El fallo era un VETO (−1), no una derrota por puntos."""
    obs = _obs()
    sc = _scores(obs)
    assert sc[_idx_de(obs, FEZ)] > 0, sc
    assert sc[_idx_de(obs, CHIKORITA)] > 0, sc


# ---------------------------------------------------------------------------
# 3. Lo que NO se rompe: el plan anti-Comfey sigue en pie
# ---------------------------------------------------------------------------

def test_con_un_cuerpo_en_banca_vuelve_el_veto_del_plan():
    """La exención es de SUPERVIVENCIA: en cuanto hay relevo, el plan manda
    otra vez y no se bajan cuerpos fuera de la lista."""
    obs = _obs(con_banca=True)
    sc = _scores(obs)
    assert sc[_idx_de(obs, FEZ)] <= 0, sc
    assert sc[_idx_de(obs, CHIKORITA)] <= 0, sc


def test_la_exencion_es_solo_para_basicos():
    """Una Fase 1 no se banquea, así que la urgencia no la alcanza."""
    obs = _obs(basicos_a_fase1=True)
    sc = _scores(obs)
    assert sc[_idx_de(obs, BAYLEEF)] <= 0, sc
    assert sc[_idx_de(obs, DIPPLIN)] <= 0, sc
