"""A bench slot reserved for TOMORROW does not outrank a draw that expires TODAY.

Scenario (`records/registro_005_pasos_053_hasta_056.json`, episode 91859188,
steps 54-57, turn 5 vs Alakazam):

    US                                     RIVAL
    active  Pidgey 40/40, 0 energy         active  Alakazam ex 140/140, 1 energy
    bench   Pidgey, Ogerpon ex, Ogerpon    bench   Kadabra x2, Abra, Meowth,
            ex, (one FREE slot)                    Ogerpon
    hand    Grass, Grass, FEZANDIPITI EX   prize   5 (they just took one)

Our Tapu Bulu had been knocked out on their turn 4, so Flip the Script was
ALIVE: benching Fezandipiti ex draws 3 cards, free, once per turn, and the
condition dies at the end of the turn. The promoted Pidgey could not attack, so
the whole turn was a stadium and two evolutions, and the last menu of the turn
held exactly two options:

    [0] PLAY Fezandipiti ex      [1] END TURN

The agent chose END TURN. Three cards in hand, no attack, and Flip the Script
lost for good.

Root cause: the bench reservation vs Alakazam in `ptcg/turn/options/play.py`.
With one free slot and a Xerosic's Machinations still in the deck it holds that
slot for a Meowth ex (Last-Ditch fetches the Xerosic that caps Powerful Hand),
vetoing every body that "does not advance the plan" -- redundant copies, AND
Fezandipiti ex BY NAME. That reservation is priced against a play that can still
be made afterwards; against a payment that expires with the turn the price is
wrong. What it was protecting is a Meowth ex still in the DECK -- and the three
cards it refused to draw are the likeliest place that Meowth ex was going to
come from.

The exemption already existed, written by hand, in the two other vetoes of the
same branch that had been caught doing this (the 4th ex vs Crustle/Cornerstone,
registro_008 step 74; the redundant lethal ex vs Alakazam, registro_010 step
150). Copying it a third time is how a fourth one gets missed, so it is now a
single named predicate, `_pays_today_expiring`, that all of them read -- and it
names no matchup: a payment that expires outranks a reservation for tomorrow
against ANY deck.

Its two halves both matter, and the control tests below hold each one:

  * ALIVE. Without `ko_last_turn` the ability is dead, Fezandipiti ex is two
    prizes of pure development and the reservation is right about it;
  * PAID. With the deck at <= 4 the ability's own deck-out brake
    (`ptcg/turn/options/ability.py`) vetoes Flip the Script, so the body pays
    NOTHING today and the reservation is right about it too.
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
            / "alakazam_t5_the_reserved_slot_yields_to_flip_the_script_step57.json")

FEZ = m.Fezandipiti_ex
MEOWTH = m.Meowth_ex
XEROSIC = m.Xerosic_Machinations

# The last menu of the turn: play Fezandipiti ex, or end it.
_LAST = 57


@pytest.fixture(autouse=True)
def reset_main_state():
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
    yield
    m._init_cards_tracking()


def _frames():
    with open(_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    return {item["step"]: copy.deepcopy(item["observation"])
            for item in data["sequence"]}


def _played_id(obs, choice):
    """Id of the card the main menu plays, or None if it is not a PLAY."""
    opt = obs["select"]["option"][choice[0]]
    if opt.get("type") != int(m.OptionType.PLAY):
        return None
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    return mine["hand"][opt["index"]]["id"]


def _is_end_turn(obs, choice):
    return obs["select"]["option"][choice[0]].get("type") == int(m.OptionType.END)


def _replay(frames, upto=_LAST):
    """Replays the turn's menus in order and returns (obs, choice) of `upto`."""
    obs, choice = None, None
    for _s in sorted(frames):
        obs = frames[_s]
        choice = m.agent(obs)
        if _s == upto:
            break
    return obs, choice


# ---------------------------------------------------------------------------
# 1. The board of the record
# ---------------------------------------------------------------------------

def test_the_board_of_step_57_is_the_one_from_the_record():
    obs = _frames()[_LAST]
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]

    # exactly two options: the Fezandipiti ex, or the end of the turn
    opts = obs["select"]["option"]
    assert len(opts) == 2
    assert _played_id(obs, [0]) == FEZ
    assert opts[1].get("type") == int(m.OptionType.END)

    # one free bench slot -- the one the reservation was holding
    assert len(mine["bench"]) == 4
    assert mine["benchMax"] == 5
    # ...and no Fezandipiti ex in play: this is the FIRST copy
    in_play = [p["id"] for p in mine["bench"] + mine["active"]]
    assert FEZ not in in_play
    # the deck is nowhere near the deck-out brake
    assert mine["deckCount"] > 4


def test_flip_the_script_is_alive_this_turn():
    """Our Tapu Bulu fell on their turn 4: the condition is live and expiring."""
    _replay(_frames())
    assert m.AGENT_STATE.ko_last_turn is True


