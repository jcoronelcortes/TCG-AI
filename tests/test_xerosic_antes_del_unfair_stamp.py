"""With a GIANT rival hand, Xerosic goes BEFORE the Unfair Stamp.

Scenario (user, episode 88704504, registro_008 step 90, turn 8 vs Alakazam):

    US                                          RIVAL
    active  Tapu Bulu (charged)                 active  Alakazam
    hand    Meganium, **Unfair Stamp**, Grass,  bench   Fezandipiti ex 210, ...
            Teal Mask Ogerpon ex,               hand    **18 cards**
            **Xerosic's Machinations**, Meowth ex
    They knocked us out the previous turn -> the Stamp is playable.

Both cards fit in the SAME turn: **Unfair Stamp is an Item** (ACE SPEC)
and **Xerosic's Machinations a Supporter**. Here you do not choose a card, you choose
ORDER — and they do different things with those 18 cards:

    Unfair Stamp   "Each player shuffles their hand into their deck. Then, you
                    draw 5 cards, and your opponent draws 2 cards."
    Xerosic        "Your opponent discards cards from their hand until they
                    have 3 cards in their hand."

- **Stamp -> Xerosic** (the old behaviour): the 18 go back to their deck, they draw 2, and
  Xerosic no longer does anything (they are left with 2 <= 3). Worse still: the Stamp shuffles
  **our** hand, so it takes the Xerosic itself with it (in the record it also took
  the Boss's and only one was recovered, by luck).
- **Xerosic -> Stamp** (correct): discard down to 3 → **15 cards to the
  discard FOR GOOD**; the Stamp leaves them at 2 all the same. The same board at the
  end of the turn, with half the rival deck dead.

Why it failed: `cede_a_unfair_stamp` in `_REGLAS_XEROSIC_PLAY` vetoed
Xerosic **whenever** the Stamp was playable. That veto is right for
Lillie's/Dawn/Lana's (the Stamp would shuffle away what they have just brought) but not for
Xerosic, whose effect is immediate and irreversible and which the Stamp cannot undo.

Fix (`_xr_antes_del_sello`, deck-agnostic): with the Stamp playable, Xerosic
in hand, the Supporter slot free and the rival hand >=
`XEROSIC_STAMP_ORDEN_MIN_OP_HAND` (10), the order is reversed — Xerosic keeps
its score and it is the **Stamp** that yields (`cede_el_orden_a_xerosic`). It is an ORDER
veto and it **auto-revokes**: as soon as Xerosic is played, `supporterPlayed`
turns True, the predicate switches off and the Stamp is played in the same turn.

The threshold of 10 comes from the real cost: the Supporter slot is spent BEFORE the
Stamp's refresh, so the 5 new cards can no longer pay for another
Supporter. What is gained is `op_hand - 3` burned cards; it only pays off
when that beats a whole hand (>= 7 cards → a rival hand >= 10).

A side effect corrected: the `_AJUSTES_STAMP_PLAY` did not check the score, so
`bonus_matchup` (+400 vs Alakazam) pulled the vetoed Stamp out of the resolver at
**+399** — exactly in the matchup where this veto lives. Now every adjustment
requires `s > 0`: they bonus plays that are going to happen, they do not resurrect vetoes.
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
            / "alakazam_step90_no_meowth_boss_con_unfair_stamp.json")

UNFAIR_STAMP = m.Unfair_Stamp
XEROSIC = m.Xerosic_Machinations


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


def _obs(op_hand=None, supporter_played=None, sin_xerosic=False):
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    yo = o["current"]["yourIndex"]
    if op_hand is not None:
        o["current"]["players"][1 - yo]["handCount"] = op_hand
    if supporter_played is not None:
        o["current"]["supporterPlayed"] = supporter_played
    if sin_xerosic:
        # It is REPLACED (not removed) so as not to shift the `index` of the menu's
        # PLAY options, which point to hand positions.
        for c in o["current"]["players"][yo]["hand"]:
            if c["id"] == XEROSIC:
                c["id"] = m.Meganium
    return o


def _scores(obs):
    """Returns {'stamp': score, 'xerosic': score} of the real decision."""
    visto = {}
    # The spies are installed in ALL the modules that bind the name: the one that
    # calls the scorers now lives in ptcg/turno/puntuacion.py, not in `main`.
    restauradores = []
    for clave, name in (("stamp", "_score_unfair_stamp_play"),
                          ("xerosic", "_score_xerosic_play")):
        orig = getattr(m, name)

        def espia(ctx, _orig=orig, _clave=clave):
            r = _orig(ctx)
            visto[_clave] = r
            return r

        restauradores.append(instalar(name, espia))
    try:
        m.agent(obs)
    finally:
        for restaurar in restauradores:
            restaurar()
    return visto


# ---------------------------------------------------------------------------
# 1. The real case: a rival hand of 18
# ---------------------------------------------------------------------------

def test_con_mano_rival_gigante_el_sello_cede_el_orden_a_xerosic():
    s = _scores(_obs())
    assert s["xerosic"] > 0, s
    assert s["stamp"] <= 0, s
    assert s["xerosic"] > s["stamp"], s


def test_el_veto_del_sello_no_lo_resucitan_los_ajustes():
    """`bonus_matchup` (+400 vs Alakazam) pulled the veto (−1) up to +399."""
    s = _scores(_obs())
    assert s["stamp"] <= 0, s


def test_tras_jugar_xerosic_el_sello_se_juega_el_mismo_turno():
    """The veto is one of ORDER and auto-revokes: with the Supporter slot already
    spent, the Stamp recovers its normal score."""
    s = _scores(_obs(supporter_played=True))
    assert s["stamp"] > 0, s


# ---------------------------------------------------------------------------
# 2. The edges of the threshold
# ---------------------------------------------------------------------------

def test_justo_en_el_umbral_el_orden_se_invierte():
    s = _scores(_obs(op_hand=m.XEROSIC_STAMP_ORDEN_MIN_OP_HAND))
    assert s["xerosic"] > 0 and s["stamp"] <= 0, s


def test_bajo_el_umbral_vuelve_la_conducta_antigua():
    """With a small rival hand the mill does not pay for the Supporter slot: the
    Stamp rules and Xerosic yields, as before."""
    s = _scores(_obs(op_hand=m.XEROSIC_STAMP_ORDEN_MIN_OP_HAND - 1))
    assert s["stamp"] > 0, s
    assert s["xerosic"] <= 0, s


# ---------------------------------------------------------------------------
# 3. Controls: the veto is about the ORDER, not about the Stamp
# ---------------------------------------------------------------------------

def test_sin_xerosic_en_mano_el_sello_se_juega_normal():
    s = _scores(_obs(sin_xerosic=True))
    assert s["stamp"] > 0, s


def test_si_xerosic_no_va_a_jugarse_el_sello_no_cede():
    """Guard of `cede_el_orden_a_xerosic`: if some other rail knocks Xerosic down to
    `XEROSIC_SCORE_LAST_RESORT` (e.g. `alakazam_cede_a_gusteo_ganador`, where
    the turn is decided by a Boss's), the Stamp does not yield the way to anyone."""
    # Xerosic has to be patched in `ptcg.decision.disrupcion`, NOT in `main`:
    # the one that consults it is `_score_unfair_stamp_play`, which lives in that same
    # module and resolves the name in ITS namespace. `main` only has a copy of the
    # binding (it arrived via `import *`), so patching it there does not reach the scorer.
    # The Stamp IS patched in `main`, because the one that calls it is `agent()`.
    from ptcg.decision import disrupcion

    orig = disrupcion._score_xerosic_play
    disrupcion._score_xerosic_play = lambda ctx: m.XEROSIC_SCORE_LAST_RESORT
    try:
        obs = _obs()
        visto = {}
        orig_stamp = m._score_unfair_stamp_play

        def espia(ctx):
            r = orig_stamp(ctx)
            visto["stamp"] = r
            return r

        _rest_score_unfair_stamp_play = instalar("_score_unfair_stamp_play", espia)
        try:
            m.agent(obs)
        finally:
            _rest_score_unfair_stamp_play()
    finally:
        disrupcion._score_xerosic_play = orig
    assert visto["stamp"] > 0, visto


def test_el_fixture_tiene_de_verdad_las_dos_cartas_y_la_mano_gigante():
    """Without a Stamp + Xerosic in hand and a big rival hand the test measures nothing."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    mano = [c["id"] for c in o["current"]["players"][yo]["hand"]]
    assert UNFAIR_STAMP in mano, mano
    assert XEROSIC in mano, mano
    assert o["current"]["players"][1 - yo]["handCount"] >= 18
    assert o["current"]["supporterPlayed"] is False
