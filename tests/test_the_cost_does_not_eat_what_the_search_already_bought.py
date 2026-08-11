"""The turn bought a Supporter with a Meowth ex and then paid a cost with it.

Scenario (user, `records/registro_004_pasos_031_hasta_045.json`, episode
91650234, turn 4 vs Solrock/Lunatone/Hariyama -- LOST):

    US (6 prizes)                          RIVAL (6 prizes)
    active  Meowth ex 70/170               active  Solrock 110, 2 {G}
    bench   Tapu Bulu, Applin              bench   Lunatone, Hariyama, Lunatone,
    hand    Grass, Xerosic, Ultra Ball,            Solrock
            Bayleef, Hydrapple ex,
            Night Stretcher, Ultra Ball,   (our Supporter slot still FREE)
            Grass

The first half of the turn was excellent. Ultra Ball (paying with the Grass we
had just drawn and the Xerosic) -> **Meowth ex** to the bench -> Last-Ditch
Catch, and of the whole deck it brought back a **Lillie's Determination**: the
refill this hand needed, with the Supporter slot untouched.

Four menus later the SECOND Ultra Ball paid its cost with that very Lillie's.
The turn ended with the Supporter slot still free, the Lillie's in the discard
pile, and an Ultra Ball, a Meowth ex, a bench seat and four cards spent to buy
a card that never touched the board.

NOTHING "CHANGED ITS MIND" -- the two halves never spoke. The fetch scorer reads
the DECK against the board and answers "this is what this board needs"; the
discard ladders read the HAND with static proxies (how many copies, is it the
last refill, how big is the discard pile) and not one of them can tell a card
that was drawn from a card WE WENT AND GOT ten seconds ago. So the most valuable
card in the deck and the cheapest card in the hand were allowed to be the same
card. It is the same disagreement `DISCARD_LINK_THE_SEARCH_BUYS` already forbids
for the card a search is ABOUT to buy ("the card we keep and the card we would
play cannot disagree"), asked of the purchase that has already arrived.

THE RECORD'S OWN CARD IS NOT WHAT THIS FIXES, and the tests below say so out
loud: a Lillie's Determination that is the last refill is saved by her own
ladder (`_protect_refresh_supporter`, score 2) and this board is already right
without any new rule. What was NOT right is everything else the same Last-Ditch
Catch can buy -- see `test_control_without_the_purchase_the_ladders_eat_it`:
on this very board, a Xerosic's Machinations bought by that same ability was
still priced at 60 and thrown away by the next Ultra Ball.

THE FIX. `AGENT_STATE._bought_this_turn` is the memory that was missing: the
serials our own searches moved into this hand THIS TURN, taken off the MOVE_CARD
logs (deck -> hand and discard -> hand, ours), reset with the turn. A DRAW is a
different log and does not enter -- nobody chose it, so it is not the reason any
cost was paid, and the record proves the distinction matters: the Grass drawn
for turn 4 paid the FIRST Ultra Ball, correctly, and still does. The discard
scorer then keeps a purchase at `DISCARD_WHAT_THE_SEARCH_ALREADY_BOUGHT` (4),
one rung above the card the current search is buying. It names no card and no
archetype: whatever the search bought is what the next cost stops pricing as
fodder.

THE PURCHASE IS A COUNT, NOT A SERIAL, and the frozen corpus is what asked for
that guard. Its only event was a Basic Grass the Night Stretcher had recovered
while two more sat in the same hand: protecting THAT copy saves nothing, since
the twins are the same card. Worse -- measured, by running the rule without the
guard -- it moves the cost onto cards that matter: `registro_020` (a Crustle
wall) started discarding a **Tapu Bulu**, the one body that breaks through such
a wall, and `registro_031` a **Xerosic's Machinations**, instead of the fungible
Grass each of them had been paying with. So the spares -- the copies in hand
beyond the purchase -- keep their ordinary price and are what the cost eats.
With the guard in, the rule flips ZERO of the 3 580 frozen decisions.

WHAT IS DELIBERATELY *NOT* DONE, for the same reason the sibling rule documents:
it is NOT mirrored into `_ub_real_fodder`. This is a RANKING among the cards the
cost takes, not a claim that the purchase is untouchable -- the menu still takes
`minCount` cards whatever the scores say. Fed to the veto family it would cancel
the very search the purchase was made for. The last test here is that guard.
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
            / "solrock_t4_the_cost_does_not_eat_what_the_search_already_bought"
              "_step39.json")

SEAT = 1                       # our seat in the record
COST_STEP = 39                 # the menu the second Ultra Ball's cost opens
BOUGHT_SERIAL = 87             # what the Last-Ditch Catch brought back
MEOWTH_SERIAL = 79             # what the FIRST Ultra Ball brought back
DRAWN_SERIAL = 121             # the Grass drawn for the turn: NOT a purchase

BAYLEEF = m.Bayleef
BOSS = m.Boss_Orders
BUG_SET = m.Bug_Catching_Set
DAWN = m.Dawn
GRASS = m.Basic_Grass_Energy
HYDRAPPLE = m.Hydrapple_ex
LANAS = m.Lanas_Aid
LILLIE = m.Lillie_Determination
MEOWTH = m.Meowth_ex
NIGHT_STRETCHER = m.Night_Stretcher
ULTRA_BALL = m.Ultra_Ball
XEROSIC = m.Xerosic_Machinations


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _turn(bought_is=None, twin=None):
    """Every menu of our turn 4, in the order the game asked them.

    `bought_is` rewrites the card the Last-Ditch Catch brought back, keeping its
    serial -- which is what the fetch LOG carries, so the purchase is exactly as
    real as the record's. That is the deck-agnostic half: the board, the search
    and its cost do not change, only what the search decided to buy.

    `twin` adds a second copy of that same card to the hand of the cost menu, a
    copy no search of ours brought.
    """
    with open(_FIXTURE, encoding="utf-8") as f:
        menus = json.load(f)["observaciones"]
    for obs in menus:
        hand = obs["current"]["players"][SEAT]["hand"]
        if bought_is is not None:
            for c in hand:
                if c["serial"] == BOUGHT_SERIAL:
                    c["id"] = bought_is
        if twin is not None and obs["step"] == COST_STEP:
            hand.append({"id": twin, "playerIndex": SEAT, "serial": 900})
            obs["select"]["option"].append(
                {"area": int(m.AreaType.HAND), "index": len(hand) - 1,
                 "playerIndex": SEAT, "type": int(m.OptionType.CARD)})
    return menus


def _menu(menus, step):
    for obs in menus:
        if obs["step"] == step:
            return obs
    raise AssertionError(f"step {step} is not in the fixture")


def _cost_paid_with(menus, from_step=None):
    """Replays the turn and returns the card ids the cost menu discarded.

    The whole turn is replayed on purpose: the fetch log of the Last-Ditch Catch
    travels in the batch of step 38 and the decision under test is the next
    menu, so a fixture holding only the cost board would not exercise the fact
    at all. `from_step` starts the replay later, which is how the CONTROL asks
    for the same board with no purchase behind it.
    """
    paid = None
    for obs in menus:
        if from_step is not None and obs["step"] < from_step:
            continue
        choice = m.agent(copy.deepcopy(obs))
        if obs["step"] == COST_STEP:
            hand = obs["current"]["players"][SEAT]["hand"]
            paid = [hand[obs["select"]["option"][i]["index"]]["id"]
                    for i in choice]
    assert paid is not None, "the cost menu is not in the fixture"
    return paid


# ---------------------------------------------------------------------------
# 1. The record: the board and the purchase that produced the mistake
# ---------------------------------------------------------------------------

def test_the_cost_menu_is_the_one_from_the_record():
    obs = _menu(_turn(), COST_STEP)
    mine = obs["current"]["players"][SEAT]

    assert obs["current"]["turn"] == 4
    # the Supporter slot is still FREE: the Lillie's could have been played
    assert obs["current"]["supporterPlayed"] is False
    # our own Ultra Ball is asking, and it asks for exactly two cards
    assert obs["select"]["context"] == int(m.SelectContext.DISCARD)
    assert obs["select"]["effect"]["id"] == ULTRA_BALL
    assert obs["select"]["effect"]["playerIndex"] == SEAT
    assert obs["select"]["minCount"] == 2 and obs["select"]["maxCount"] == 2
    # the hand it is pricing, with the Lillie's the Meowth ex had just bought
    assert [c["id"] for c in mine["hand"]] == [
        BAYLEEF, HYDRAPPLE, NIGHT_STRETCHER, LILLIE]
    assert [c["serial"] for c in mine["hand"]][3] == BOUGHT_SERIAL
    # and the Meowth ex that bought it, on the bench, benched this same turn
    bench = {p["id"]: p for p in mine["bench"]}
    assert MEOWTH in bench and bench[MEOWTH]["appearThisTurn"] is True


def test_the_purchases_are_dated_off_the_logs_and_last_the_turn():
    """Sticky, and it tells a purchase from a draw.

    Serial 79 is the Meowth ex the first Ultra Ball fetched (step 35), serial 87
    the Lillie's its ability brought back (step 38). Serial 121 is the Grass
    DRAWN for the turn: nobody chose it, so it never enters -- and the record
    paid the first Ultra Ball with it, correctly, at step 33.
    """
    seen = {}
    for obs in _turn():
        m.agent(copy.deepcopy(obs))
        seen[obs["step"]] = set(m.AGENT_STATE._bought_this_turn)

    assert seen[31] == set() and seen[34] == set()
    assert seen[35] == {MEOWTH_SERIAL}, "the fetch log travels in this batch"
    assert seen[38] == {MEOWTH_SERIAL, BOUGHT_SERIAL}
    assert seen[COST_STEP] == {MEOWTH_SERIAL, BOUGHT_SERIAL}
    assert all(DRAWN_SERIAL not in s for s in seen.values()), (
        "a DRAW is not a purchase: nobody chose it")


def test_the_cost_does_not_pay_with_the_lillie_it_just_bought():
    paid = _cost_paid_with(_turn())
    assert LILLIE not in paid, (
        "la Ultra Ball anterior + el Meowth ex + su habilidad se gastaron en "
        f"traer esa Lillie's y el Supporter del turno sigue libre; pago {paid}")
    assert sorted(paid) == sorted([BAYLEEF, NIGHT_STRETCHER])


# ---------------------------------------------------------------------------
# 2. The rule, on everything else the same ability can buy
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bought", [XEROSIC, BOSS, DAWN, LANAS, BUG_SET,
                                    ULTRA_BALL, m.Tapu_Bulu])
def test_whatever_the_search_bought_is_what_the_cost_stops_eating(bought):
    """Same board, same search, same cost -- only the purchase changes.

    Deck-agnostic by construction: the rule reads the fetch log, not the card.
    """
    paid = _cost_paid_with(_turn(bought_is=bought))
    assert bought not in paid, (
        f"el coste se comio la compra del turno ({bought}); pago {paid}")
    assert sorted(paid) == sorted([BAYLEEF, NIGHT_STRETCHER])


def test_control_without_the_purchase_the_ladders_eat_it():
    """The load-bearing control: the SAME hand, with no search behind it.

    Starting the replay at the cost menu means the fetch log never arrives, so
    the card is just a card in hand and the ordinary ladders price it -- the Bug
    Catching Set the most discardable thing there. That is the decision the
    record would still be making, and it is what the rule changes.

    IT USED TO BE THE XEROSIC, and the card had to change when the cap learned
    to read the opposing hand (`DISCARD_XEROSIC_CAPS_A_FAT_HAND`). On this board
    their hand is over the threshold, so the ordinary ladder now KEEPS the cap --
    which makes it a fine card and a useless control. Measured while swapping it:
    of the five candidates only the Bug Catching Set is still eaten here; every
    Supporter in the hand is protected by its own branch, with or without this
    rule. A control has to be a card the ladder really does throw away.
    """
    paid = _cost_paid_with(_turn(bought_is=BUG_SET), from_step=COST_STEP)
    assert BUG_SET in paid, (
        "sin la compra, la escalera ordinaria tira el Bug Catching Set: si esto "
        "deja de pasar, la regla nueva ya no es la que salva la carta")


def test_control_the_lillie_of_the_record_is_saved_by_her_own_ladder():
    """Honesty about the record: this board was already right without the rule.

    A Lillie's Determination that is the last refill scores 2 whoever brought
    her. The record's own card is the STORY, not the fix -- the fix is the test
    above it.
    """
    paid = _cost_paid_with(_turn(), from_step=COST_STEP)
    assert LILLIE not in paid


# ---------------------------------------------------------------------------
# 3. The guards
# ---------------------------------------------------------------------------

def test_a_twin_nobody_bought_is_what_pays():
    """The purchase is a COUNT, not a serial: copies are interchangeable.

    With two Xerosic in hand and only one of them bought, one of them pays and
    the purchase survives -- exactly what the frozen corpus asked for, where the
    recovered card was a Basic Grass with two twins beside it.
    """
    menus = _turn(bought_is=BUG_SET, twin=BUG_SET)
    paid = _cost_paid_with(menus)
    assert paid.count(BUG_SET) == 1, (
        f"solo la copia sobrante paga; pago {paid}")
    assert BAYLEEF in paid


def test_a_discard_forced_by_their_card_buys_nothing():
    """The whole rule hangs on the cost being OURS. Under an opposing
    hand-cutter nothing of ours is being bought and the ladders rule again."""
    menus = _turn(bought_is=BUG_SET)
    _menu(menus, COST_STEP)["select"]["effect"] = {
        "id": XEROSIC, "playerIndex": 1 - SEAT, "serial": 300}
    assert BUG_SET in _cost_paid_with(menus)


def test_the_ultra_ball_is_still_played_at_all():
    """The step BEFORE the cost, on the same board: the Ultra Ball is still the
    play of the turn.

    This is the guard, not a formality. If `_ub_real_fodder` ever learns this
    rule, the cost vetoes start cancelling the very search the purchase was made
    for and the turn ends with neither the purchase spent nor the search made.
    """
    menus = _turn()
    picked = None
    for obs in menus:
        if obs["step"] > 38:
            break
        choice = m.agent(copy.deepcopy(obs))
        if obs["step"] == 38:
            picked = obs["select"]["option"][choice[0]]
            hand = obs["current"]["players"][SEAT]["hand"]
    assert picked is not None
    assert picked.get("type") == int(m.OptionType.PLAY)
    assert hand[picked["index"]]["id"] == ULTRA_BALL, (
        f"la Ultra Ball sigue siendo la jugada del turno; eligio {picked}")