# ---------------------------------------------------------------------------
# 2. The fix
# ---------------------------------------------------------------------------

def test_the_body_that_draws_today_goes_down_instead_of_ending_the_turn():
    obs, choice = _replay(_frames())
    assert not _is_end_turn(obs, choice), (
        "the turn ended with Flip the Script unused: the draw is free, once "
        "per turn, and its condition dies with the turn")
    assert _played_id(obs, choice) == FEZ


def test_and_the_ability_is_then_used_the_same_turn():
    """The play is only worth its 22500 if the draw follows it.

    A body benched and an ability left unused is the same loss with an extra
    two prizes on the board, so the invariant is checked and not assumed: the
    Fezandipiti ex is moved to the bench and the next menu offers Flip the
    Script against the end of the turn.
    """
    frames = _frames()
    obs, choice = _replay(frames)
    assert _played_id(obs, choice) == FEZ

    nxt = copy.deepcopy(obs)
    cur = nxt["current"]
    mine = cur["players"][cur["yourIndex"]]
    fez = next(c for c in mine["hand"] if c["id"] == FEZ)
    mine["hand"] = [c for c in mine["hand"] if c["id"] != FEZ]
    mine["handCount"] = len(mine["hand"])
    mine["bench"].append({
        "appearThisTurn": True, "energies": [], "energyCards": [],
        "hp": 210, "id": FEZ, "maxHp": 210, "playerIndex": cur["yourIndex"],
        "preEvolution": [], "serial": fez["serial"], "tools": []})
    cur["turnActionCount"] += 1
    nxt["logs"] = []
    ability = {"type": int(m.OptionType.ABILITY), "area": 5,
               "index": len(mine["bench"]) - 1}
    nxt["select"]["option"] = [ability, {"type": int(m.OptionType.END)}]

    assert m.agent(nxt) == [0], (
        "Flip the Script is free and once per turn: with the body already on "
        "the bench, ending the turn instead of drawing 3 is the same bug one "
        "menu later")


def test_the_reservation_is_what_was_vetoing_it():
    """The premise: the slot really was being held for a Meowth ex + Xerosic."""
    obs, _ = _replay(_frames())
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert MEOWTH not in [p["id"] for p in mine["bench"] + mine["active"]]
    assert m.AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
        XEROSIC, {}).get(m.ZONE_DECK, 0) > 0, (
        "with no Xerosic left in the deck there is nothing to reserve for and "
        "the test would pass without the fix")


# ---------------------------------------------------------------------------
# 3. Controls: each half of the law, denied in turn
# ---------------------------------------------------------------------------

def test_control_with_the_ability_dead_the_reservation_holds():
    """No KO last turn -> Flip the Script is dead -> it is 2 prizes of nothing.

    Denied on the BOARD and not on the flag: the opponent's prize row is put
    back to six, which is what "they knocked nothing out" looks like from here.
    """
    frames = _frames()
    for _s in sorted(frames):
        cur = frames[_s]["current"]
        op = cur["players"][1 - cur["yourIndex"]]
        op["prize"] = [None] * 6
        for entry in frames[_s].get("logs") or []:
            entry.pop("putDamageCounter", None)
    obs, choice = _replay(frames)
    assert m.AGENT_STATE.ko_last_turn is False, (
        "the counterfactual did not take: with the KO still detected this "
        "control would pass for the wrong reason")
    assert _is_end_turn(obs, choice), (
        "with the ability dead the body pays nothing today and the "
        "reservation is right to keep the slot")


def test_control_at_the_deck_out_brake_the_reservation_holds():
    """Deck <= 4: the ability's own brake vetoes the draw, so nothing is paid."""
    frames = _frames()
    for _s in sorted(frames):
        mine = frames[_s]["current"]["players"][
            frames[_s]["current"]["yourIndex"]]
        mine["deckCount"] = 3
    obs, choice = _replay(frames)
    assert _is_end_turn(obs, choice), (
        "with the deck at 3, Flip the Script is vetoed by its own deck-out "
        "brake: benching Fezandipiti ex only hands over two prizes")


def test_control_a_plain_redundant_body_is_still_vetoed():
    """The reservation itself is intact: only the expiring payment overrides it."""
    frames = _frames()
    # swap the Fezandipiti ex in hand for a DUPLICATE of a body already benched
    for _s in sorted(frames):
        cur = frames[_s]["current"]
        mine = cur["players"][cur["yourIndex"]]
        dup = next(p["id"] for p in mine["bench"] if p["id"] != FEZ)
        for card in mine["hand"] or []:
            if card["id"] == FEZ:
                card["id"] = dup
    obs, choice = _replay(frames)
    assert _is_end_turn(obs, choice), (
        "a duplicate of something already in play is exactly what the "
        "reservation exists to keep out of the last slot")
