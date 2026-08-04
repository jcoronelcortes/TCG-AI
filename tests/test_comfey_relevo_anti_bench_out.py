"""vs Comfey: with an EMPTY BENCH a relief body is played, even if the plan restricts it.

Scenario (autopsy `comfey`, Jul 2026; a fixture captured from self-play, turn 20):

    US                                        RIVAL (mill)
    active  Teal Mask Ogerpon ex              active  Brambleghast
    bench   **EMPTY**                         bench   Brambleghast, Comfey x2,
    hand    Fezandipiti ex, Chikorita,                Bramblin
            Ultra Ball x2, Forest x2,
            Boss's Orders, Grass

The anti-Comfey plan is deliberate and measured: against a deck that mills our
deck, **only Teal Mask Ogerpon ex is played** (max 2) — it is the matchup's attacker
and everything else thins out resources without advancing the plan. That plan had a single
STARTUP exception: if there is no Ogerpon in play or in hand **and there is no
body in play**, a starter is played so we can get going.

The hole is in that "no body": `_cf_has_body` counts the bench **or** the active.
With an empty bench and the active still alive the exception did NOT fire, so
the Fezandipiti ex (which scored 22000) and the Chikorita fell to −1 and the turn
closed with **zero Pokémon on the bench**. If the rival knocks out the active, it is
a bench-out and the game is over.

Measured before the fix (n=250 per deck): the **bench-out is 82% of our
losses** vs comfey (14 of 17) and 50% vs comfey_yveltal_nz (7 of 14) — 5.6% and
2.8% of all games, against the 0.4-2% of the other matchups —, with the
median at **turn 5**.

Fix: `_cf_relevo_urgente` (an empty bench + a BASIC card) joins the exception
alongside `_cf_need_starter`. It is the same shape as the counter-stadium exception
that already lives in the anti-Comfey whitelist of the Trainers branch: *a
matchup whitelist describes which cards advance the plan, and it cannot veto
the card that stops us losing the game on the spot*. And here there is not even an
anti-mill cost to defend: playing a body from HAND does not thin the deck by a single
card.

Differential gate n=1500 per branch: **comfey 90.8% → 95.9% (+5.1)** and
**comfey_yveltal_nz 93.6% → 98.2% (+4.6)**, both ≈5σ. Mirror 47.3%
[44.2-50.4] and the controls (crustle +3.5, hops −1.3) within the noise: the rule
is behind `op_is_comfey_deck`, so it cannot fire in other matchups.
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
            / "comfey_banca_vacia_baja_relevo.json")

FEZ = m.Fezandipiti_ex
CHIKORITA = m.Chikorita
OGERPON = m.Teal_Mask_Ogerpon_ex
BAYLEEF = m.Bayleef            # Stage 1: it is NOT benched
DIPPLIN = m.Dipplin            # Stage 1: it is NOT benched
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
        # Any body on the bench: there is NO relief urgency any more.
        cuerpo = copy.deepcopy(mio["active"][0])
        cuerpo["serial"] = 59
        mio["bench"] = [cuerpo]
    if basicos_a_fase1:
        # The two Basics in hand become Stage 1: they are not benched, so
        # the exemption must not reach them.
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

    def espia(ctx, sel, sc, ob, mi, top_n=3):
        visto.setdefault("s", list(sc))

    # `_debug_log_decision` and `DEBUG_DECISIONS` live in ptcg/motor/depuracion.py,
    # and the one that consults them is in ptcg/turno/finalize.py: they have to be set in
    # all the modules that bind them, not just in `main`.
    _restaurar_espia = instalar("_debug_log_decision", espia)
    _restaurar_flag = instalar("DEBUG_DECISIONS", True)
    try:
        m.agent(obs)
    finally:
        _restaurar_flag()
        _restaurar_espia()
    return visto["s"]


def _flag_de_agent(obs, nombre):
    """Reads a LOCAL variable of `agent()` on return."""
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
# 1. The scenario
# ---------------------------------------------------------------------------

def test_el_fixture_es_banca_vacia_con_activo_vivo_y_relevo_en_mano():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]

    assert not [b for b in mio["bench"] if b]            # EMPTY bench
    assert mio["active"] and mio["active"][0]            # ...but the active is ALIVE
    mano = [h["id"] for h in mio["hand"]]
    assert FEZ in mano and CHIKORITA in mano             # there is a basic relief
    assert OGERPON not in mano                           # and it is NOT Ogerpon ex
    # `op_is_comfey_deck` is LOCAL to `agent()`, not global: reading it with
    # `m.<flag>` would give what the test's reset left, not the decision.
    assert _flag_de_agent(o, "op_is_comfey_deck") is True


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_con_la_banca_vacia_se_baja_un_relevo():
    obs = _obs()
    accion, cid = _jugada(obs, m.agent(obs))
    assert accion == "PLAY", (accion, cid)
    assert cid in BASICOS, m.card_table[cid].name


def test_el_relevo_ya_no_esta_vetado():
    """The failure was a VETO (−1), not a defeat on points."""
    obs = _obs()
    sc = _scores(obs)
    assert sc[_idx_de(obs, FEZ)] > 0, sc
    assert sc[_idx_de(obs, CHIKORITA)] > 0, sc


# ---------------------------------------------------------------------------
# 3. What is NOT broken: the anti-Comfey plan still stands
# ---------------------------------------------------------------------------

def test_con_un_cuerpo_en_banca_vuelve_el_veto_del_plan():
    """The exemption is about SURVIVAL: as soon as there is a relief body, the plan rules
    again and no bodies outside the list are played."""
    obs = _obs(con_banca=True)
    sc = _scores(obs)
    assert sc[_idx_de(obs, FEZ)] <= 0, sc
    assert sc[_idx_de(obs, CHIKORITA)] <= 0, sc


def test_la_exencion_es_solo_para_basicos():
    """A Stage 1 is not benched, so the urgency does not reach it."""
    obs = _obs(basicos_a_fase1=True)
    sc = _scores(obs)
    assert sc[_idx_de(obs, BAYLEEF)] <= 0, sc
    assert sc[_idx_de(obs, DIPPLIN)] <= 0, sc
