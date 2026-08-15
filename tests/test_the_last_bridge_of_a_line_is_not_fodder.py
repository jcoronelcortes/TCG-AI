"""Both Bayleef paid for one Ultra Ball, and the Meganium never reached the board.

THE BOARD (user, `records/registro_006_pasos_047_hasta_073.json` step 47,
episode 93159383 vs a Marnie/Grimmsnarl deck, LOST). Our turn 6, prizes 6-6:

    US                                        RIVAL
    active  Tapu Bulu 140/140, 1 {G}          active  Munkidori 100/110, 1 {D}
    bench   Teal Mask Ogerpon ex 180/210 1{G}  bench   Snorunt, Froslass,
            Teal Mask Ogerpon ex 180/210 1{G}          Marnie's Morgrem x2,
            Dipplin 40/80                              Munkidori
    hand    **Bayleef, Bayleef, Ultra Ball**
    stadium Forest of Vitality (ours)

The menu has exactly two options: PLAY the Ultra Ball, or END. Nothing else in
hand is playable -- a Bayleef needs a Chikorita under it and there is none in
play. So the Ultra Ball's cost of TWO CARDS FROM HAND can be paid with one thing
only: both Bayleef.

WHY THAT IS THE GAME. The deck runs 2 Chikorita, 2 Bayleef, 2 Meganium and no
Rare Candy, so Bayleef is the ONLY bridge to the Meganium whose *Wild Growth*
("each Basic {G} Energy attached to all of your Pokemon provides {G}{G}") is this
deck's whole energy engine -- it is what makes a Tapu Bulu on two Grass able to
pay Wood Hammer's {G}{G}{C}{C} for 220.

The agent played it. The two Bayleef went to the discard at step 49 and were
still there at step 190, the last step of the game. Fourteen steps later a
Meganium reached hand and stayed there for 127 of the game's 191 steps; the
Chikorita it was waiting for was benched on that same turn 6, under our own
Forest of Vitality -- "each player's {G} Pokemon can evolve into {G} Pokemon
during the turn they play those Pokemon", so Chikorita -> Bayleef -> Meganium was
ONE turn's work -- and it was still sitting on the bench, unevolved, when the
game ended. Turn 6 closed with the Tapu Bulu on two Grass and no attack, and
every turn after it paid the full physical price for its energy. We lost.

CAUSE, and it is a shape this file's neighbours already name. Every reader of an
evolution piece in hand prices it against the BOARD: `_ub_real_fodder` asks
`field_counts[Chikorita] >= 1` and, failing that, calls the Bayleef fodder; the
forced-discard ladder asks the same and then hands `hand_counts[Bayleef] > 1` the
surplus band (75), which made the two Bayleef the two CHEAPEST cards in the hand.
That branch never even reached its own `ZONE_DECK` test -- unreachable while we
hold two -- so "we have a spare" and "these are the last two in existence" got
the same price.

Both readings are right about a copy THE DECK CAN REPLACE and wrong about the
last ones. THE SEAT CAN BE SEARCHED FOR, THE DISCARDED CARD CANNOT: the missing
Chikorita is a card the deck still holds and this very Ultra Ball could buy,
while a Bayleef in the discard is beyond every search in the deck and takes the
Meganium down with it. That is also why this is NOT the circularity
`_line_base_benchable` refuses ("THE DECK IS NOT A SEAT"): that one vetoed the
search that would un-orphan the piece, and no search un-orphans what it has just
thrown away.

`_evo_bridge_last_copies` asks the four questions that separate the two cases and
names no card -- the stages come from `EVO_LINES`, so the Dipplin of the Applin
line is covered on the same terms. It has two call sites, which are two halves of
one sentence: the Ultra Ball's cost count refuses to price the bridge as fodder
(so `_ub_cancel_no_surplus` speaks when the hand cannot pay around it), and the
forced-discard ladder keeps ONE copy at `DISCARD_LINK_LAST_BRIDGE` and lets the
surplus fall.

MEASURED. Frozen corpus: ONE flip, and it is Dipplin and Hydrapple ex swapping
places inside a single discard ranking that takes both -- the same cards, the
same outcome. Golden corpus: the two decisions of this board. Census
(`utils/census_the_last_bridge_is_not_fodder.py`): 1.55 last-bridge boards per
self-play game, of which 0.11 per game cross the Ultra Ball's threshold of two
and cancel a play.
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
from ptcg.cards import lines as _lines
from ptcg.cards.ids import DISCARD_LINK_LAST_BRIDGE
from ptcg.cards.lines import _evo_bridge_last_copies

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_step047_the_cost_eats_the_only_bridge.json")

BAYLEEF = m.Bayleef
CHIKORITA = m.Chikorita
MEGANIUM = m.Meganium
APPLIN = m.Applin
DIPPLIN = m.Dipplin
HYDRAPPLE = m.Hydrapple_ex
ULTRA = m.Ultra_Ball


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.meganium_in_play = False
    m.forest_in_play = False
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.we_go_first = False
    m._field_at_turn_start = {}
    m._grass_attaches_this_turn = 0
    yield
    m._init_cards_tracking()


def _obs():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _mine(obs):
    return obs["current"]["players"][obs["current"]["yourIndex"]]


# ---------------------------------------------------------------------------
# 1. The scenario: without it the rest measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_a_hand_whose_only_fodder_is_the_whole_line():
    obs = _obs()
    mine = _mine(obs)

    # Hand of exactly three, and two of them are the bridge.
    hand = [c["id"] for c in mine["hand"]]
    assert sorted(hand) == sorted([BAYLEEF, BAYLEEF, ULTRA])

    # The menu is binary: play the Ultra Ball, or end the turn. A Bayleef is not
    # playable -- nothing on the board wears it.
    types = {opt["type"] for opt in obs["select"]["option"]}
    assert types == {int(m.OptionType.PLAY), int(m.OptionType.END)}
    board = {p["id"] for p in mine["active"] + mine["bench"]}
    assert CHIKORITA not in board

    # And the line above is still worth finishing: the Forest is already ours,
    # so a Chikorita benched later can evolve the turn it lands.
    assert obs["current"]["stadium"][0]["id"] == m.Forest_of_Vitality
    assert obs["current"]["stadium"][0]["playerIndex"] == obs["current"]["yourIndex"]


def test_the_belief_says_these_two_are_the_last_bayleef_anywhere():
    """The claim the whole rule rests on, read off the agent's own belief."""
    m.agent(_obs())
    belief = m.AGENT_STATE.ACTIVE_CARDS_IN_DECK
    assert belief[BAYLEEF] == {"DECK": 0, "BENCH": 0, "HAND": 2,
                               "PRIZE": 0, "DISCARD": 0}
    # ...on a line whose top and whose Basic are both still live.
    assert belief[MEGANIUM]["DECK"] == 2
    assert belief[CHIKORITA]["DECK"] == 2


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_the_ultra_ball_is_not_paid_for_with_the_only_bridge():
    obs = _obs()
    choice = m.agent(obs)
    assert obs["select"]["option"][choice[0]]["type"] == int(m.OptionType.END)


