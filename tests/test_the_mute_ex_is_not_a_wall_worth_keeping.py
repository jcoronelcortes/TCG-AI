"""A Meowth ex in front is not a wall: the Grass pays its retreat.

Scenario (user, episode 90321662, turn 24 vs a Crustle / Great Tusk deck, LOST
by deck-out with five prizes still on the table). The turn opens at step 104:

    US                                        RIVAL
    active  Meowth ex 170/170, 0 energy       active  Great Tusk 140/140, 1 energy
    bench   Teal Mask Ogerpon ex   2/3        bench   Crustle 50/150
            Teal Mask Ogerpon ex   2/3                Crustle 150/150
            Tapu Bulu              2/4                Great Tusk 140/140
            Dipplin                1/1  READY
            Dipplin                1/1  READY        stadium: Neutralization Zone (theirs)
    hand    2 Grass, Hydrapple ex, Tapu Bulu, Meganium, Fezandipiti ex,
            2 Ultra Ball, 2 Night Stretcher, Dawn

The whole turn was there: Grass on the Meowth ex (retreat cost 1), retreat,
promote a Dipplin and hit the Great Tusk for 100 (Do the Wave, 20 x 5 bench).
What the agent played instead was one Grass onto the benched Tapu Bulu (28000,
"Tapu Bulu is the main attacker vs Crustle") and END. It had not attacked for
turns and it never did again.

Why the line was invisible: `_grass_unlocks_active_retreat` measures the chip
damage of the relay through `_bench_attacker_best_damage(min_body_hp=...)`, and
with one of our ex in the active spot that floor is the ex's own HP -- the "do
not swap an ex for a worse body" guard of the retreat scorer. 170. Under their
Neutralization Zone our ex do zero damage to a 1-prize active, so the ONLY
bodies that could hurt the Great Tusk were the non-ex ones, all smaller than
170: Dipplin (80) and Tapu Bulu (140) were discarded before their damage was
even read, chip came out 0, and both the attachment flag and the retreat itself
switched off.

The fix is the reading the promotion menu already makes (the mute ex that
yields to the body that hits the wall), moved one step earlier: an ex with NO
entry in `ATTACK_ENERGY_REQ` -- Meowth ex, our draw engine -- can never turn
energy into damage, so the 170 HP it "endures" buys nothing except the two
prizes it eventually hands over. `_ex_active_is_a_wall` says so, and where the
HP floor drops the guard keeps its other half, the one the Archaludon case was
really about: the body coming up may not hand over MORE prizes than the one
going down.

Coverage:
  * the record's board: the Grass goes to the ACTIVE, not to the benched Tapu;
  * the retreat that follows is not vetoed (both halves must agree, or the
    energy is spent on a retreat that never happens);
  * the promotion brings up a Dipplin, and the promoted Dipplin attacks;
  * which ex is a wall, read on the helper;
  * detector boundaries -- the same board with a Hydrapple ex on 170 HP (an ex
    we DO attack with) keeps the floor and stays switched off, and the same
    Hydrapple on 80 HP switches back on, so it is the floor that was holding it;
  * the half of the guard that survives: a relay handing over more prizes than
    the body going down is not counted.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m
from cg.api import AreaType, OptionType
from state_builder import Scenario, pk

GRASS = m.Basic_Grass_Energy
MEOWTH = m.Meowth_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu
DIPPLIN = m.Dipplin
APPLIN = m.Applin
HYDRAPPLE = m.Hydrapple_ex
ZONE = m.Neutralization_Zone

OP_GREAT_TUSK = 58
OP_CRUSTLE = m.Crustle_Grass
OP_DWEBBLE = m.Dwebble_Grass

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "great_tusk_step104_the_mute_ex_pays_the_retreat.json")


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


def _obs_step104():
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _attach_target(obs, choice):
    """Where the chosen ATTACH points: 'active' / 'bench-k'."""
    assert choice, f"the agent ended the turn: {choice}"
    opt = obs["select"]["option"][choice[0]]
    assert opt["type"] == int(OptionType.ATTACH), f"expected an ATTACH, got {opt}"
    if opt.get("inPlayArea") == int(AreaType.ACTIVE):
        return "active"
    return f"bench-{opt.get('inPlayIndex')}"


# ---------------------------------------------------------------------------
# 1. The record: without this board the test measures nothing
# ---------------------------------------------------------------------------

def test_step104_the_board_is_the_records_one():
    obs = _obs_step104()
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert cur["energyAttached"] is False
    assert mine["active"][0]["id"] == MEOWTH
    assert mine["active"][0]["energies"] == []
    assert m.RETREAT_COST[MEOWTH] == 1
    # Meowth ex is not a body we attack with: no amount of energy changes that.
    assert m.AGENT_STATE.ATTACK_ENERGY_REQ.get(MEOWTH) is None
    assert [p["id"] for p in mine["bench"]] == [OGERPON, OGERPON, TAPU,
                                                DIPPLIN, DIPPLIN]
    # The two Dipplin are ready; nothing else on the bench is.
    assert [len(p["energies"]) for p in mine["bench"]] == [2, 2, 2, 1, 1]
    assert sum(1 for c in mine["hand"] if c["id"] == GRASS) == 2
    assert theirs["active"][0]["id"] == OP_GREAT_TUSK
    assert cur["stadium"][0]["id"] == ZONE, "their Neutralization Zone is the point"


def test_step104_the_grass_pays_the_retreat_of_the_mute_ex():
    obs = _obs_step104()
    assert _attach_target(obs, m.agent(obs)) == "active", (
        "the Meowth ex has no attack: the only thing its energy can buy is the "
        "retreat that brings up the Dipplin, the one body the Zone has not "
        "switched off")


# ---------------------------------------------------------------------------
# 2. The rest of the chain: an attachment whose retreat is vetoed is worse
#    than no attachment at all
# ---------------------------------------------------------------------------

def _board(active=None, bench=None, hand=(), energy_played=True):
    """The record's board, parameterised. The Grass is already on the active."""
    sc = (Scenario(turn=24, step=105, tac=2, first_player=1,
                   energy_played=energy_played)
          .my_active(active if active is not None
                     else pk(MEOWTH, energies=1, fisicas=1))
          .my_bench(*(bench if bench is not None else [
              pk(OGERPON, energies=2, fisicas=2),
              pk(OGERPON, energies=2, fisicas=2),
              pk(TAPU, energies=2, fisicas=2),
              pk(DIPPLIN, pre_evo=[APPLIN], energies=1, fisicas=1),
              pk(DIPPLIN, pre_evo=[APPLIN], energies=1, fisicas=1)]))
          .my_hand(*hand)
          .op_active(pk(OP_GREAT_TUSK, hp=140, max_hp=140, energies=1))
          .op_bench(pk(OP_CRUSTLE, hp=50, max_hp=150, pre_evo=[OP_DWEBBLE]),
                    pk(OP_CRUSTLE, pre_evo=[OP_DWEBBLE]),
                    pk(OP_GREAT_TUSK, hp=140, max_hp=140))
          .stadium(ZONE, of_the_opponent=True)
          .op_zones(hand=10, deck=6, prizes=6))
    return sc


