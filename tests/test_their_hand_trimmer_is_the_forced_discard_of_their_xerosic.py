"""Their Hand Trimmer is answered by the ladder their Xerosic's is answered by.

Scenario (user, `registro_001_pasos_005_hasta_017.json`, episode 92489131, step
16, turn 1 vs Mega Lopunny ex / Mega Froslass ex -- LOST; the board is frozen in
`tests/fixtures/lopunny_froslass_t1_their_hand_trimmer_cuts_us_to_five_step16.json`).
We are seat 1 and have not played yet: Fezandipiti ex alone in the Active Spot,
an empty bench. On their first turn they play HAND TRIMMER -- "each player
discards cards from their hand until they have 5 cards in their hand; your
opponent discards first" -- and our hand of eight has to come down to five:

    hand   {G} Energy, {G} Energy, Dawn, Bug Catching Set, Bayleef,
           Forest of Vitality, Lana's Aid, Boss's Orders

THE ASK: when they play it, choose the discards exactly as if they had played
Xerosic's Machinations.

THE ANSWER, AND WHY IT IS A TEST AND NOT A RULE. We already do, and not by
coincidence: the `SelectContext.DISCARD` ladder prices THE CARDS IN OUR HAND and
reads `select.effect` exactly once -- to ask WHOSE card is making us discard
(`_forced_discard`, the horizon that lint rule R8 exists to protect) -- so it
never learns which card cut the hand and cannot treat two cutters differently.
A rule keyed on the Hand Trimmer would be a second name for the answer the tree
already gives, and the first thing to fall out of step with it.

What was missing is the guarantee. Every board this ladder was measured on was a
Xerosic's board, so the equivalence was an accident of nobody having written the
name down. This file makes it a property:

  * on the record's own menu, and on the Alakazam board of step 124 where every
    rung of the ladder bites (the cap at 1, the Boss's on the keep floor at 2,
    the Unfair Stamp vetoed), swapping the cutter changes NOTHING -- not the
    choice, not one score;
  * and it is not vacuous: the same menu presented as OUR OWN cost answers
    differently, which is the discriminator doing its job.

THE ONE THING THE TWO CUTTERS DO NOT SHARE, and the reason the discriminator
cannot be `state.supporterPlayed`: Xerosic's Machinations is a Supporter, so
that flag was True on every forced discard the agent had ever seen -- the
observation R8 was written from. Hand Trimmer is an ITEM, and the turn it fires
on may still have its Supporter unspent. Whose card it is survives that. Which
card it is would not.

NOT MEASURED HERE: whether the hand the ladder keeps is the right one. It hands
over both {G} Energy and the Lana's Aid on turn 1, which may well be part of why
this game was lost -- but that is the Xerosic ladder's pricing, the same on both
menus, and moving it is a different question with a different gate.
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
            / "lopunny_froslass_t1_their_hand_trimmer_cuts_us_to_five_step16.json")
_ALAKAZAM = (ROOT / "tests" / "fixtures"
             / "alakazam_t9_their_xerosic_must_not_eat_our_cap_step124.json")

TRIMMER = m.Hand_Trimmer
XEROSIC = m.Xerosic_Machinations
GRASS = m.Basic_Grass_Energy
BOSS = m.Boss_Orders
BAYLEEF = 709
SEAT = 1


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs(path=_FIXTURE):
    with open(path, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _cutter(obs, card_id, seat):
    """The same menu, made by a different card -- or by us."""
    obs = copy.deepcopy(obs)
    obs["select"]["effect"] = {"id": card_id, "playerIndex": seat,
                               "serial": obs["select"]["effect"]["serial"]}
    return obs


def _run(obs):
    """(the indices chosen, the score of every card the menu priced)."""
    scores = {}
    original = m.score_option

    def spy(tc, o, score):
        result = original(tc, o, score)
        card = m.get_card(tc.obs, o.area, o.index,
                          getattr(o, "playerIndex", tc.my_index))
        if card is not None and result is not tc._SALTAR:
            scores.setdefault(card.id, []).append(result)
        return result

    spaces = [sp for sp in
              (getattr(mod, "__dict__", {}) for mod in list(sys.modules.values())
               if mod is not None)
              if sp.get("score_option") is original]
    for sp in spaces:
        sp["score_option"] = spy
    try:
        choice = m.agent(copy.deepcopy(obs))
    finally:
        for sp in spaces:
            sp["score_option"] = original
    return choice, scores


def _discarded(obs, choice):
    hand = obs["current"]["players"][obs["current"]["yourIndex"]]["hand"]
    return sorted(hand[obs["select"]["option"][i]["index"]]["id"] for i in choice)


# ---------------------------------------------------------------------------
# 1. The record: the menu their Hand Trimmer hands us
# ---------------------------------------------------------------------------

def test_the_menu_of_step_16_is_the_one_from_the_record():
    obs = _obs()
    cur = obs["current"]
    assert cur["yourIndex"] == SEAT
    us = cur["players"][SEAT]
    assert [c["id"] for c in us["hand"]] == [
        GRASS, GRASS, m.Dawn, m.Bug_Catching_Set, BAYLEEF,
        m.Forest_of_Vitality, m.Lanas_Aid, BOSS]
    # THEIR card, on THEIR turn: the effect belongs to the other seat.
    assert obs["select"]["effect"]["id"] == TRIMMER
    assert obs["select"]["effect"]["playerIndex"] != SEAT
    assert obs["select"]["context"] == int(m.SelectContext.DISCARD)
    # "...until they have 5 cards in their hand": eight minus five is what it asks for.
    cut = obs["select"]["minCount"]
    assert cut == obs["select"]["maxCount"] == us["handCount"] - m.HAND_CUT_TO


def test_the_cutter_is_theirs_and_not_a_card_of_ours():
    """It is not in `deck.csv`: nothing here is about playing it, only about
    being on the receiving end."""
    ours = [int(line) for line in
            (ROOT / "deck.csv").read_text(encoding="utf-8").split()
            if line.strip().isdigit()]
    assert TRIMMER not in ours


# ---------------------------------------------------------------------------
# 2. The property that was asked for: one ladder, two cutters
# ---------------------------------------------------------------------------

def test_the_record_menu_answers_the_same_as_their_xerosic():
    obs = _obs()
    trimmer_choice, trimmer_scores = _run(obs)
    xerosic_choice, xerosic_scores = _run(_cutter(obs, XEROSIC, 0))
    assert trimmer_choice == xerosic_choice
    assert trimmer_scores == xerosic_scores, (
        "el descarte forzado se decide por DE QUIEN es la carta, nunca por CUAL: "
        f"Hand Trimmer {trimmer_scores} vs Xerosic {xerosic_scores}")


def test_the_alakazam_board_answers_the_same_rung_for_rung():
    """The board where the ladder has structure to lose: their cutter cuts seven
    cards down to three, the Xerosic in OUR hand is the last cap anywhere (1),
    the Boss's holds the keep floor (2) and the Unfair Stamp is vetoed. Swapping
    which card is doing the cutting moves none of it."""
    obs = _obs(_ALAKAZAM)
    seat = obs["current"]["yourIndex"]
    assert obs["select"]["effect"]["id"] == XEROSIC
    assert obs["select"]["effect"]["playerIndex"] != seat
    xerosic_choice, xerosic_scores = _run(obs)
    trimmer_choice, trimmer_scores = _run(
        _cutter(obs, TRIMMER, obs["select"]["effect"]["playerIndex"]))
    assert trimmer_choice == xerosic_choice
    assert trimmer_scores == xerosic_scores
    # and the rungs really were live on this board
    assert xerosic_scores[XEROSIC] == [m.DISCARD_XEROSIC_CAP_IS_THE_ANSWER]
    assert xerosic_scores[BOSS] == [m.DISCARD_SUPPORTER_LIVE_KEEP]


# ---------------------------------------------------------------------------
# 3. The other half: the horizon is live, so the equivalence is not vacuous
# ---------------------------------------------------------------------------

def _board_where_the_horizon_bites(effect_id, effect_seat):
    """The record's board with the hand trimmed to ONE Supporter and ONE Energy,
    and both turn flags spent.

    Those are the two readings `_forced_discard` rewrites: with the Supporter
    slot and the attachment already gone THIS turn, the last Supporter is not
    protected (`_protect_last_supporter`) and the last Energy is priced as
    something the turn can no longer use. On THEIR turn neither is true -- the
    turn those flags belong to has not started -- and both come back.
    """
    obs = _obs()
    us = obs["current"]["players"][SEAT]
    wanted = [GRASS, BOSS, m.Bug_Catching_Set, BAYLEEF, m.Forest_of_Vitality]
    hand, pending = [], list(wanted)
    for card in us["hand"]:
        if card["id"] in pending:
            pending.remove(card["id"])
            hand.append(card)
    assert not pending
    us["hand"] = hand
    us["handCount"] = len(hand)
    obs["current"]["supporterPlayed"] = True
    obs["current"]["energyAttached"] = True
    obs["select"] = {
        "type": 1, "context": int(m.SelectContext.DISCARD),
        "contextCard": None, "deck": None,
        "effect": {"id": effect_id, "playerIndex": effect_seat, "serial": 32},
        "minCount": 1, "maxCount": 1,
        "remainDamageCounter": 0, "remainEnergyCost": 0,
        "option": [{"type": 3, "area": 2, "index": i, "playerIndex": SEAT}
                   for i in range(len(hand))]}
    return obs


def test_their_hand_trimmer_reads_the_turn_flags_as_theirs():
    """Their Item, their turn: the Supporter slot and the attachment we are
    about to get are FREE, so neither the last Boss's Orders nor the last Energy
    is what pays -- the cost falls on the spare stadium instead."""
    trimmer = _board_where_the_horizon_bites(TRIMMER, 0)
    choice, scores = _run(trimmer)
    assert _discarded(trimmer, choice) == [m.Forest_of_Vitality]
    assert GRASS not in _discarded(trimmer, choice)
    assert scores[BOSS] < scores[GRASS]

    # ...exactly what their Xerosic's gets on the same board.
    xerosic = _board_where_the_horizon_bites(XEROSIC, 0)
    x_choice, x_scores = _run(xerosic)
    assert (x_choice, x_scores) == (choice, scores)


def test_the_same_menu_as_our_own_cost_does_not_answer_the_same():
    """CONTROL. Make the effect OURS and the two flags start describing what WE
    spent: the Supporter that can no longer be played this turn stops being the
    thing to protect and the Energy that can no longer be attached becomes the
    cheapest card in hand. If this ever matched the two tests above, the
    equivalence they assert would be measuring nothing."""
    ours = _board_where_the_horizon_bites(m.Ultra_Ball, SEAT)
    choice, scores = _run(ours)
    assert _discarded(ours, choice) == [GRASS]
    assert scores[GRASS] > scores[BOSS]

    theirs = _board_where_the_horizon_bites(TRIMMER, 0)
    _, their_scores = _run(theirs)
    assert scores[GRASS] != their_scores[GRASS]
    assert scores[BOSS] != their_scores[BOSS]
