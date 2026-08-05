"""An order that can never arrive is not an order: it is a lost Supporter.

`ultra_ball_completes_the_line` says: do not refill yet -- the Ultra Ball has to
bring the missing intermediate piece of the line first, and Lillie's would
shuffle both the Stage 2 and the Ultra Ball into the deck. That is an ORDER, not
a judgement about what Lillie's is worth, and it holds exactly as long as the
Ultra Ball can still be played.

Under ITEM LOCK it cannot. Against a Jellicent deck (or an opposing Budew) the
engine does not even OFFER the Ultra Ball, so there is no "afterwards": the veto
waits for a card that will not be played this turn and the turn's Supporter dies
in hand. Measured over 200 games against `deck/opponents/jellicent_lock.csv`,
before the fix: the rule fired 124 times, in ALL 124 with no Ultra Ball on the
menu, and 26 of those turns closed with the Supporter slot unused -- the same
hand growing turn after turn with a Lillie's in it that was never played.

The fix is the mechanism that already existed for abilities (registro_006 step
78, Flip the Script behind the Unfair Stamp): the veto is registered in
`_order_veto` as DEFERRABLE and the "REVOKE ORDERING VETOES" block lifts it when
no blocker is offered and playable. `_lillie_play_order_veto` publishes the score
the chain would give without the ordering rule.

Two bounds, both measured, both of them the reason this stays narrow:

* it is registered ONLY when the Ultra Ball is NOT OFFERED at all. While it is
  on the menu the order stands even at -1: its cost vetoes are about this
  instant and lift themselves within the turn -- in registro_004 step 47 the
  Meowth ex goes down first and the Ultra Ball is playable right after. That
  case is pinned by `test_step47_does_not_shuffle_meganium_line_with_lillie`.
* it is registered ONLY when this Lillie's is the only Supporter in hand. That
  bound is not new: it is the one the `ub_gapped_line` mutual-block breaker
  already decided for this very rule -- with another Supporter in hand the slot
  is used anyway, so the veto costs nothing. Without it, half the measured flips
  were Boss's / Dawn / Lana's giving way to Lillie's, which is a change of
  Supporter PRIORITY and a different question.

Fixture: a real observation captured from self-play against `jellicent_lock.csv`,
frozen at the step where the repair changes the choice.
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
            / "jellicent_item_lock_lillie_waits_for_a_locked_ultra_ball.json")

LILLIE = m.Lillie_Determination
ULTRA_BALL = m.Ultra_Ball
BOSS = m.Boss_Orders


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _hand(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]["hand"]


def _idx_play(obs, card_id):
    hand = _hand(obs)
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(m.OptionType.PLAY) and hand[o["index"]]["id"] == card_id:
            return i
    return -1


def _offered(obs, card_id):
    return _idx_play(obs, card_id) >= 0


# ---------------------------------------------------------------------------
# 1. The scenario: the blocker is in hand and cannot be played
# ---------------------------------------------------------------------------

def test_the_fixture_holds_a_locked_ultra_ball_and_the_turns_supporter():
    o = _obs()
    cur = o["current"]
    ids = [c["id"] for c in _hand(o)]

    assert cur["supporterPlayed"] is False, "el Supporter del turno sigue libre"
    assert ULTRA_BALL in ids, "la Ultra Ball esta en la mano..."
    assert not _offered(o, ULTRA_BALL), (
        "...y el motor NO la ofrece: los Items estan bloqueados")
    assert _offered(o, LILLIE), "el paso ofrecia jugar Lillie's Determination"
    assert not any(_offered(o, _sid) for _sid in m._SUPP_PLAY_IDS
                   if _sid != LILLIE), (
        "Lillie's es el UNICO Supporter jugable: el slot se pierde entero")
    assert any(o_["type"] in (int(m.OptionType.ATTACK), int(m.OptionType.END))
               for o_ in o["select"]["option"]), "el turno se cierra en este menu"


def test_the_supporter_is_played_instead_of_dying_in_hand():
    """The regression: the agent attacked and the Lillie's stayed in hand
    waiting for an Ultra Ball that item lock will never let it play."""
    o = _obs()
    assert m.agent(o) == [_idx_play(o, LILLIE)]


# ---------------------------------------------------------------------------
# 2. The bounds of the deferral, on the predicate
# ---------------------------------------------------------------------------

def _ctx_of(obs):
    """The real DecisionContext of the fixture, so the predicate is measured on
    the board that produced it and not on a stub."""
    captured = {}
    orig = m._lillie_play_order_veto

    def spy(ctx):
        captured.setdefault("ctx", ctx)
        return orig(ctx)

    m._lillie_play_order_veto = spy
    try:
        m.agent(copy.deepcopy(obs))
    finally:
        m._lillie_play_order_veto = orig
    return captured.get("ctx")


def test_the_predicate_publishes_a_real_score_and_the_blocker():
    ctx = _ctx_of(_obs())
    assert ctx is not None, "el escenario no llega a consultar el predicado"
    deferred = m._lillie_play_order_veto(ctx)
    assert deferred is not None, "el veto de este paso es de ORDEN, no de valor"
    score, blockers = deferred
    assert score > 0, "el score real de la Lillie's sin la regla de orden"
    assert blockers == (ULTRA_BALL,), "lo que se esta esperando es la Ultra Ball"


def test_another_supporter_in_hand_keeps_the_veto():
    """The bound of the `ub_gapped_line` mutual-block breaker: with a second
    Supporter the slot gets used anyway, so the veto costs nothing and the line
    is preserved. Repairing a wasted slot is one question; deciding WHICH
    Supporter wins it is another."""
    ctx = _ctx_of(_obs())
    assert ctx is not None
    ctx.hand_counts[BOSS] = ctx.hand_counts.get(BOSS, 0) + 1
    assert m._lillie_play_order_veto(ctx) is None


def test_with_the_ultra_ball_on_the_menu_the_order_stands():
    """The other bound, and the counter-example that pays for it: in
    registro_004 step 47 the Ultra Ball is offered at -1 (its cost would take
    the Meowth ex), the Meowth goes down first and the Ultra Ball becomes
    playable straight after. `test_step47_does_not_shuffle_meganium_line_with_lillie`
    pins that step; here the same boundary is read on this fixture by putting
    the Ultra Ball back on the menu."""
    o = _obs()
    cur = o["current"]
    hand = _hand(o)
    ub_hand_index = next(i for i, c in enumerate(hand) if c["id"] == ULTRA_BALL)
    o["select"]["option"].insert(
        0, {"type": int(m.OptionType.PLAY), "index": ub_hand_index})
    assert m.agent(o) != [_idx_play(o, LILLIE)], (
        "con la Ultra Ball ofrecida el veto de orden vale y la Lillie's espera")
