"""The Supporter that RECOVERS the energy is the finisher (`ROUTE_RECOVER`).

Scenario (user, episode 90115646, turn 10 vs Archaludon ex, LOST). Their turn 9
knocked out our 8-energy Ogerpon ex and its four Grass joined the four already
in the discard. We promote the benched Ogerpon ex, which carries 4 effective
energy, and their active is an Archaludon ex at 300/300 with 3 energy:

    US                                        RIVAL
    active  Ogerpon ex 210/210, 4 effective   active  Archaludon ex 300/300,
    bench   Meowth ex, Meganium, Tapu Bulu,           3 energy
            Fezandipiti ex                    bench   Duraludon (1 prize)
    hand    **Lana's Aid**, Boss's Orders     prizes  1 left
    discard **8 Basic Grass**
    prizes  2 left

The line the board holds, and the arithmetic that decides it:

    Lana's Aid recovers 3 Grass -> the manual attachment (+2, Meganium's Wild
    Growth doubles every Grass) and Teal Dance (+2) put two of them on the
    Ogerpon -> 8 effective energy -> Myriad Leaf Shower 30 + 30 x (8 ours + 3
    theirs) = 360, -30 for Archaludon's Grass resistance = **330 on a 300 HP
    body** -> their ex, the last two prizes, the game.

With ONE Grass fewer the attack stops at 270 and knocks out nothing.

What the agent did instead was play Boss's Orders to gust the Duraludon for a
single prize. And the plan of that turn printed, in full:

    TurnPlan(my_prize=2, op_prize=1, win_route='', win_needs_charge=False,
             prizes_today=1, op_prizes_next=2, op_wins_next=True, mode='DENY')

It ALREADY KNEW it lost on the reply, and it took one prize anyway.

Two deliberate limits, each sound on its own, added up until they hid the route
-- see `_win_via_energy_recovery`, which pays both costs explicitly instead of
loosening either primitive for every caller:

  1. `_charge_this_turn` projects at most ONE attachment, so the plan never
     claims damage the turn will not do. But Teal Dance IS a second real
     attachment.
  2. `_reachable_grass_for` leaves Lana's Aid out on purpose: it spends the
     Supporter slot, which its callers cannot see from where they stand.

And underneath both, the reason the VALUE layer was silent: `_grass_plan` prices
Grass by whether it puts a body in ATTACK RANGE, and this Ogerpon already
reached `ATTACK_ENERGY_REQ` -- it asked for nothing. For an attacker that
SCALES, extra energy is not legality, it is damage.

Coverage:
  * the record's board: the plan sees the route and the turn stops reading DENY;
  * the decision: Lana's Aid takes the Supporter slot from the Boss's;
  * the recovery: what comes back is the Grass, even with a charged bench,
    where `_grass_plan` reports no demand at all;
  * six controls, one per condition the route depends on, because a WIN_NOW
    route governs the whole turn and a loose one is worse than none.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m
from state_builder import Scenario, pk
from ptcg.turn import game_plan as gp

OGERPON = m.Teal_Mask_Ogerpon_ex
GRASS = m.Basic_Grass_Energy
LANA = m.Lanas_Aid
BOSS = m.Boss_Orders
ARCHALUDON = 190        # 300 HP, resists Grass -30
DURALUDON = 666         # their bench, 1 prize: the body the record gusted


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


def _scenario(grass_in_discard=8, hand=(LANA, BOSS), active_energy=4,
              charged_bench=False, supporter_played=False,
              op_active_hp=300, with_attack=False):
    """The turn-10 board. Every parameter is a control: the route depends on
    each one and must go out when it is taken away."""
    bench = [pk(m.Meowth_ex),
             pk(m.Meganium, pre_evo=[m.Chikorita, m.Bayleef]),
             pk(m.Fezandipiti_ex),
             # A Tapu Bulu at 0/4 is what creates Grass DEMAND for
             # `_grass_plan`; charging it takes the demand away and is what the
             # picker control needs.
             pk(m.Tapu_Bulu, energies=4 if charged_bench else 0,
                fisicas=2 if charged_bench else 0)]
    esc = (Scenario(turn=10, step=140, tac=0, first_player=1,
                    supporter_played=supporter_played, own_prizes=2)
           # 4 EFFECTIVE energy = 2 physical cards: Meganium's Wild Growth is
           # on the bench and the observation arrives already doubled.
           .my_active(pk(OGERPON, energies=4, fisicas=2))
           .my_bench(*bench)
           .my_hand(*hand)
           .my_discard(*([GRASS] * grass_in_discard))
           .op_active(pk(ARCHALUDON, hp=op_active_hp, max_hp=op_active_hp,
                         energies=3))
           .op_bench(pk(DURALUDON, hp=130, max_hp=130, energies=1))
           .op_zones(hand=5, deck=30, prizes=1)
           .menu_hand(with_attack=with_attack))
    return esc.build()


def _played_card(obs, choice):
    assert choice, f"the agent ended the turn: {choice}"
    opt = obs["select"]["option"][choice[0]]
    if opt["type"] != int(m.OptionType.PLAY):
        return None
    return obs["current"]["players"][0]["hand"][opt["index"]]["id"]


def _plan_of_decision(obs):
    """The plan the agent really built for this observation."""
    m.agent(obs)
    return m.AGENT_STATE.turn_plan


# ---------------------------------------------------------------------------
# 1. The board: without this, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_board_is_the_one_from_the_record():
    obs = _scenario()
    mine = obs["current"]["players"][0]
    op = obs["current"]["players"][1]

    assert mine["active"][0]["id"] == OGERPON
    assert len(mine["active"][0]["energies"]) == 4      # effective
    assert sum(1 for c in mine["discard"] if c["id"] == GRASS) == 8
    assert not obs["current"]["supporterPlayed"]
    assert op["active"][0]["maxHp"] == 300 and len(op["active"][0]["energies"]) == 3
    # the prize race that makes the energy decisive
    assert len(mine["prize"]) == 2 and len(op["prize"]) == 1


def test_the_arithmetic_is_the_one_that_decides():
    """Two attachments knock out and one does not. If this ever stops holding,
    every assertion below is measuring something else."""
    m.agent(_scenario())                       # it puts Meganium's unit in play
    assert m.AGENT_STATE.meganium_in_play
    unit = m._grass_attach_unit()
    assert unit == 2, "Wild Growth: one physical Grass is worth two effective"

    class _T:
        id, hp, maxHp = ARCHALUDON, 300, 300
        energies, tools = [1, 1, 1], []

    for attaches, expected in ((1, False), (2, True)):
        base = 30 + 30 * ((4 + attaches * unit) + 3)
        dmg = m._our_effective_damage(
            m.Pokemon(id=OGERPON, serial=1, hp=210, maxHp=210,
                      appearThisTurn=False, energies=[1] * 4, energyCards=[],
                      tools=[], preEvolution=[]),
            _T(), base, True, False)
        assert (dmg >= 300) is expected, (
            f"{attaches} attachment(s) -> {dmg} damage vs 300 HP")


# ---------------------------------------------------------------------------
# 2. The plan sees the route
# ---------------------------------------------------------------------------

def test_the_plan_finds_the_winning_recovery():
    plan = _plan_of_decision(_scenario())
    assert plan.win_route == gp.ROUTE_RECOVER
    assert plan.mode == gp.MODE_WIN_NOW, (
        "the turn used to read DENY -- it knew it lost on the reply and took "
        "one prize anyway")
    assert plan.wins_this_turn and plan.lethal_recovery


def test_the_route_asks_for_the_supporter_and_for_a_charge():
    """It is the most expensive of the four: it spends the Supporter slot AND
    the turn's attachments. Both costs are reported, because the ordering of
    the turn is built on them."""
    plan = _plan_of_decision(_scenario())
    assert plan.win_needs_supporter
    assert plan.win_needs_charge
    # ... and it is not a gust: nothing may reserve the slot for a Boss's.
    assert not plan.lethal_gust and not plan.gust_closes_it_now


# ---------------------------------------------------------------------------
# 3. The decision, which is the only thing that counts
# ---------------------------------------------------------------------------

def test_the_supporter_slot_goes_to_the_recovery_and_not_to_the_gust():
    obs = _scenario()
    assert _played_card(obs, m.agent(obs)) == LANA, (
        "the record played Boss's Orders here and gusted a 1-prize Duraludon "
        "while the Grass that knocked out their ex for the last two prizes "
        "sat in the discard")


def test_it_does_not_lose_the_slot_to_developing_the_bench():
    """Measured while building this, and it is the reason the change needed a
    fourth site. With an Applin in hand the turn benched the Basic and left the
    Lana's Aid unplayed -- and raising its score from 20000 to 41000 changed
    NOTHING, because a Pokemon PLAY sits in `_TIER_DEVELOP` (40) and a Supporter
    PLAY in tier 0, and the ORDER TIER is resolved before the score. The fix is
    the tier in `finalize.py`, the same one the winning gust already carries."""
    obs = _scenario(hand=(LANA, BOSS, m.Applin, m.Ultra_Ball))
    assert _played_card(obs, m.agent(obs)) == LANA, (
        "a bench that has no tomorrow does not outrank the play that ends the "
        "game")


def test_it_still_wins_the_slot_with_the_attack_on_the_menu():
    """The active CAN attack (4 energy >= the 3 of Myriad), and attacking now
    does 210 against 300 HP: a turn that ends the game does not spend itself on
    an attack that does not."""
    obs = _scenario(with_attack=True)
    assert _played_card(obs, m.agent(obs)) == LANA


# ---------------------------------------------------------------------------
# 4. The recovery: what comes back has to be the Grass
# ---------------------------------------------------------------------------

def _recovery(charged_bench):
    """The SAME turn, one step later: Lana's Aid is on the table and the menu
    offers what it can pick up -- Grass and an Applin, which is what a real
    discard offers. The MAIN menu is answered first because that is what fixes
    `turn_plan_open`, the plan of the turn BEFORE the Supporter was spent."""
    m.agent(_scenario(charged_bench=charged_bench))
    assert m.AGENT_STATE.turn_plan_open.lethal_recovery, (
        "premise of the control: the opening plan of this turn is the route")

    bench = [pk(m.Meowth_ex),
             pk(m.Meganium, pre_evo=[m.Chikorita, m.Bayleef]),
             pk(m.Fezandipiti_ex),
             pk(m.Tapu_Bulu, energies=4 if charged_bench else 0,
                fisicas=2 if charged_bench else 0)]
    obs = (Scenario(turn=10, step=141, tac=1, first_player=1,
                    supporter_played=True, own_prizes=2)
           .my_active(pk(OGERPON, energies=4, fisicas=2))
           .my_bench(*bench)
           .my_hand(BOSS)
           .my_discard(*([GRASS] * 8), m.Applin)
           .op_active(pk(ARCHALUDON, hp=300, max_hp=300, energies=3))
           .op_bench(pk(DURALUDON, hp=130, max_hp=130, energies=1))
           .op_zones(hand=5, deck=30, prizes=1)
           .fetch_discard(LANA, cuantas=3, only=(GRASS, m.Applin))
           .build())
    choice = m.agent(obs)
    mine = obs["current"]["players"][0]
    return [mine["discard"][obs["select"]["option"][i]["index"]]["id"]
            for i in choice]


def test_the_recovery_takes_the_grass():
    picked = _recovery(charged_bench=False)
    assert picked.count(GRASS) >= 2, (
        f"the finisher needs two Grass in hand; it recovered {picked}")


def test_the_grass_wins_even_with_no_demand_on_the_board():
    """The hole the bands could not cover. `unlocks_today` and `demanda` both
    measure ATTACK RANGE: with the bench charged and an active that already
    reaches its cost, NOBODY asks for Grass and it falls to SURPLUS (120),
    below a Pokemon in the generic scorer's ~150-280 band. Under a winning
    route that ordering is exactly backwards."""
    picked = _recovery(charged_bench=True)
    assert picked.count(GRASS) >= 2, (
        f"with a charged bench the demand is 0 and it recovered {picked}")


# ---------------------------------------------------------------------------
# 5. The turn EXECUTES it: a route nothing can carry out is worse than none
# ---------------------------------------------------------------------------

def test_with_the_grass_in_hand_the_turn_charges_the_active():
    """The step after the recovery. The double charge itself was already built
    -- `_ogerpon_td_manual_lethal` in `agent()` detects exactly this +2 lethal,
    which the greedy scorer misses because it only ever looks at one energy at
    a time -- and its gate is `Basic_Grass_Energy >= 2` IN HAND. That is the
    condition Lana's Aid has just created, and it is why the route needed no
    new charging machinery: what was missing was the energy, not the play."""
    obs = (Scenario(turn=10, step=142, tac=2, first_player=1,
                    supporter_played=True, own_prizes=2)
           .my_active(pk(OGERPON, energies=4, fisicas=2))
           .my_bench(pk(m.Meowth_ex),
                     pk(m.Meganium, pre_evo=[m.Chikorita, m.Bayleef]),
                     pk(m.Fezandipiti_ex), pk(m.Tapu_Bulu))
           .my_hand(GRASS, GRASS, BOSS)
           .my_discard(*([GRASS] * 6))
           .op_active(pk(ARCHALUDON, hp=300, max_hp=300, energies=3))
           .op_bench(pk(DURALUDON, hp=130, max_hp=130, energies=1))
           .op_zones(hand=5, deck=30, prizes=1)
           .menu_teal_dance_options()
           .build())
    choice = m.agent(obs)
    assert choice, "the agent ended a turn that wins"
    kind = obs["select"]["option"][choice[0]]["type"]
    assert kind in (int(m.OptionType.ATTACH), int(m.OptionType.ABILITY)), (
        "with two Grass in hand and their ex at 300 HP, the turn charges the "
        f"active: Myriad only reaches 330 with BOTH energies (chose {kind})")


# ---------------------------------------------------------------------------
# 6. The controls: a WIN_NOW route governs the whole turn, so it has to be
#    exactly as wide as the line it describes
# ---------------------------------------------------------------------------

def test_no_lanas_aid_in_hand_is_no_route():
    plan = _plan_of_decision(_scenario(hand=(BOSS,)))
    assert plan.win_route != gp.ROUTE_RECOVER


def test_the_spent_supporter_closes_the_route():
    plan = _plan_of_decision(_scenario(supporter_played=True))
    assert plan.win_route != gp.ROUTE_RECOVER


def test_without_grass_in_the_discard_there_is_nothing_to_recover():
    plan = _plan_of_decision(_scenario(grass_in_discard=0))
    assert plan.win_route != gp.ROUTE_RECOVER


def test_one_grass_short_is_not_a_route():
    """The whole point of the arithmetic: recovering is only a WIN when the
    energy really reaches lethal. A 400 HP body needs more than the two
    attachments the turn has."""
    plan = _plan_of_decision(_scenario(op_active_hp=400))
    assert plan.win_route != gp.ROUTE_RECOVER
    assert plan.mode != gp.MODE_WIN_NOW


def test_it_is_not_a_route_when_it_does_not_end_the_game():
    """`prize_count_op(target) < my_prize`: the KO happens, but two prizes with
    three to go is not a win, and the route must not claim the Supporter slot
    of a turn that still has a tomorrow."""
    obs = _scenario()
    obs["current"]["players"][0]["prize"] = [None] * 3
    plan = _plan_of_decision(obs)
    assert plan.win_route != gp.ROUTE_RECOVER


def test_a_night_stretcher_that_already_gets_there_keeps_the_slot():
    """The only flip the route produced in 400 games vs archaludon.csv was
    `PLAY Night Stretcher` -> `PLAY Lana's Aid`, which is what sharpened the
    floor: the route is measured against everything the turn already reaches
    WITHOUT the Supporter. Here the active is one attachment short and the
    Stretcher pays for it, so an ITEM closes the game and the Supporter stays
    in hand."""
    # 6 effective energy: ONE more Grass (the Stretcher's) is already 330.
    obs = _scenario(hand=(LANA, m.Night_Stretcher))
    obs["current"]["players"][0]["active"][0]["energies"] = [1] * 6
    plan = _plan_of_decision(obs)
    assert plan.win_route != gp.ROUTE_RECOVER, (
        "an Item was already paying for this KO: the Supporter is not spent")


def test_the_crustle_matchup_is_left_out_because_it_did_not_execute():
    """The one confinement that measurement imposed rather than reasoning.

    Replaying the 11 boards where the route really fired in self-play, the
    Crustle matchup DETECTED the win and never carried it out: the recovered
    Grass went to the bench in 8 of them, because charging the active Ogerpon
    there is vetoed by several stacked layers -- the physical caps, whose only
    exception counts ONE extra energy while this line needs TWO. A WIN_NOW
    route that cannot be executed is worse than no route, so it stays out
    until something measures it."""
    obs = _scenario()
    # A Dwebble on their bench is what switches `op_is_crustle_deck` on.
    obs["current"]["players"][1]["bench"].append({
        "id": m.Dwebble_Grass, "hp": 70, "maxHp": 70, "energies": [],
        "energyCards": [], "tools": [], "preEvolution": [], "serial": 777,
        "appearThisTurn": False, "playerIndex": 1})
    plan = _plan_of_decision(obs)
    assert m.AGENT_STATE.op_is_crustle_deck, "premise of the control"
    assert plan.win_route != gp.ROUTE_RECOVER


def test_an_attack_that_already_knocks_out_does_not_claim_the_slot():
    """`now < hp <= after`: the recovery has to be what CREATES the KO.
    Against a body our 4 energy already knock out, spending the turn's
    Supporter on energy buys nothing."""
    plan = _plan_of_decision(_scenario(op_active_hp=200))
    assert plan.win_route != gp.ROUTE_RECOVER
