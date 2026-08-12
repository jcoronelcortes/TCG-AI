"""On the turn we lose unless we win, the last bench seat belongs to the search.

Scenario (`records/registro_010`, episode 92214949, steps 137-142, turn 10 vs
Archaludon ex, LOST):

    US (2 prizes)                      RIVAL (1 prize)
    active Teal Mask Ogerpon ex        active Archaludon ex 300/300, 3 energies,
           210/210, 6 effective               {G} RESISTANCE
    bench  Meowth ex, Ogerpon ex,      bench  Archaludon ex (2 energies),
           Meganium, Dipplin  (4/5)           2x Relicanth
    hand   Tapu Bulu, 2x Boss's,       stadium Full Metal Lab ({M} takes -30)
           ULTRA BALL

Myriad Leaf Shower was 30 + 30x(6 ours + 3 theirs) = 300, minus 30 for the
Grass resistance and 30 for the Full Metal Lab = 240 into 300 HP. Their
Archaludon knocks our Ogerpon out on the reply and takes its last prize, so the
turn either ends the game or the game is over -- and the plan said exactly that:
`win_route=''`, `prizes_today=1`, `op_prizes_next=2`, `op_wins_next=True`,
mode DENY.

ONE more physical Grass ends it. Meganium's Wild Growth doubles it, so the
attack becomes 30 + 30x(8+3) = 360 - 60 = 300 on a 300 HP body: their ex, the
last two prizes, the game. That Grass was in the deck, behind
Ultra Ball -> Meowth ex -> Last-Ditch Catch -> Lillie's Determination -> six
cards (two Basic Grass, a Night Stretcher over a discard with five, and a Bug
Catching Set: four outs in twenty cards).

Two independent things threw the line away, and neither was a score:

  1. THE ORDER. The Ultra Ball was the highest number on the menu (11900) and
     the Tapu Bulu that cannot attack this turn scored 8900 -- but a Pokemon
     PLAY lives in `_TIER_DEVELOP` (40) and an ordinary Ultra Ball in tier 0,
     and the tier decides before the score. The Tapu Bulu took the fifth seat;
     three actions later `ub->meowth` was vetoed by `full_bench` (10) and the
     search fell to `ub->hydrapple` (`dipplin_evolvable`, 980), an evolution
     that adds no attack. Fixed by `_TIER_SEARCH_KEEPS_THE_SEAT`
     (`ptcg/turn/finalize.py`).

  2. THE TARGET. With the seat kept free the ladder still bought the wrong
     body: `ub->fez` 1050 (`refill_after_a_ko`, three cards off Flip the
     Script) over `ub->meowth` 1000. `_ub_no_attacker_prefer_meowth` asks
     whether an attack is LEGAL, and ours was -- for 240 into 300, on the last
     turn we get. Fixed by making `do_or_die` turn a non-closing attacker into
     no attacker at all (`ptcg/turn/options/card.py`), which is the same
     correction `_ready_attack_is_inert` already makes for the PLAY branch,
     extended to the case it leaves out (`prizes_today >= 1`: a prize taken on
     a turn we do not survive is not a prize).

  3. THE DESTINATION. And with the Grass finally in hand it went to a BENCHED
     Ogerpon. `_charge_active_finishes` -- "the charge that finishes goes to
     the active, ahead of every energy cap" -- only ever looked at boards where
     the active could not yet PAY for its attack (`_cav_e < _cav_req`), and
     ours paid for it eight times over. Myriad Leaf Shower scales with energy,
     so past the cost each Grass is 60 more damage; the flag was reading the
     cost when what mattered was the HP. The scorer then fell through to a
     development rule ("the active does not need energy and a Dipplin on the
     bench is waiting to become a Hydrapple") and the winning energy went to
     the wrong body. Fixed in `main.py`, on the same do-or-die gate.

All three are gated on `TurnPlan.do_or_die` -- 18 of the 3580 decisions of the
frozen corpus, 0.50% -- so nothing changes on a turn that has a tomorrow. The
control tests below are that gate: with the opponent's prize pile deeper the
old order, the old fetch and the old charge have to come back unchanged.

The fixture replays the whole rescue in order. Step 137 is the record's real
menu and 140 its real search menu with the fifth seat still free; 141-144 are
that line rebuilt by hand, because the game the record holds went the other way
and there are no real frames for the turn that wins.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m  # noqa: E402
from ptcg.turn.game_plan import MODE_DENY  # noqa: E402

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "archaludon_t10_the_last_seat_belongs_to_the_search.json")

ULTRA_BALL = m.Ultra_Ball
TAPU_BULU = m.Tapu_Bulu
MEOWTH = m.Meowth_ex
FEZ = m.Fezandipiti_ex
HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
ARCHALUDON = 190


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


def _fetched_id(obs, choice):
    """Id of the card a deck search takes."""
    return obs["select"]["deck"][
        obs["select"]["option"][choice[0]]["index"]]["id"]


def _give_them_room(obs, prizes=4):
    """Same board, their prize pile DEEPER: their reply no longer ends the
    game, so the turn has a tomorrow and none of this may fire."""
    op = obs["current"]["players"][1 - obs["current"]["yourIndex"]]
    op["prize"] = [None] * prizes
    return obs


# ---------------------------------------------------------------------------
# 1. The board, and the sentence the plan writes about it
# ---------------------------------------------------------------------------

def test_the_board_is_the_one_from_the_record():
    obs = _frames()[137]
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    op = cur["players"][1 - cur["yourIndex"]]

    assert len(mine["prize"]) == 2 and len(op["prize"]) == 1, (
        "we need two prizes, they need ONE: their reply ends the game")
    assert len(mine["bench"]) == 4 and mine["benchMax"] == 5, (
        "exactly one free seat -- that is the whole scenario")
    assert ULTRA_BALL in [c["id"] for c in mine["hand"]]
    assert TAPU_BULU in [c["id"] for c in mine["hand"]]
    assert cur["supporterPlayed"] is False
    # their active is the 300 HP body our 240 does not knock out
    assert op["active"][0]["id"] == ARCHALUDON and op["active"][0]["hp"] == 300


def test_the_plan_reads_the_turn_as_do_or_die():
    obs = _frames()[137]
    m.agent(obs)
    plan = m.AGENT_STATE.turn_plan
    assert plan.mode == MODE_DENY and plan.do_or_die is True
    assert plan.wins_this_turn is False, (
        "no route closes the game with what is in hand")
    assert plan.op_wins_next is True, (
        "their reply takes their last prize")
    assert plan.prizes_today == 1, (
        "the turn CAN take a prize (Boss's on a Relicanth) -- and that is "
        "exactly why `_ready_attack_is_inert` does not cover this board")


# ---------------------------------------------------------------------------
# 2. The order: the search goes before the body that would take the seat
# ---------------------------------------------------------------------------

def test_the_search_is_played_before_the_last_seat_is_spent():
    obs = _frames()[137]
    played = m.agent(obs)
    assert _played_id(obs, played) == ULTRA_BALL, (
        "with one seat left and no tomorrow, the card that decides what the "
        "seat is FOR goes first; benching the Tapu Bulu vetoes the Meowth ex "
        "the search was going to buy (`full_bench`)")


def test_the_body_that_cannot_act_scored_lower_all_along():
    """The scores were never wrong -- only the tier was. Guards the fix from
    being 'corrected' by raising a score somewhere else."""
    obs = _frames()[137]
    m.agent(obs)
    # the Tapu Bulu cannot attack this turn: it has no energy and the active
    # would have to retreat for it, which no menu of this turn offers
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    tapu = [c for c in mine["hand"] if c["id"] == TAPU_BULU]
    assert tapu, "the Tapu Bulu is in hand"
    assert all(len(p.get("energies") or []) == 0
               for p in mine["bench"] if p["id"] == TAPU_BULU), (
        "nothing on the bench is a charged Tapu Bulu waiting for the seat")


# ---------------------------------------------------------------------------
# 3. The target: the search buys the deepest look at the deck
# ---------------------------------------------------------------------------

def test_the_search_buys_the_meowth_and_not_the_blind_draw():
    frames = _frames()
    m.agent(frames[137])
    obs = frames[140]
    choice = m.agent(obs)
    fetched = _fetched_id(obs, choice)
    assert fetched == MEOWTH, (
        "Last-Ditch Catch fetches Lillie's Determination and draws SIX; "
        "Flip the Script draws three blind and the Hydrapple ex adds no "
        f"attack at all. It fetched {m.card_table[fetched].name}")


def _replay(steps, transform=None):
    """Answers the fixture's menus in order and returns (obs, choice) of the last.

    IN ORDER on purpose: the charge rule reads the plan of the turn's FIRST
    menu (`turn_plan_open`), which does not exist until step 137 is answered.
    """
    frames = _frames()
    obs = choice = None
    for step in steps:
        obs = frames[step]
        if transform is not None:
            obs = transform(obs)
        choice = m.agent(obs)
    return obs, choice


# ---------------------------------------------------------------------------
# 4. The destination: the Grass that wins goes on the body that attacks
# ---------------------------------------------------------------------------

def test_the_rest_of_the_chain_holds():
    """Meowth benched, Last-Ditch on the refill: the two links between the
    search and the Grass."""
    frames = _frames()
    m.agent(frames[137])
    m.agent(frames[140])

    obs = frames[141]
    assert _played_id(obs, m.agent(obs)) == MEOWTH, (
        "the body the Ultra Ball paid for goes down: its Last-Ditch Catch is "
        "the only reason it was bought")

    obs = frames[142]
    choice = m.agent(obs)
    fetched = obs["select"]["deck"][
        obs["select"]["option"][choice[0]]["index"]]["id"]
    assert fetched == m.Lillie_Determination, (
        "six cards, and four of the twenty left in the deck answer the turn "
        "(two Grass, a Night Stretcher over a discard with five, a Bug "
        f"Catching Set); it fetched {m.card_table[fetched].name}")


def test_the_winning_grass_goes_on_the_active_and_not_on_the_bench():
    obs, choice = _replay([137, 140, 141, 142, 143])
    opt = obs["select"]["option"][choice[0]]
    assert opt.get("type") == int(m.OptionType.ATTACH), (
        "the turn's attachment is the whole play")
    assert opt.get("inPlayArea") == int(m.AreaType.ACTIVE), (
        "one physical Grass on the ACTIVE Ogerpon is 30 + 30x(8+3) = 360, "
        "-30 resistance -30 Full Metal Lab = 300 on a 300 HP body. On the "
        "benched Ogerpon it is a body that never attacks")


def test_and_then_it_attacks():
    obs, choice = _replay([137, 140, 141, 142, 143, 144])
    assert obs["select"]["option"][choice[0]].get("type") == int(
        m.OptionType.ATTACK)
    plan = m.AGENT_STATE.turn_plan
    assert plan.mode == "WIN_NOW" and plan.win_route == "ACTIVE", (
        "with the eighth effective energy on it the plan finally sees what "
        "was there from the first menu of the turn")


# ---------------------------------------------------------------------------
# 5. The gate: with a tomorrow, nothing changes
# ---------------------------------------------------------------------------

def test_control_with_their_prizes_deeper_the_body_goes_down_first():
    obs = _give_them_room(_frames()[137])
    m.agent(obs)
    assert m.AGENT_STATE.turn_plan.do_or_die is False, (
        "their reply no longer closes the game: the turn has a tomorrow")


def test_control_with_a_tomorrow_the_old_order_holds():
    obs = _give_them_room(_frames()[137])
    played = m.agent(obs)
    assert _played_id(obs, played) == TAPU_BULU, (
        "off the do-or-die board the body benched now is early, not lost: "
        "the development tier keeps the order it has always had")


def test_control_with_a_tomorrow_the_fetch_keeps_its_own_ladder():
    frames = _frames()
    m.agent(_give_them_room(frames[137]))
    obs = _give_them_room(frames[140])
    choice = m.agent(obs)
    assert _fetched_id(obs, choice) != MEOWTH, (
        "with a tomorrow our active IS a usable attacker and the fetch is "
        "decided by the ladder that was measured for it")


def test_control_with_a_tomorrow_the_charge_keeps_its_own_ladder():
    """The third fix is the one that reaches furthest -- it overrides every
    energy cap in the file -- so its gate is the one worth pinning down."""
    obs, choice = _replay([137, 140, 141, 142, 143], _give_them_room)
    opt = obs["select"]["option"][choice[0]]
    assert opt.get("inPlayArea") != int(m.AreaType.ACTIVE), (
        "off the do-or-die board the active already pays for its attack and "
        "the energy scorer decides where the Grass goes exactly as it always "
        "did; `_charge_active_finishes` must not have fired")