def test_the_retreat_is_not_vetoed_once_the_grass_is_there():
    obs = _board().menu_hand(with_retreat=True).build()
    options = obs["select"]["option"]
    retreat = next(i for i, o in enumerate(options)
                   if o["type"] == int(OptionType.RETREAT))
    assert m.agent(obs) == [retreat], (
        "the guard that vetoed this retreat is the same one that hid the "
        "attachment: if only one of the two halves is fixed, the Grass is "
        "spent on a retreat that never happens")


def test_the_promotion_brings_up_a_dipplin():
    obs = _board().promote_after_retreat().build()
    choice = m.agent(obs)
    opt = obs["select"]["option"][choice[0]]
    mine = obs["current"]["players"][0]
    promoted = mine["bench"][opt["index"]]
    assert promoted["id"] == DIPPLIN, (
        f"expected a Dipplin -- the only body that damages their Great Tusk "
        f"under the Zone -- got {promoted['id']}")


def test_the_promoted_dipplin_attacks():
    obs = (_board(active=pk(DIPPLIN, pre_evo=[APPLIN], energies=1, fisicas=1),
                  bench=[pk(OGERPON, energies=2, fisicas=2),
                         pk(OGERPON, energies=2, fisicas=2),
                         pk(TAPU, energies=2, fisicas=2),
                         pk(DIPPLIN, pre_evo=[APPLIN], energies=1, fisicas=1),
                         pk(MEOWTH)])
           .menu_hand(with_attack=True).build())
    options = obs["select"]["option"]
    attacks = [i for i, o in enumerate(options)
               if o["type"] == int(OptionType.ATTACK)]
    assert attacks, "the promoted Dipplin can pay its attack"
    assert m.agent(obs)[0] in attacks, (
        "the end of the chain: 100 damage on their Great Tusk instead of a "
        "turn that ends without attacking")


# ---------------------------------------------------------------------------
# 3. The reading itself: which ex is a wall
# ---------------------------------------------------------------------------

def test_only_an_ex_we_attack_with_is_a_wall():
    body = lambda cid: SimpleNamespace(id=cid)   # it only reads the id
    assert m._ex_active_is_a_wall(body(MEOWTH)) is False, (
        "Meowth ex has no entry in ATTACK_ENERGY_REQ: no energy ever makes it "
        "damage, so its HP is not defending anything")
    for _wall in (HYDRAPPLE, OGERPON, m.Fezandipiti_ex):
        assert m._ex_active_is_a_wall(body(_wall)) is True
    # Not one of our ex: the guard never applied there in the first place.
    assert m._ex_active_is_a_wall(body(DIPPLIN)) is False
    assert m._ex_active_is_a_wall(None) is False