def test_without_the_reading_it_burns_them(monkeypatch):
    """The same board with the switch off: the flip is THIS rule's, not the
    working tree's."""
    monkeypatch.setattr(_lines, "LAST_BRIDGE_IS_NOT_FODDER", False)
    obs = _obs()
    choice = m.agent(obs)
    assert obs["select"]["option"][choice[0]]["type"] == int(m.OptionType.PLAY)


def test_the_bridge_that_survives_assembles_the_line_that_same_turn():
    """WHAT THE RULE IS KEEPING THE CARD FOR, and the answer to "why did it not
    just search another Bayleef": the routing half was never broken -- the card
    was.

    `marnie_step072_..._assembles_the_line.json` is the real step 72 with ONE
    change: the Bayleef the Ultra Ball burned at step 49 is back in hand, in the
    Poke Pad's place. Everything else is the board the agent actually reached --
    Chikorita benched THIS turn, Forest of Vitality in play (so it may evolve
    anyway), Meganium in hand, five bodies on the bench. The agent evolves on
    the spot.

    In the recorded game that menu never existed: the deck ran two Bayleef, both
    were in the discard from step 49, and neither the Poke Pad in hand nor the
    two Ultra Balls it played afterwards can reach the discard pile. There was
    no Bayleef left to search for.
    """
    path = (ROOT / "tests" / "fixtures"
            / "marnie_step072_the_bridge_that_survived_assembles_the_line.json")
    with open(path, encoding="utf-8") as f:
        obs = copy.deepcopy(json.load(f)["observation"])

    mine = _mine(obs)
    assert [c["id"] for c in mine["hand"]].count(BAYLEEF) == 1
    assert any(c["id"] == MEGANIUM for c in mine["hand"])
    chikorita = next(b for b in mine["bench"] if b["id"] == CHIKORITA)
    assert chikorita["appearThisTurn"] is True     # only the Forest allows this
    assert obs["current"]["stadium"][0]["id"] == m.Forest_of_Vitality

    choice = m.agent(obs)
    picked = obs["select"]["option"][choice[0]]
    assert picked["type"] == int(m.OptionType.EVOLVE)
    assert mine["hand"][picked["index"]]["id"] == BAYLEEF
    assert mine["bench"][picked["inPlayIndex"]]["id"] == CHIKORITA


