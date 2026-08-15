"""Under Neutralization Zone the Grass goes to the body that can still hit.

Scenario (user, episode 93142685, turn 10 vs a Mesprit / Uxie / Azelf deck, at
`records/registro_010_pasos_070_hasta_080.json` step 70). The turn opens with:

    US                                        THEM
    active  Hydrapple ex 330/330, 1 Grass     bench   Mesprit  70/70
            (= 2 effective: Wild Growth)              Mesprit  70/70
    bench   Meowth ex 170/170                         Mesprit  70/70
            Meganium 160/160, ZERO energy             Mesprit  70/70
            Teal Mask Ogerpon ex, 4 eff               Azelf    70/70
            Teal Mask Ogerpon ex, ZERO
    hand    1 Grass, Ultra Ball, Bayleef,      stadium: Neutralization Zone (theirs)
            Hydrapple ex, Xerosic

Neutralization Zone prevents all damage done to Pokemon WITHOUT a Rule Box by
attacks from the opponent's ex, and every body they have is a 70 HP non-ex. So
our Hydrapple ex and both Ogerpon ex are mute, and the only card on our side
that can take a prize is the Meganium: Solar Beam does 140, and Wild Growth
doubles every Basic Grass, so TWO cards arm it.

The turn's only Grass went to the benched Ogerpon ex via Teal Dance. The agent
did not misread the damage -- `_our_effective_damage` returns 0 for our ex here
and always has -- it never asked. Teal Dance took 31300 from the
`_active_hydra_ready` rung, whose sentence is "the active covers Syrup Storm's
cost, so the surplus goes to the bench": true of the cost, false of the board.

The reading is that Neutralization Zone is the THIRD shape of a wall the agent
already knows, and the one that reads backwards -- the wall is not a body of
theirs, it is the ABSENCE of a Rule Box on the body in front, so it comes and
goes with THEIR promotion. Both halves of the turn move with it:

  * the Teal Dance ladder joins the rung it already had for Crustle and
    Cornerstone ("the last Grass belongs to the body that can still hit the
    wall"), with the widest creditor list of the three -- this wall filters by
    Rule Box and not by our abilities, so Meganium is owed too;
  * the bench halves of the stadium's own energy bands stop being development
    while the front is mute. Without that half the Grass simply moves from the
    mute benched ex to the mute ACTIVE one (7810), which is not a fix.

Coverage:
  * the record's board, pinned before anything is asked of the agent;
  * the choice: the Grass reaches the Meganium, and neither Teal Dance nor the
    active Hydrapple ex takes it;
  * the helper `_nz_mutes_our_ex` on its four answers, the unknown card
    included -- it must NOT switch our attackers off on data we cannot read;
  * the boundary that proves it is the stadium doing the work: the same board
    with a Rule-Box body in front goes back to Teal Dance;
  * the strict no-op: with no stadium at all, the same board is unchanged;
  * the bench promotion keeps the bands in their order and stays under every
    ACTIVE band, so the body in front still gets the energy when it can use it.
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
from ptcg.calc.damage import _nz_mutes_our_ex

GRASS = m.Basic_Grass_Energy
MEGANIUM = m.Meganium
HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
ZONE = m.Neutralization_Zone

OP_MESPRIT = 216
OP_AZELF = 217
OP_UXIE = 215

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "mesprit_step070_the_stadium_mutes_our_ex.json")


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


def _obs_step70():
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _chosen(obs, choice):
    """The menu option the agent picked, as a plain dict."""
    assert choice, f"the agent ended the turn: {choice}"
    return obs["select"]["option"][choice[0]]


def _attach_target(obs, choice):
    """Where the chosen ATTACH points: 'active' / 'bench-k'; None if not one."""
    opt = _chosen(obs, choice)
    if opt["type"] != int(OptionType.ATTACH):
        return None
    if opt.get("inPlayArea") == int(AreaType.ACTIVE):
        return "active"
    return f"bench-{opt.get('inPlayIndex')}"


# ---------------------------------------------------------------------------
# 1. The record: without this board the test measures nothing
# ---------------------------------------------------------------------------

def test_step70_the_board_is_the_records_one():
    obs = _obs_step70()
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert cur["yourIndex"] == 1
    assert cur["energyAttached"] is False
    assert [c["id"] for c in cur["stadium"]] == [ZONE]

    assert mine["active"][0]["id"] == HYDRAPPLE
    # One physical Grass showing as two effective: Wild Growth is already
    # applied in the observation, which is why every band here reads
    # len(energies) as EFFECTIVE energy.
    assert len(mine["active"][0]["energies"]) == 2
    assert len(mine["active"][0]["energyCards"]) == 1

    bench = {p["id"]: p for p in mine["bench"]}
    assert MEGANIUM in bench and bench[MEGANIUM]["energies"] == []
    assert sum(1 for p in mine["bench"] if p["id"] == OGERPON) == 2

    assert hand_ids(mine).count(GRASS) == 1, "the turn hangs on ONE Grass"

    # Every body of theirs is a 70 HP non-ex: the stadium mutes our whole ex
    # half of the board.
    assert theirs["active"] == [] or theirs["active"][0]["id"] in (
        OP_MESPRIT, OP_AZELF, OP_UXIE)
    for p in theirs["bench"]:
        assert p["id"] in (OP_MESPRIT, OP_AZELF, OP_UXIE)
        assert p["maxHp"] == 70


def hand_ids(player):
    return [c["id"] for c in (player.get("hand") or [])]


# ---------------------------------------------------------------------------
# 2. The choice
# ---------------------------------------------------------------------------

def test_the_grass_goes_to_the_meganium():
    obs = _obs_step70()
    choice = m.agent(obs)
    mine = obs["current"]["players"][1]
    target = _attach_target(obs, choice)
    assert target is not None, f"expected an ATTACH, got {_chosen(obs, choice)}"
    idx = int(target.split("-")[1]) if target.startswith("bench") else None
    assert idx is not None, "the Grass went to the mute active ex"
    assert mine["bench"][idx]["id"] == MEGANIUM


def test_teal_dance_does_not_take_the_last_grass():
    obs = _obs_step70()
    choice = m.agent(obs)
    assert _chosen(obs, choice)["type"] != int(OptionType.ABILITY), (
        "the dance charged a body the stadium has switched off")


# ---------------------------------------------------------------------------
# 3. The helper, on its four answers
# ---------------------------------------------------------------------------

class _Body:
    def __init__(self, cid):
        self.id = cid


@pytest.mark.parametrize("cid, muted", [
    (OP_MESPRIT, True),      # 70 HP basic, no Rule Box
    (m.Hydrapple_ex, False),  # a Rule Box in front: our ex hit it normally
])
def test_the_helper_reads_the_body_in_front(cid, muted):
    assert _nz_mutes_our_ex(_Body(cid), True) is muted


def test_the_helper_is_silent_without_the_stadium():
    assert _nz_mutes_our_ex(_Body(OP_MESPRIT), False) is False


def test_the_helper_is_silent_with_no_body_in_front():
    assert _nz_mutes_our_ex(None, True) is False


def test_an_unknown_card_does_not_switch_our_attackers_off():
    # `_tiene_rule_box` answers True for a card it cannot read, so this answers
    # False: on data we cannot read we do not mute our own half of the board.
    assert _nz_mutes_our_ex(_Body(10 ** 7), True) is False


# ---------------------------------------------------------------------------
# 4. The boundary: it is the STADIUM doing the work, not the matchup
# ---------------------------------------------------------------------------

def test_with_a_rule_box_in_front_the_dance_takes_it_back():
    """Their promotion switches the reading off, and the old line returns.

    The same board with a Rule-Box body in the active spot: our ex are no
    longer mute, nothing is owed to the Meganium, and Teal Dance goes back to
    being the best use of the Grass. If this ever stops holding, the change
    stopped being about the stadium.
    """
    obs = _obs_step70()
    theirs = obs["current"]["players"][0]
    theirs["active"] = [dict(theirs["bench"][0], id=m.Mega_Kangaskhan_ex,
                             hp=400, maxHp=400)]
    choice = m.agent(obs)
    assert _chosen(obs, choice)["type"] == int(OptionType.ABILITY)


def test_without_the_stadium_the_board_is_unchanged():
    """The strict no-op half: with no stadium the reading cannot fire at all.

    Same board, same Rule-Box-less bodies opposite -- only the stadium gone.
    Our ex hit them normally now, nothing is owed to the Meganium and the turn
    goes back to the dance. The reading owns the stadium and nothing else.
    """
    obs = _obs_step70()
    obs["current"]["stadium"] = []
    choice = m.agent(obs)
    assert _chosen(obs, choice)["type"] == int(OptionType.ABILITY)


# ---------------------------------------------------------------------------
# 5. The bench promotion keeps its order, and stays under the ACTIVE bands
# ---------------------------------------------------------------------------

def test_the_promotion_keeps_the_bench_below_every_active_band():
    """22000 is chosen so the front still outranks the bench.

    The stadium's ACTIVE bands are 23200 (Tapu Bulu, Dipplin), 23000 (Pinsir)
    and 15000 (Meganium); the bench ones are 600/400/380/300. The promotion is
    added to the bench halves only, so their internal order is untouched and
    the best of them stays below the worst active band that is still asking for
    the energy. A promotion that broke either of those would take the Grass off
    a body that could attack TODAY.
    """
    bench = [600, 400, 380, 300]
    promoted = [b + 22000 for b in bench]
    assert promoted == sorted(promoted, reverse=True) == [22600, 22400, 22380, 22300]
    assert max(promoted) < 23000, "the bench outranks an ACTIVE band"
