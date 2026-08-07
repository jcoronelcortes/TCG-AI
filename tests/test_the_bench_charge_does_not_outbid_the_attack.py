"""The matchup's favourite body does not outbid the Grass that buys the attack.

Scenario (user, episode 90319176, turn 28 vs a Crustle / Great Tusk deck, WON
with the mistake still in it). The turn opens at step 147:

    US (1 prize left)                         RIVAL (5 prizes left)
    active  Meganium 160/160, 0 energy        active  Great Tusk 140/140
    bench   Dipplin  80/80, 1 Grass  READY    bench   Great Tusk 140/140, 1 energy
            Dipplin  80/80, 0
            Tapu Bulu 140/140, 0
            Teal Mask Ogerpon ex 210/210, 0
            Chikorita 70/70, 0                stadium: Forest of Vitality (ours)
    hand    Basic Grass, Hydrapple ex, Teal Mask Ogerpon ex, Fezandipiti ex,
            Unfair Stamp, Xerosic's Machinations

The whole turn was there, and Wild Growth is what pays for it: Meganium's
ability makes every basic Grass count as {G}{G}, so the ONE Grass in hand
covers its retreat cost of 2 by itself. Grass on the active, retreat, promote
the charged Dipplin, Do the Wave for 100 (20 x 5 bench) on their Great Tusk.
Meganium itself could do nothing -- Solar Beam costs 4 and it had zero.

What the agent played was that Grass onto the benched Tapu Bulu, and END.

The line was NOT invisible: `_grass_unlocks_active_retreat` saw it and
`_attach_enable_retreat_attack` scored the attachment to the active at 31200,
the band whose own comment reads "above any bench charge (<= 31150)". That
invariant held for the generic development bands (~8000) and broke against the
per-matchup branches of `_energy_score_base`, which return up to 44000: vs
Crustle a benched Tapu Bulu below its four effective energies is worth
8000 + 20000 (the matchup's main attacker) + 11000 (a Chikorita on the bench)
= 39000. It outbid the attack by 7800 points.

Those branches answer "which body do I develop", a question that only comes up
when the energy is not doing anything better. Here the alternative was
ATTACKING, and the ceiling in the `energy_score` wrapper says so:
`SCORE_BENCH_YIELDS_TO_RETREAT_UNLOCK`, applied only while the chip variant of
the line is live -- which is to say only while the active has no attack of its
own this turn -- and only below the lethal floor.

It is a ceiling and not a veto, and it keeps the relative order among benched
bodies: the matchup still decides WHERE the Grass goes when the active does not
take it.

Coverage:
  * the record's board: the Grass goes to the ACTIVE, not to the benched Tapu;
  * the rest of the chain -- the retreat is not vetoed, the promotion brings up
    the CHARGED Dipplin, and that Dipplin attacks;
  * the reason it is deck-agnostic: the same board with the Crustle branch off
    still routes the Grass to the active;
  * the boundaries, which are what keeps the matchup priority alive -- with the
    active already able to retreat, or with no ready body on the bench, the
    line is off and the benched Tapu Bulu gets the energy back;
  * the calibration of the constant against the bands it sits between.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m
from cg.api import AreaType, OptionType
from state_builder import Scenario, pk

GRASS = m.Basic_Grass_Energy
MEGANIUM = m.Meganium
CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
DIPPLIN = m.Dipplin
APPLIN = m.Applin
TAPU = m.Tapu_Bulu
OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRAPPLE = m.Hydrapple_ex
FEZANDIPITI = m.Fezandipiti_ex
FOREST = m.Forest_of_Vitality

OP_GREAT_TUSK = 58
OP_CRUSTLE = m.Crustle_Grass
OP_DWEBBLE = m.Dwebble_Grass

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "great_tusk_step147_wild_growth_pays_the_retreat.json")


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


def _obs_step147():
    """The record's observation, with the one piece of history it depends on.

    By turn 28 both of their Crustle were already in the discard, so the board
    alone no longer names the matchup: `op_is_crustle_deck` is STICKY on
    purpose (`_update_cards_tracking` only clears it on a new game) and it was
    on when the decision was taken. Replaying the frame cold would switch off
    the very branches that produced the mistake -- and the branch that scored
    the benched Tapu Bulu at 39000 is the whole point of this test.
    """
    with open(_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    m.AGENT_STATE.op_is_crustle_deck = True
    return obs


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

def test_step147_the_board_is_the_records_one():
    obs = _obs_step147()
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert cur["energyAttached"] is False
    # The active: Meganium with nothing on it. Solar Beam costs 4, its retreat
    # costs 2 -- it can neither attack nor move.
    assert mine["active"][0]["id"] == MEGANIUM
    assert mine["active"][0]["energies"] == []
    assert m.RETREAT_COST[MEGANIUM] == 2
    assert m.AGENT_STATE.ATTACK_ENERGY_REQ[MEGANIUM] == 4
    # ...and Wild Growth is what makes ONE Grass enough for that retreat.
    assert [p["id"] for p in mine["bench"]] == [DIPPLIN, DIPPLIN, TAPU,
                                                OGERPON, CHIKORITA]
    # One Dipplin is ready (one physical Grass doubled to {G}{G} by Wild
    # Growth, and Do the Wave costs 1); nothing else on the bench is.
    assert [len(p["energies"]) for p in mine["bench"]] == [2, 0, 0, 0, 0]
    assert len(mine["bench"][0]["energyCards"]) == 1
    assert m.AGENT_STATE.ATTACK_ENERGY_REQ[DIPPLIN] == 1
    assert sum(1 for c in mine["hand"] if c["id"] == GRASS) == 1, (
        "one Grass: the whole turn is about where it lands")
    assert theirs["active"][0]["id"] == OP_GREAT_TUSK
    assert theirs["active"][0]["hp"] == 140


def test_step147_the_grass_pays_the_retreat_of_the_mute_meganium():
    obs = _obs_step147()
    assert _attach_target(obs, m.agent(obs)) == "active", (
        "Meganium has 0 of the 4 energies Solar Beam costs: the only thing "
        "this Grass can buy today is the retreat that brings up the Dipplin. "
        "The benched Tapu Bulu is worth 39000 to the Crustle branch and the "
        "attack was worth 31200")


def test_step147_the_recorded_play_was_the_bench():
    """What the agent actually did, so the fixture is not silently rewritten."""
    with open(_FIXTURE, encoding="utf-8") as f:
        fx = json.load(f)
    played = fx["observation"]["select"]["option"][fx["recorded_action"][0]]
    assert played["inPlayArea"] == int(AreaType.BENCH)
    assert played["inPlayIndex"] == 2, "bench slot 2 was the Tapu Bulu"


# ---------------------------------------------------------------------------
# 2. The rest of the chain: an attachment whose retreat never happens is worse
#    than no attachment at all
# ---------------------------------------------------------------------------

def _board(active=None, bench=None, hand=(), energy_played=True,
           op_bench=None):
    """The record's board, parameterised. By default the Grass is already on
    the active Meganium (one physical card, {G}{G} through Wild Growth)."""
    return (Scenario(turn=28, step=148, tac=2, first_player=0,
                     energy_played=energy_played, own_prizes=1)
            .my_active(active if active is not None
                       else pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF],
                               energies=2, fisicas=1))
            .my_bench(*(bench if bench is not None else [
                pk(DIPPLIN, pre_evo=[APPLIN], energies=2, fisicas=1),
                pk(DIPPLIN, pre_evo=[APPLIN]),
                pk(TAPU),
                pk(OGERPON),
                pk(CHIKORITA)]))
            .my_hand(*hand)
            .stadium(FOREST)
            .op_active(pk(OP_GREAT_TUSK, hp=140, max_hp=140))
            .op_bench(*(op_bench if op_bench is not None else [
                pk(OP_GREAT_TUSK, hp=140, max_hp=140, energies=1),
                pk(OP_CRUSTLE, pre_evo=[OP_DWEBBLE])]))
            .op_zones(hand=5, deck=8, prizes=5))


def test_the_retreat_is_not_vetoed_once_the_grass_is_there():
    obs = _board().menu_hand(with_retreat=True).build()
    options = obs["select"]["option"]
    retreat = next(i for i, o in enumerate(options)
                   if o["type"] == int(OptionType.RETREAT))
    assert m.agent(obs) == [retreat], (
        "both halves have to agree: an attachment that enables a retreat the "
        "scorer then vetoes spends the turn's energy on nothing")


def test_the_promotion_brings_up_the_charged_dipplin():
    obs = _board().promote_after_retreat().build()
    choice = m.agent(obs)
    opt = obs["select"]["option"][choice[0]]
    promoted = obs["current"]["players"][0]["bench"][opt["index"]]
    assert promoted["id"] == DIPPLIN and promoted["energies"], (
        f"expected the Dipplin that can pay Do the Wave TODAY, got "
        f"{promoted['id']} with {len(promoted['energies'])} energies")


def test_the_promoted_dipplin_attacks():
    obs = (_board(active=pk(DIPPLIN, pre_evo=[APPLIN], energies=2, fisicas=1),
                  bench=[pk(DIPPLIN, pre_evo=[APPLIN]),
                         pk(TAPU),
                         pk(OGERPON),
                         pk(CHIKORITA),
                         pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF])])
           .menu_hand(with_attack=True).build())
    attacks = [i for i, o in enumerate(obs["select"]["option"])
               if o["type"] == int(OptionType.ATTACK)]
    assert attacks, "the promoted Dipplin can pay its attack"
    assert m.agent(obs)[0] in attacks, (
        "the end of the chain: 100 damage on their Great Tusk instead of a "
        "turn that ends without attacking")


# ---------------------------------------------------------------------------
# 3. Deck-agnostic: the Crustle branch is the offender that was measured, not
#    the rule
# ---------------------------------------------------------------------------

def test_without_the_crustle_matchup_the_grass_still_pays_the_retreat():
    """The same shape with no Crustle anywhere: the ceiling never fires (no
    bench charge climbs that high) and the line has to hold on its own."""
    obs = (_board(active=pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
                  hand=[GRASS], energy_played=False,
                  op_bench=[pk(OP_GREAT_TUSK, hp=140, max_hp=140, energies=1)])
           .menu_hand(with_attachment=True).build())
    assert m.AGENT_STATE.op_is_crustle_deck is False
    assert _attach_target(obs, m.agent(obs)) == "active"


# ---------------------------------------------------------------------------
# 4. Boundaries: the ceiling only exists while the turn would be sterile
# ---------------------------------------------------------------------------

def _blocked_active_board(active_cards):
    """The same relay, behind a Meowth ex carrying `active_cards` physical Grass.

    Meowth ex is the cleanest probe for this boundary: it has no attack in any
    state of the game, so no finisher rule can claim the energy and the only
    thing the charge can ever buy is the retreat. Its cost is 1, which Wild
    Growth covers with a single card -- so ONE physical Grass already on it is
    the difference between "the retreat is blocked" and "the retreat is paid".
    Meganium moves to the bench, where its ability keeps doubling all the same.
    """
    return (_board(active=pk(m.Meowth_ex, energies=active_cards * 2,
                             fisicas=active_cards),
                   bench=[pk(DIPPLIN, pre_evo=[APPLIN], energies=2, fisicas=1),
                          pk(DIPPLIN, pre_evo=[APPLIN]),
                          pk(TAPU),
                          pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
                          pk(CHIKORITA)],
                   hand=[GRASS], energy_played=False)
            .menu_hand(with_attachment=True).build())


def test_the_blocked_active_takes_the_grass():
    """The control of the pair below, and the rule stated without Meganium in
    the active spot: any body that cannot move and cannot attack."""
    obs = _blocked_active_board(0)
    assert _attach_target(obs, m.agent(obs)) == "active"


def test_with_the_active_already_able_to_retreat_the_bench_gets_the_energy():
    """`_grass_unlocks_active_retreat` returns nothing when the active ALREADY
    pays its retreat: there is no retreat to unlock. One physical Grass on the
    Meowth ex is that case -- the ceiling switches off and the matchup's
    priority (the benched Tapu Bulu) rules again."""
    obs = _blocked_active_board(1)
    assert _attach_target(obs, m.agent(obs)) == "bench-2", (
        "the active does not need this Grass to move: the ceiling must not "
        "steal it from the body the matchup wants charged")


def test_with_no_ready_body_on_the_bench_the_ceiling_is_off():
    """No relay that can attack today -> no line to protect. The Grass goes
    back to the body the Crustle matchup wants charged."""
    obs = (_board(active=pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
                  bench=[pk(DIPPLIN, pre_evo=[APPLIN]),
                         pk(DIPPLIN, pre_evo=[APPLIN]),
                         pk(TAPU),
                         pk(OGERPON),
                         pk(CHIKORITA)],
                  hand=[GRASS], energy_played=False)
           .menu_hand(with_attachment=True).build())
    assert _attach_target(obs, m.agent(obs)) != "active", (
        "with nothing ready to promote, paying Meganium's retreat buys a "
        "sterile turn just the same")


# ---------------------------------------------------------------------------
# 5. The calibration of the constant: it is the whole point of the fix
# ---------------------------------------------------------------------------

def test_the_ceiling_sits_between_the_bands_it_arbitrates():
    assert m.SCORE_BENCH_YIELDS_TO_RETREAT_UNLOCK < 31200, (
        "it has to leave room UNDER the attachment to the active (31200) and "
        "under its ability twin (31250): that is what it is for")
    assert m.SCORE_BENCH_YIELDS_TO_RETREAT_UNLOCK < m.SCORE_CHARGE_LETHAL_FLOOR
    assert m.SCORE_BENCH_YIELDS_TO_RETREAT_UNLOCK > 9000, (
        "and well above the development band, so a capped bench charge is "
        "still preferred to the plays that do nothing this turn")
