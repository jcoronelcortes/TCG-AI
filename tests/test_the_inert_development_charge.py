"""When nothing else uses the Grass, the retreat fee takes it.

Scenario (user, episode 90316244, turn 8 vs Mega Venusaur ex, WON with a
sterile turn). The turn opens at step 44 like this:

    US                                       RIVAL
    active  Meowth ex 170/170, 0 energy      active  --
    bench   Meganium 0/4, Meowth ex 20 HP    bench   Meowth ex, Meganium,
    hand    Dipplin, Chikorita,                      Meowth ex 20 HP
            Unfair Stamp, 1 Grass

With no attacker on the bench, "the retreat fee needs somebody to hand over
to" demotes the charge on the active to 7500 and the Grass goes to the Meganium
(7950). But the Meganium is not an attacker being assembled either: one
attachment leaves it at 2 of the 4 it needs and nothing this turn closes the
gap. BOTH destinations are inert, and only one of them can still be SPENT.

What that cost, play by play: the turn went on to build a Hydrapple ex on the
bench (Unfair Stamp -> Bug Catching Set -> Applin -> Dipplin -> Hydrapple ex),
so the pivot the fee pays for did exist -- it just was not on the board yet when
the energy was committed. Bringing the Hydrapple up costs a retreat, the retreat
costs energy on the active, and the only charging route still alive that can
reach the active is Ripening Charge. So the ability that should have charged the
Hydrapple paid the retreat instead: the Grass went hand -> active -> discard,
the Hydrapple ex was promoted at 0 energy and the engine offered nothing but
END.

That is the answer to "why did it not charge the Hydrapple with its own ability
and attack?": the ability had already been spent, on the very body that was
retreated. With the Grass on the active from the start, Ripening Charge charges
the Hydrapple that comes up and the promoted Hydrapple attacks.

The rule (`_fee_beats_parking_it` in ptcg/turn/energy.py) is a TIE-BREAK inside
the development band, and it is deck-agnostic: it reads a retreat cost, a bench
and the charging routes still alive, never a particular attacker. It yields
whenever the energy has a real use -- a body that reaches its attack cost with
it, an attacker being assembled, or a charging ability that attaches the same
Grass for free.

Coverage:
  * the record's board: the Grass takes the fee instead of the inert Meganium;
  * control -- a Meganium at 2 of 4 IS one Grass from attacking: the bench wins;
  * control -- with a live Teal Dance the fee still yields (the measured case of
    `records/registro_002`, an active Chikorita with a benched Ogerpon);
  * the payoff, step by step: Ripening Charge goes to the body coming up, the
    retreat is paid and the promoted Hydrapple ex can attack.
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
STAMP = m.Unfair_Stamp
MEOWTH = m.Meowth_ex
MEGANIUM = m.Meganium
HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
APPLIN = m.Applin
DIPPLIN = m.Dipplin
FEZA = m.Fezandipiti_ex
OP_MEOWTH = 1071        # the 170 HP body their active was on turn 8
OP_BULBASAUR = 92       # a bench body of their Venusaur line

_FIXTURE = ROOT / "tests" / "fixtures" / "venusaur_step44_inert_development_charge.json"


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


def _obs_step44():
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _target(obs, choice):
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

def test_step44_the_board_is_the_records_one():
    obs = _obs_step44()
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]

    assert cur["turn"] == 8
    assert cur["energyAttached"] is False
    assert mine["active"][0]["id"] == MEOWTH
    assert mine["active"][0]["energies"] == []
    assert sum(1 for c in mine["hand"] if c["id"] == GRASS) == 1
    # Every destination is inert: the Meganium needs 4 and one attachment
    # leaves it at 2, and the other body is a 20 HP Meowth ex.
    assert [p["id"] for p in mine["bench"]] == [MEGANIUM, MEOWTH]
    assert all(p["energies"] == [] for p in mine["bench"])


def test_step44_the_fee_takes_the_grass_from_the_inert_bench():
    obs = _obs_step44()
    assert _target(obs, m.agent(obs)) == "active", (
        "the only energy that can still become a play this turn is the one on "
        "the active: it pays the retreat that brings up the attacker the turn "
        "has not built yet")


# ---------------------------------------------------------------------------
# 2. Controls: the fee only wins when nothing else uses the energy
# ---------------------------------------------------------------------------

def _board(bench, hand=(GRASS,), teal_dance_bearer=False):
    bench = list(bench)
    if teal_dance_bearer:
        bench.append(pk(OGERPON))
    return (Scenario(turn=8, step=44, tac=1, first_player=1)
            .my_active(pk(MEOWTH))
            .my_bench(*bench)
            .my_hand(*hand)
            .op_active(pk(OP_MEOWTH, hp=170, max_hp=170))
            .op_bench(pk(OP_BULBASAUR, hp=40, max_hp=40))
            .op_zones(hand=4, deck=30, prizes=5)
            .menu_hand(with_attachment=True)
            .build())


def test_a_body_that_reaches_its_cost_with_this_grass_beats_the_fee():
    """A Meganium at 2 of the 4 it needs is one Grass from attacking."""
    obs = _board([pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF], energies=2,
                     fisicas=1)])
    assert _target(obs, m.agent(obs)).startswith("bench"), (
        "this Grass leaves the Meganium ready: that is progress, the fee is not")


def test_with_a_live_teal_dance_the_fee_still_yields():
    """The measured case (`records/registro_002`): an active Chikorita, a
    benched Ogerpon at 0 energy and one Grass in hand. Teal Dance attaches the
    same Grass to the body being assembled AND draws a card, so the manual
    attachment is not spent on a retreat fee. The Ogerpon cannot attack today,
    so it is precisely the branch where the fee had nothing to hand over to."""
    obs = (Scenario(turn=2, step=18, tac=1, first_player=1)
           .my_active(pk(CHIKORITA))
           .my_bench(pk(OGERPON), pk(APPLIN))
           .my_hand(GRASS)
           .op_active(pk(OP_MEOWTH, hp=170, max_hp=170))
           .op_zones(hand=4, deck=30, prizes=6)
           .menu_hand(with_attachment=True)
           .build())
    assert _target(obs, m.agent(obs)) != "active", (
        "with a charging ability still alive the manual attachment is not spent "
        "on a retreat fee")


# ---------------------------------------------------------------------------
# 3. The payoff: the turn that the record could not play
# ---------------------------------------------------------------------------

def _after_the_refresh(active_energy, hydrapple_energy=0):
    """The same turn once the Unfair Stamp and the Bug Catching Set have built
    the Hydrapple ex on the bench."""
    return (Scenario(turn=8, step=53, tac=8, first_player=1,
                     supporter_played=True, energy_played=True)
            .my_active(pk(MEOWTH, energies=active_energy,
                          fisicas=1 if active_energy else 0))
            .my_bench(pk(HYDRAPPLE, pre_evo=[APPLIN, DIPPLIN],
                         energies=hydrapple_energy,
                         fisicas=1 if hydrapple_energy else 0),
                      pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
                      pk(FEZA))
            .my_hand(GRASS)
            .op_active(pk(OP_MEOWTH, hp=170, max_hp=170))
            .op_bench(pk(OP_BULBASAUR, hp=40, max_hp=40))
            .op_zones(hand=4, deck=30, prizes=5))


def test_ripening_charge_goes_to_the_body_coming_up():
    """The fee is already paid: the ability charges the future attacker, not
    the body whose energy the retreat is about to discard."""
    obs = _after_the_refresh(active_energy=2).ability_charge_target(bench_idx=0).build()
    choice = m.agent(obs)
    opt = obs["select"]["option"][choice[0]]
    assert (opt["area"], opt["index"]) == (int(AreaType.BENCH), 0), (
        "Ripening Charge went to a body that is leaving")


def test_the_promoted_hydrapple_can_attack():
    """The end of the chain: charged on the bench, it comes up able to pay
    Syrup Storm -- which is what the record's turn never got to."""
    obs = (_after_the_refresh(active_energy=2, hydrapple_energy=2)
           .promote_after_retreat()
           .build())
    choice = m.agent(obs)
    opt = obs["select"]["option"][choice[0]]
    assert opt["index"] == 0, f"expected to promote the Hydrapple ex, got {opt}"

    mine = obs["current"]["players"][0]
    promoted = mine["bench"][opt["index"]]
    assert m._can_attack_eff(promoted["id"], len(promoted["energies"])), (
        "the promoted body cannot pay an attack: the turn closes sterile again")
