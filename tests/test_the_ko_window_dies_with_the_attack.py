"""The Unfair Stamp is played BEFORE the attack that closes the turn.

Scenario (user, episode 90587542, turn 16 vs Hop's, LOST). Their turn 15 knocked
our Teal Mask Ogerpon ex out, so turn 16 opened with the KO WINDOW OPEN and the
agent used it well for nine actions: it evolved the Applin, played a Bug Catching
Set, benched an Ogerpon ex, cashed Fezandipiti's FLIP THE SCRIPT -- the ability
that asks for the very same clause -- and the three cards it drew included the
UNFAIR STAMP. Then, at step 150:

    US                                      RIVAL
    active  Fezandipiti ex 210, 4 energy    active  140/140, 5 energy, tool
    bench   Applin 40                       bench   140/140 tool, 150, 60,
            Dipplin 80 2e                           70 (1 energy), 60
            Meganium 160 2e
            Teal Mask Ogerpon ex 210 4e
            Teal Mask Ogerpon ex 210
    hand    Bayleef, 2x Ultra Ball, 2x Hydrapple ex, Lana's Aid,
            UNFAIR STAMP, Lillie's Determination, Tapu Bulu
    the turn's Supporter: UNPLAYED       THEIR HAND: 6 CARDS
    prizes  us 3, them 1 (they are at match point)

Their hand of six is above `STAMP_MIN_OP_HAND`, so the card rule
(`_stamp_worth_playing`) said PLAY IT: the Stamp would have left them on two
cards with one prize to go. The ranking was

    attack 8600  >  STAMP 2200  >  Lillie's -1

and the agent SNIPED with Cruel Arrow, closing the turn with the Stamp in hand.
It lost TWO cards to that one action, not one: the -1 on Lillie's is
`yields_to_unfair_stamp`, the ordering veto by which every Supporter of the deck
steps aside for a Stamp that is going to be played -- so the Supporter slot went
unspent as well, given away to a card that was never played.

It is the same failure the Supporter net already answers
(`test_the_supporter_slot_dies_with_the_attack.py`) and the reason that net
exists applies to the Stamp MORE strongly, which is why it now covers it: a
Supporter kept in hand is played tomorrow, but the Stamp carries printed "you
may play this card only if any of your Pokemon were Knocked Out during your
opponent's last turn", so tomorrow it is ILLEGAL unless we are knocked out again
-- the opponent's choice, not ours. The KO window does not accumulate either,
and it is rarer than the slot.

Deck-agnostic by construction: the candidate set is `KO_WINDOW_PLAY_IDS`, the
cards carrying that printed clause, never a matchup list. The last test checks
it with another archetype in front.

Coverage:
  * the record's board, so a future fixture cannot quietly stop measuring it;
  * step 150 plays the Stamp instead of sniping;
  * the prize is not lost: the item does not close the turn and the same board
    still ends it with Cruel Arrow;
  * the limits -- a Stamp vetoed by its own card rule reorders nothing, and the
    winning finisher is never delayed;
  * the Supporter slot ALREADY SPENT does not block the rescue: that guard
    belongs to the Supporter half only;
  * the reorder does not depend on the opposing deck.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m
from cg.api import OptionType

STAMP = m.Unfair_Stamp
LILLIE = m.Lillie_Determination
LANAS = m.Lanas_Aid
ULTRA_BALL = m.Ultra_Ball
GRASS = m.Basic_Grass_Energy
FEZ = m.Fezandipiti_ex
OGERPON = m.Teal_Mask_Ogerpon_ex

CRUEL_ARROW = 183                   # the attack of the record's active

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "hops_step150_the_stamp_goes_before_the_attack.json")


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m._prev_op_prize = 6
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _load():
    with open(_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    return (copy.deepcopy(data["previous_observation"]),
            copy.deepcopy(data["observation"]))


def _obs_step150():
    return _load()[1]


def _decide(obs):
    """The real decision, with the turn's first menu replayed before it.

    The KO window is state carried BETWEEN calls (`_track_ko_window`), so the
    decision is only faithful if the agent has seen the turn open.
    """
    previous, _ = _load()
    m.agent(previous)
    return m.agent(obs)


def _play(obs, choice):
    """('PLAY', card id) / ('ATTACK', attackId) / ('END', None)..."""
    assert choice, f"the agent chose nothing: {choice}"
    o = obs["select"]["option"][choice[0]]
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    if o["type"] == int(OptionType.PLAY):
        return ("PLAY", mine["hand"][o["index"]]["id"])
    if o["type"] == int(OptionType.ATTACK):
        return ("ATTACK", o.get("attackId"))
    if o["type"] == int(OptionType.RETREAT):
        return ("RETREAT", None)
    if o["type"] == int(OptionType.END)   :
        return ("END", None)
    return (o["type"], None)


def _plays(obs):
    return [_play(obs, [i]) for i in range(len(obs["select"]["option"]))]


def _hand_index(obs, card_id):
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    return next(i for i, c in enumerate(mine["hand"]) if c["id"] == card_id)


def _menu(obs, hand_ids, *, attack=True, end=True):
    """Rewrites the menu with exactly these hand cards playable."""
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    opts = [{"index": _hand_index(obs, cid), "type": int(OptionType.PLAY)}
            for cid in hand_ids]
    if attack:
        opts.append({"attackId": CRUEL_ARROW, "type": int(OptionType.ATTACK)})
    if end:
        opts.append({"type": int(OptionType.END)})
    obs["select"]["option"] = opts
    return obs


# ---------------------------------------------------------------------------
# 1. The record: without this board the test measures nothing
# ---------------------------------------------------------------------------

def test_step150_the_board_is_the_records_one():
    obs = _obs_step150()
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert cur["turn"] == 16
    assert cur["supporterPlayed"] is False, (
        "the slot went unspent too: that is the second card the snipe lost")
    assert mine["active"][0]["id"] == FEZ
    assert len(mine["active"][0]["energies"]) == 4, "Cruel Arrow is paid for"
    assert [c["id"] for c in mine["hand"]].count(STAMP) == 1
    assert theirs["handCount"] == 6, (
        "six cards is what the Stamp was going to shuffle back into their "
        "deck, leaving them on two with one prize to go")
    assert len(theirs["prize"]) == 1, "they are at match point"
    assert any(p["hp"] <= 100 for p in theirs["bench"]), (
        "Cruel Arrow has a body it knocks out, which is why the attack was "
        "worth 8600 and won the menu")

    plays = _plays(obs)
    assert ("PLAY", STAMP) in plays, plays
    assert ("ATTACK", CRUEL_ARROW) in plays, plays


def test_step150_the_ko_window_is_open():
    """The window is the whole premise: the same clause the agent had already
    cashed with Flip the Script five actions earlier."""
    obs = _obs_step150()
    _decide(obs)
    assert m.AGENT_STATE.ko_last_turn is True


# ---------------------------------------------------------------------------
# 2. The mistake
# ---------------------------------------------------------------------------

def test_step150_the_stamp_goes_before_the_snipe():
    obs = _obs_step150()
    assert _play(obs, _decide(obs)) == ("PLAY", STAMP), (
        "the snipe ends the turn and the KO window does not accumulate: "
        "playing the Stamp first costs the attack nothing")


def test_step150_the_snipe_is_not_lost_only_delayed():
    """The reorder must not cost the prize. The Stamp is an ITEM: it does not
    close the turn, so the menu it hands back is the one that has to end in
    Cruel Arrow."""
    obs = _obs_step150()
    after = copy.deepcopy(obs)
    cur = after["current"]
    mine = cur["players"][cur["yourIndex"]]
    # The Stamp resolves: our whole hand goes back into the deck and we draw
    # five; they shuffle theirs and draw two.
    mine["hand"] = [{"id": GRASS, "playerIndex": cur["yourIndex"],
                     "serial": 900 + k} for k in range(5)]
    mine["handCount"] = len(mine["hand"])
    cur["players"][1 - cur["yourIndex"]]["handCount"] = 2
    after["select"]["option"] = [
        {"attackId": CRUEL_ARROW, "type": int(OptionType.ATTACK)},
        {"type": int(OptionType.END)},
    ]
    assert _play(after, m.agent(after)) == ("ATTACK", CRUEL_ARROW)


# ---------------------------------------------------------------------------
# 3. The limits: what the net must NOT reorder
# ---------------------------------------------------------------------------

def test_a_stamp_vetoed_by_its_own_rule_reorders_nothing():
    """The net only fixes ORDER; VALUE stays with `_RULES_STAMP_PLAY`. With
    their hand on two the Stamp disrupts nothing, and our nine cards are far
    above `STAMP_MAX_HAND_SACRIFICED`: the card rule vetoes it and a vetoed
    play never reaches the net. The Supporter slot is spent here so that the
    Supporter half cannot fire either and the menu is left to the attack."""
    obs = _obs_step150()
    cur = obs["current"]
    cur["supporterPlayed"] = True
    cur["players"][1 - cur["yourIndex"]]["handCount"] = 2
    _menu(obs, [STAMP, ULTRA_BALL])
    assert _play(obs, _decide(obs)) == ("ATTACK", CRUEL_ARROW)


def test_the_winning_route_is_not_delayed_by_the_stamp():
    """Nothing survives the turn if the turn is the last one. With our prize
    count down to one the plan switches to WIN_NOW and the route that closes
    the game lives in `_TIER_WIN_ATTACK`, above every score -- the Stamp waits
    forever, so it must not take the action.

    (On this board the closing route is the retreat of
    `_win_ko_active_via_promote`, which shares that tier for the same reason:
    it is the first half of the finisher. The net never sees it -- it only
    fires on an ATTACK in tier 0 -- and that is the point being measured: the
    Stamp does not get in front of a turn that ends the game.)"""
    obs = _obs_step150()
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    mine["prize"] = mine["prize"][:1]
    choice = _decide(obs)
    assert _play(obs, choice) != ("PLAY", STAMP)
    assert _play(obs, choice)[0] in ("RETREAT", "ATTACK"), _play(obs, choice)


def test_the_spent_supporter_slot_does_not_block_the_window():
    """The free-slot guard belongs to the SUPPORTER half. A window play has no
    slot to be free: after a Supporter has already been played the Stamp is
    still the card that dies with the turn, and the net still lifts it."""
    obs = _obs_step150()
    obs["current"]["supporterPlayed"] = True
    _menu(obs, [STAMP, ULTRA_BALL])
    assert _play(obs, _decide(obs)) == ("PLAY", STAMP)


def test_without_the_stamp_in_hand_the_snipe_keeps_the_menu():
    """The control of the whole file: the same board minus the Stamp -- and
    minus the Supporters, so no half of the net has a candidate -- snipes,
    which is what the record did."""
    obs = _obs_step150()
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    for cid in (STAMP, LILLIE, LANAS):
        i = next((k for k, c in enumerate(mine["hand"]) if c["id"] == cid),
                 None)
        if i is not None:
            del mine["hand"][i]
    mine["handCount"] = len(mine["hand"])
    _menu(obs, [ULTRA_BALL])
    assert _play(obs, _decide(obs)) == ("ATTACK", CRUEL_ARROW)


# ---------------------------------------------------------------------------
# 4. Any opposing deck
# ---------------------------------------------------------------------------

def test_the_reorder_does_not_depend_on_the_opposing_deck():
    """Same board, another archetype in front: their active becomes a
    Dragapult ex, which moves every matchup flag the scorers read. The reorder
    is identical, because what decides it is the printed clause of OUR card and
    which of the two plays survives the turn -- never the opposing deck."""
    obs = _obs_step150()
    theirs = obs["current"]["players"][1 - obs["current"]["yourIndex"]]
    theirs["active"] = [dict(theirs["active"][0], id=m.Dragapult_ex,
                             hp=320, maxHp=320, preEvolution=[], tools=[])]
    assert _play(obs, _decide(obs)) == ("PLAY", STAMP)
