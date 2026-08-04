"""Lillie's <-> Ultra Ball: two vetoes that yield to each other and kill the turn.

Scenario (`records/registro_010_pasos_103_hasta_116.json`, step 116, turn 10,
LOST vs Dragapult -- episode 89079426):

    US                                         RIVAL
    active Teal Mask Ogerpon ex 120/210, 4 eff. active Dragapult ex 320, 2 en.
    bench  Fezandipiti ex, Meowth ex,          bench  Budew, Dragapult ex,
           Meganium, Meowth ex,                       Munkidori, Drakloak x2
           **Applin just played**
    hand   **Ultra Ball x3**, Hydrapple ex,
           **Lillie's Determination**

The Lillie's came from the *Last-Ditch Catch* of a Meowth ex played that same turn
(step 107) and the turn closed with an **attack**, with the Supporter dead in hand.

Cause: a **mutual block** between two vetoes that, each on its own, are
correct:

  * `ultra_ball_completa_linea` (a Lillie's rule) -- "do not play Lillie's:
    it would shuffle away the Ultra Ball I am going to build Applin → Dipplin →
    Hydrapple ex with". It switches on because the gap exists **on paper**: Applin
    in play, Hydrapple ex in hand, Dipplin in the deck.
  * `_ub_cancel_lillie` (an Ultra Ball veto) -- "do not play the Ultra Ball: its
    cost of discarding 2 would take the Lillie's".

Both fire at once, no card is played and the turn's Supporter slot is
thrown away. It is the same failure already corrected in the
Stamp ↔ Supporter pair (`_stamp_worth_playing`: «it yielded the way to a card that was
no longer going to be played»).

It was covered up by chance by `_ld_supp_comprometido` -- the score floor that forces
playing the Supporter brought by a *Last-Ditch* of THIS turn --, so the block
was still alive for any Lillie's that did not come from a Meowth ex. That is why the
main test checks the play **with the mark cancelled**: it measures the rule, not the
net that was covering it.

Fix: the deference only makes sense if the Ultra Ball can be played for something
that is NOT this very Lillie's. With **two guards** that are exactly what separates
this step from the scenarios where the veto does have to hold:

  1. **Only the circular veto.** The Ultra Ball's full score is not
     consulted: the other COST vetoes belong to this instant and lift by themselves
     within the turn. In registro_004 step 47 -- the case that created the rule --
     the Ultra Ball is also at −1, but through `_ub_cancel_meowth`: the agent
     plays the Meowth ex first and then the Ultra Ball is playable. A gate
     by score would have thrown that line away (covered by
     `test_step47_does_not_shuffle_meganium_line_with_lillie`).
  2. **Only if the Lillie's is the ONLY Supporter in hand.** With another
     Supporter alongside, the turn's slot gets used anyway, so vetoing the
     Lillie's wastes nothing and on top of that keeps the line (covered by the
     controls of `test_pesca_de_remate_probabilistica`, where there is a Boss's
     Orders in hand).
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from patching import instalar
from golden_corpus import reset_agent

_RECORD = ROOT / "records" / "registro_010_pasos_103_hasta_116.json"

LILLIE = m.Lillie_Determination
ULTRA_BALL = m.Ultra_Ball
HYDRAPPLE = m.Hydrapple_ex
APPLIN = m.Applin
BOSS = m.Boss_Orders

pytestmark = pytest.mark.skipif(
    not _RECORD.exists(),
    reason="registro local rotado (records/ es transitorio)")


def _frames():
    data = json.load(open(_RECORD, encoding="utf-8"))
    return [it["observation"] for st in data["steps"] for it in st
            if it.get("status") == "ACTIVE"
            and isinstance(it.get("observation"), dict)
            and (it["observation"].get("current") or {}).get("yourIndex") == 0
            and it["observation"].get("select")]


def _replay(anular_marca_ld):
    """Replays the whole turn and returns (obs, choice) of the last menu."""
    reset_agent(m)
    last = None
    for obs in _frames():
        if anular_marca_ld:
            m._ld_supp_comprometido = 0
        last = (obs, m.agent(obs))
    return last


def _played_card(obs, choice):
    o = obs["select"]["option"][choice[0]]
    if o.get("type") != int(m.OptionType.PLAY):
        return None
    yo = obs["current"]["yourIndex"]
    return obs["current"]["players"][yo]["hand"][o["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. The scenario: without these pieces there is no block to break
# ---------------------------------------------------------------------------

def test_step_116_has_both_halves_of_the_block():
    obs = _frames()[-1]
    yo = obs["current"]["players"][0]
    hand = [c["id"] for c in yo["hand"]]
    campo = [p["id"] for p in yo["active"] + [b for b in yo["bench"] if b]]

    # the line gap that switches on `ultra_ball_completa_linea`...
    assert ULTRA_BALL in hand and HYDRAPPLE in hand
    assert APPLIN in campo and m.Dipplin not in campo
    # ...and the Lillie's as the ONLY Supporter in hand.
    assert hand.count(LILLIE) == 1
    assert not any(s in hand for s in m._SUPP_PLAY_IDS if s != LILLIE)
    assert obs["current"]["supporterPlayed"] is False
    # The Applin appeared this turn: that is why the Ultra Ball builds nothing today.
    assert next(b for b in yo["bench"] if b["id"] == APPLIN)["appearThisTurn"]


# ---------------------------------------------------------------------------
# 2. The correction, measured WITHOUT the net that was covering it
# ---------------------------------------------------------------------------

def test_step116_plays_lillie_even_when_it_did_not_come_from_a_last_ditch():
    obs, choice = _replay(anular_marca_ld=True)
    assert _played_card(obs, choice) == LILLIE, (
        "con la Lillie's como único Supporter y la Ultra Ball vetada por esa "
        "misma Lillie's, ceder el paso tira el hueco de Supporter del turno")


def test_step116_also_plays_it_through_the_last_ditch_route():
    """The `_ld_supp_comprometido` net still stands: the two routes agree."""
    obs, choice = _replay(anular_marca_ld=False)
    assert _played_card(obs, choice) == LILLIE


# ---------------------------------------------------------------------------
# 3. The two guards, each with its contrast
# ---------------------------------------------------------------------------

def _ctx_lillie_of_step116(mutar=None):
    """Builds the real `_CtxLillie` of step 116 and returns its flag."""
    reset_agent(m)
    frames = _frames()
    capturado = {}
    orig = m._CtxLillie

    class _Spy(orig):
        def __init__(self, ctx):
            super().__init__(ctx)
            capturado["v"] = self.ub_gapped_line

    for i, obs in enumerate(frames):
        if i == len(frames) - 1:
            if mutar is not None:
                obs = mutar(json.loads(json.dumps(obs)))
            m._CtxLillie = _Spy
            capturado.clear()
            try:
                m.agent(obs)
            finally:
                m._CtxLillie = orig
        else:
            m.agent(obs)
    return capturado.get("v")


def test_guard2_with_another_supporter_in_hand_the_veto_holds():
    """Contrast for the second guard: it is enough to add a Boss's Orders to the hand
    for the turn's slot to stop being wasted -- and then keeping
    the line is the right thing again."""
    def with_boss(obs):
        yo = obs["current"]["players"][0]
        yo["hand"].append({"id": BOSS, "playerIndex": 0, "serial": 31})
        return obs

    assert _ctx_lillie_of_step116() is False, (
        "sin Supporter de repuesto el bloqueo se rompe")
    assert _ctx_lillie_of_step116(mutar=with_boss) is True, (
        "con un Boss's al lado el Supporter del turno se juega igual: el veto "
        "de Lillie's no desperdicia nada y conserva la línea")


def test_guard1_an_unrelated_cost_veto_does_not_break_the_block():
    """Contrast for the first guard, on the step that created the rule: there the
    Ultra Ball is also vetoed, but through `_ub_cancel_meowth` (its cost would
    take the Meowth ex), not through the Lillie's. That veto lifts by itself within
    the turn -- the Meowth is played first -- so the line is kept."""
    fx = (ROOT / "tests" / "fixtures"
          / "alakazam_step47_ultraball_completes_line_before_lillie.json")
    obs = json.load(open(fx, encoding="utf-8"))["observation"]
    reset_agent(m)

    vistos = []
    _ub = m._score_ultra_ball_play
    m._score_ultra_ball_play = lambda c: (
        vistos.append((_ub(c), m._ub_cancel_lillie(c), m._ub_cancel_meowth(c)))
        or vistos[-1][0])
    try:
        choice = m.agent(obs)
    finally:
        _rest_score_ultra_ball_play = instalar("_score_ultra_ball_play", _ub)
    # The Ultra Ball is vetoed, but NOT because of the Lillie's.
    reales = [v for v in vistos if v[0] <= 0]
    assert reales, "el escenario exige una Ultra Ball vetada"
    assert all(not cancel_lillie for _, cancel_lillie, _ in reales)
    assert any(cancel_meowth for _, _, cancel_meowth in reales)
    # ...so the Lillie's is STILL vetoed and the line is kept.
    assert _played_card(obs, choice) != LILLIE
