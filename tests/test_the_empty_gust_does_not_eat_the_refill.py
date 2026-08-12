"""A gust that its OWN scorer calls empty does not spend the turn's Supporter.

Scenario (user, `registro_004` step 39, episode 91861054, turn 4 vs Marnie,
LOST):

    US (seat 1)                            RIVAL (Marnie)
    active  Tapu Bulu 140/140, ZERO         active  Marnie's Impidimp 70/70
            energy -> it cannot attack      bench   Impidimp x2, Morgrem,
    bench   Teal Mask Ogerpon ex (2e),              Munkidori (1e)
            Ogerpon ex (1e), Applin,
            Chikorita
    hand    Boss's Orders, Hydrapple ex, Meowth ex, Ultra Ball, Meganium,
            LILLIE'S DETERMINATION
    prizes  6 - 6

The menu offered four plays. Every one of them was waiting for another:

    Lillie's       -1  `ultra_ball_completes_the_line` -- "the Ultra Ball first"
    Ultra Ball     -1  `_ub_cancel_meowth` -- "the Meowth ex first", a veto that
                       is itself gated on `not supporterPlayed`
    Meowth ex      -1
    Boss's Orders  20  `empty_gust_yields_to_lillie` -- BOSS_SCORE_EMPTY_GUST,
                       its own chain saying "the active cannot attack, this gust
                       takes no prize, Lillie's should take the slot"

So the only card above zero was the one that had just declared it did not want
the slot, and the agent played it. The gust took nothing; the Ultra Ball became
playable one action later precisely BECAUSE the Supporter was gone
(`_ub_cancel_meowth` switches off once the slot is spent); and the turn closed
with Lillie's Determination still in hand.

Boss's yield was a promise its score could not keep: 20 still beats -1. The four
`yields_to_lillie` rules of `_RULES_BOSS_PLAY` price the gust at the last-resort
band to say "Lillie's takes this slot", but nothing made the yield real.

THE FIX, and where it goes
--------------------------
Not on the Boss's side: vetoing the gust would leave the menu with nothing above
zero and the turn would END on the spot, losing the Ultra Ball and the evolution
too. The circle has to be broken by letting the card that is WAITING move, and
the veto holding it is an ORDER, not a value -- the mechanism to lift it already
existed (`_lillie_play_order_veto` + the "REVOKE ORDERING VETOES" block).

What that mechanism lacked was this case, and it lacked it for a reason written
in its own docstring: it refused to defer whenever ANY other Supporter was in
hand, on the premise that "the slot gets used anyway, so keeping Lillie's vetoed
costs nothing". That premise is false for exactly one band --
`SUPP_SCORE_LAST_RESORT_BAND`, where a Supporter's own scorer says "I have no
useful effect today: play me only because nothing else scores". Down there the
slot is not used, it is WASTED.

The guard now reads the same question on `_supp_play_score`, the scale that
really resolves the slot -- which is what `_supp_in_hand_takes_the_turn` and
`_meowth_fetch_loses_the_turn` already do with this very constant. It was the
third caller of the same law, and the only one still counting cards.

It names no deck and no gust: a Supporter that is not taking the turn cannot
keep another one waiting, against ANY deck.
"""

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m  # noqa: E402

_FIX = Path(__file__).parent / "fixtures" / (
    "marnie_t4_the_empty_gust_ate_the_refill_step39.json")

LILLIE = m.Lillie_Determination
BOSS = m.Boss_Orders
ULTRA_BALL = m.Ultra_Ball