# ---------------------------------------------------------------------------
# 3. The predicate, on its own terms and deck-agnostic
# ---------------------------------------------------------------------------

def _bridge(card_id, hand, field, reachable):
    return _evo_bridge_last_copies(card_id, hand, field, reachable)


def test_the_bridge_is_the_middle_link_only():
    """A Basic and a top are somebody else's question: a Basic is what a search
    fetches and a top is what `_evo_top_unlocked_by_the_search` prices."""
    hand = {CHIKORITA: 2, MEGANIUM: 2}
    reach = {CHIKORITA: 2, BAYLEEF: 2, MEGANIUM: 2}
    assert not _bridge(CHIKORITA, hand, {}, reach)
    assert not _bridge(MEGANIUM, hand, {}, reach)


def test_it_fires_on_the_last_copies_and_only_then():
    hand, field = {BAYLEEF: 2}, {}
    last = {CHIKORITA: 2, BAYLEEF: 2, MEGANIUM: 2}
    assert _bridge(BAYLEEF, hand, field, last)

    # One still in the deck -> the search can replace it, nothing to protect.
    spare = {**last, BAYLEEF: 3}
    assert not _bridge(BAYLEEF, hand, field, spare)


def test_a_bridge_already_worn_is_a_spare():
    """With a Bayleef on the board the line is under way and the copy in hand is
    the surplus the cost is supposed to eat."""
    assert not _bridge(BAYLEEF, {BAYLEEF: 1}, {BAYLEEF: 1},
                       {CHIKORITA: 2, BAYLEEF: 2, MEGANIUM: 2})


def test_a_bridge_to_nowhere_is_not_protected():
    """Every Meganium in the discard: the bridge leads nowhere and is fodder
    like anything else. The same for a line with no Basic left to stand on."""
    assert not _bridge(BAYLEEF, {BAYLEEF: 2}, {},
                       {CHIKORITA: 2, BAYLEEF: 2, MEGANIUM: 0})
    assert not _bridge(BAYLEEF, {BAYLEEF: 2}, {},
                       {CHIKORITA: 0, BAYLEEF: 2, MEGANIUM: 2})


def test_it_names_no_card_and_covers_the_other_line():
    """The stages come from `EVO_LINES`: the Dipplin between Applin and
    Hydrapple ex answers exactly like the Bayleef, with no branch of its own."""
    reach = {APPLIN: 2, DIPPLIN: 1, HYDRAPPLE: 2}
    assert _bridge(DIPPLIN, {DIPPLIN: 1}, {}, reach)
    assert not _bridge(DIPPLIN, {DIPPLIN: 1}, {}, {**reach, DIPPLIN: 2})


def test_the_switch_turns_the_whole_reading_off(monkeypatch):
    monkeypatch.setattr(_lines, "LAST_BRIDGE_IS_NOT_FODDER", False)
    assert not _lines._evo_bridge_last_copies(
        BAYLEEF, {BAYLEEF: 2}, {}, {CHIKORITA: 2, BAYLEEF: 2, MEGANIUM: 2})


# ---------------------------------------------------------------------------
# 4. The forced-discard half: keep ONE, let the surplus fall
# ---------------------------------------------------------------------------

def test_the_protected_band_sits_above_the_untouchable_floor():
    """A card we can never get back outranks the two bands that price cards a
    search still reaches -- and still yields to a card already doing its job."""
    from ptcg.cards.ids import (DISCARD_LINK_THE_SEARCH_BUYS,
                                DISCARD_WHAT_THE_SEARCH_ALREADY_BOUGHT)
    assert DISCARD_LINK_THE_SEARCH_BUYS < DISCARD_LINK_LAST_BRIDGE
    assert DISCARD_WHAT_THE_SEARCH_ALREADY_BOUGHT < DISCARD_LINK_LAST_BRIDGE
    assert DISCARD_LINK_LAST_BRIDGE > 2      # the untouchable floor