# ---------------------------------------------------------------------------
# 4. Detector boundaries: what changed is the HP floor and nothing else
# ---------------------------------------------------------------------------

def _detector(obs):
    """(ko, chip) of the shared core over the built board, under their Zone."""
    st = m.to_observation_class(obs).current
    mine, theirs = st.players[0], st.players[1]
    total_grass = sum(len(p.energies)
                      for p in ([mine.active[0]] if mine.active else [])
                      + list(mine.bench) if p is not None)
    return m._grass_unlocks_active_retreat(
        mine, theirs, False, total_grass, len(mine.bench), True, False)


def test_the_detector_sees_the_chip_line_on_the_records_board():
    obs = _board(active=pk(MEOWTH), hand=[GRASS],
                 energy_played=False).menu_hand(with_attachment=True).build()
    assert _detector(obs) == (False, True), (
        "no knockout (Do the Wave does 100 to a 140 HP Great Tusk) but 100 of "
        "chip is infinitely better than the zero the turn was scoring")


def test_an_ex_we_attack_with_keeps_the_hp_floor():
    """The same board with the SAME numbers on the active -- 170 HP, one Grass
    short of its retreat -- but a Hydrapple ex instead of the Meowth ex. That
    one is a body we attack with, the floor stays at 170, and every hitter the
    Zone leaves us is smaller: the line does not switch on."""
    obs = (_board(active=pk(HYDRAPPLE, hp=170, max_hp=170,
                            pre_evo=[APPLIN, DIPPLIN], energies=2, fisicas=2),
                  bench=[pk(OGERPON, energies=2, fisicas=2),
                         pk(OGERPON, energies=2, fisicas=2),
                         pk(TAPU, energies=2, fisicas=2),
                         pk(DIPPLIN, pre_evo=[APPLIN], energies=1, fisicas=1)],
                  hand=[GRASS], energy_played=False)
           .menu_hand(with_attachment=True).build())
    assert m.RETREAT_COST[HYDRAPPLE] - 2 == 1, "one Grass short, like the Meowth"
    assert _detector(obs) == (False, False)


def test_and_it_is_the_floor_that_is_holding_it_back():
    """Proof that the previous control is the HP floor and not some other
    precondition: the same Hydrapple ex board with the wall down to 80 HP lets
    the 80 HP Dipplin through, and the line switches on again."""
    obs = (_board(active=pk(HYDRAPPLE, hp=80, max_hp=330,
                            pre_evo=[APPLIN, DIPPLIN], energies=2, fisicas=2),
                  bench=[pk(OGERPON, energies=2, fisicas=2),
                         pk(OGERPON, energies=2, fisicas=2),
                         pk(TAPU, energies=2, fisicas=2),
                         pk(DIPPLIN, pre_evo=[APPLIN], energies=1, fisicas=1)],
                  hand=[GRASS], energy_played=False)
           .menu_hand(with_attachment=True).build())
    assert _detector(obs) == (False, True)


def test_the_pivot_to_a_bigger_wall_still_stands():
    """A way OUT was added, none was taken away. Caught in the shadow: gating
    the "pivot to an equal or bigger wall" branch on the active being a wall
    turned a legal retreat into an END. Their Crustle is immune to our ex, so
    NOTHING on the bench does damage; the only thing the turn can still buy is
    a bigger body in front, and that is worth buying."""
    obs = (_board(active=pk(MEOWTH, energies=2, fisicas=2),
                  bench=[pk(OGERPON, energies=4, fisicas=4),
                         pk(TAPU, energies=2, fisicas=2)])
           .op_active(pk(OP_CRUSTLE, hp=250, max_hp=250, energies=2,
                         pre_evo=[OP_DWEBBLE]))
           .menu_hand(with_retreat=True).build())
    options = obs["select"]["option"]
    retreat = next(i for i, o in enumerate(options)
                   if o["type"] == int(OptionType.RETREAT))
    assert m.agent(obs) == [retreat], (
        "the 210 HP Ogerpon ex takes the front from the 170 HP Meowth ex: same "
        "prizes, one more turn of life")


def test_the_relay_may_not_hand_over_more_prizes_than_the_body_going_down():
    """The half of the guard that survives when the HP floor drops. Read on the
    helper, because our own deck has no 3-prize body to build the board with:
    a relay that hands over more than the ex going down is not counted."""
    obs = _board(active=pk(MEOWTH), hand=[GRASS],
                 energy_played=False).menu_hand(with_attachment=True).build()
    st = m.to_observation_class(obs).current
    mine, theirs = st.players[0], st.players[1]
    assert m._bench_attacker_best_damage(
        mine, theirs.active[0], False, len(mine.bench), 0, True,
        max_prizes=2) == 100, "the 1-prize Dipplin counts under a cap of 2"
    assert m._bench_attacker_best_damage(
        mine, theirs.active[0], False, len(mine.bench), 0, True,
        max_prizes=0) == 0, "under a cap of 0 nothing on this bench qualifies"