def _fixture():
    with open(_FIX, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _idx_play_of(obs, card_id):
    """The index of the PLAY option that plays `card_id` from hand."""
    yo = obs["current"]["yourIndex"]
    hand = obs["current"]["players"][yo]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if (o["type"] == int(m.OptionType.PLAY)
                and hand[o["index"]]["id"] == card_id):
            return i
    return -1


def _ctx_of(obs):
    """The real DecisionContext of the fixture, so the Supporter scorers are
    measured on the board that produced the decision and not on a stub."""
    captured = {}
    orig = m._score_boss_orders_play

    def spy(ctx, *args, **kwargs):
        captured.setdefault("ctx", ctx)
        return orig(ctx, *args, **kwargs)

    m._score_boss_orders_play = spy
    try:
        m.agent(copy.deepcopy(obs))
    finally:
        m._score_boss_orders_play = orig
    ctx = captured.get("ctx")
    assert ctx is not None, "el tablero no llega a puntuar el Boss's"
    return ctx


# ---------------------------------------------------------------------------
# The board: that the circle really was a circle
# ---------------------------------------------------------------------------

def test_the_board_is_the_one_of_the_record():
    """The premises the rule leans on, read off the fixture and not narrated:
    our active cannot attack, and all four cards are in hand."""
    obs = _fixture()
    yo = obs["current"]["yourIndex"]
    me = obs["current"]["players"][yo]
    assert me["active"][0]["energies"] == [], (
        "el activo sin energia es lo que hace VACIO al gusteo")
    assert not obs["current"]["supporterPlayed"], "el hueco sigue libre"
    hand = [c["id"] for c in me["hand"]]
    for _cid in (BOSS, LILLIE, ULTRA_BALL, m.Meowth_ex):
        assert _cid in hand
    # ...and the four plays are really on the menu, so nothing here is decided
    # by an option the engine never offered.
    for _cid in (BOSS, LILLIE, ULTRA_BALL, m.Meowth_ex):
        assert _idx_play_of(obs, _cid) >= 0


def test_the_gust_prices_itself_in_the_last_resort_band():
    """The Boss's own chain is the witness: `empty_gust_yields_to_lillie` gives
    it `BOSS_SCORE_EMPTY_GUST`, which IS `SUPP_SCORE_LAST_RESORT_BAND`. That is
    the card saying it does not want the slot."""
    ctx = _ctx_of(_fixture())
    assert m._supp_play_score(ctx, BOSS) == m.SUPP_SCORE_LAST_RESORT_BAND
    assert m.BOSS_SCORE_EMPTY_GUST == m.SUPP_SCORE_LAST_RESORT_BAND


def test_the_veto_on_the_refill_is_an_order_not_a_value():
    """And Lillie's is held by an ORDER -- it publishes a real score and names
    the Ultra Ball as what it is waiting for."""
    ctx = _ctx_of(_fixture())
    deferred = m._lillie_play_order_veto(ctx, blocker_offered_in_menu=True)
    assert deferred is not None, "el veto de este paso es de ORDEN, no de valor"
    score, blockers = deferred
    assert score > 0
    assert blockers == (ULTRA_BALL,)


# ---------------------------------------------------------------------------
# The decision
# ---------------------------------------------------------------------------

def test_the_refill_takes_the_slot_and_not_the_empty_gust():
    """The decision of the record, inverted."""
    obs = _fixture()
    assert m.agent(obs) == [_idx_play_of(obs, LILLIE)], (
        "con el activo sin ataque y una Lillie's en mano, el hueco de Supporter "
        "no es de un gusteo que su propio puntuador llama vacio")


# ---------------------------------------------------------------------------
# Controls: the two halves of the bound
# ---------------------------------------------------------------------------

def test_a_supporter_that_really_takes_the_turn_still_holds_the_order():
    """The half that does NOT change. Deciding WHICH Supporter wins the slot is
    a different question: above the band the order stands and Lillie's waits.

    Dawn is the one card that clears the band on THIS board (3660), so it is the
    one the control uses -- read at its real score, not stubbed."""
    ctx = _ctx_of(_fixture())
    ctx.hand_counts[m.Dawn] = ctx.hand_counts.get(m.Dawn, 0) + 1
    assert m._supp_play_score(ctx, m.Dawn) > m.SUPP_SCORE_LAST_RESORT_BAND, (
        "el control exige un Supporter que SI se lleva el turno")
    assert m._lillie_play_order_veto(
        ctx, blocker_offered_in_menu=True) is None


def test_a_second_last_resort_supporter_does_not_hold_it_either():
    """...and the law is about the BAND, not about Boss's Orders. Xerosic's
    Machinations scores exactly `SUPP_SCORE_LAST_RESORT_BAND` on this board
    through its own `XEROSIC_SCORE_LAST_RESORT`, and it holds the order no
    better than the gust does."""
    ctx = _ctx_of(_fixture())
    ctx.hand_counts[m.Xerosic_Machinations] = 1
    assert (m._supp_play_score(ctx, m.Xerosic_Machinations)
            == m.SUPP_SCORE_LAST_RESORT_BAND)
    assert m._lillie_play_order_veto(
        ctx, blocker_offered_in_menu=True) is not None


def test_the_repair_never_touches_the_gust_chain():
    """The other half: the law moves the SLOT, it does not forbid the gust.

    Nothing was added to `_RULES_BOSS_PLAY` -- vetoing the gust there would have
    left this menu with no card above zero and the turn would have ENDED on the
    spot, losing the Ultra Ball and the evolution as well. The Boss's keeps the
    exact score it always had and simply loses the comparison, and the turn
    still closes on a real play."""
    obs = _fixture()
    ctx = _ctx_of(obs)
    assert m._score_boss_orders_play(ctx) == m.BOSS_SCORE_EMPTY_GUST
    chosen = m.agent(obs)
    end_idx = next(i for i, o in enumerate(obs["select"]["option"])
                   if o["type"] == int(m.OptionType.END))
    assert chosen != [end_idx], "el turno no se tira: se juega el relleno"
