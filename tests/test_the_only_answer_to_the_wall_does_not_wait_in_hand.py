"""vs the immune wall, Tapu Bulu comes down and is charged TODAY.

THE RULE (user, ago 2026). Against Crustle our ex do ZERO -- Crustle is in
`EX_IMMUNE_IDS` -- so Tapu Bulu's Wood Hammer is the only thing on our side of
the table that removes the body in front. The project already accepted the
consequence for the charge ("the active Tapu Bulu ALWAYS has the first charging
priority, from the first turn",
`test_the_active_tapu_bulu_is_charged_against_crustle.py`). This file is the
same sentence applied to the two halves that were still reading a different
question.

FIRST HALF -- THE BODY (`ptcg/turn/options/play.py`). Every branch of the Tapu
Bulu play scorer exempts the wall matchups by hand, and then a clamp written
with no matchup in it at all undid all of them: while ANY item was left in hand,
"Tapu Bulu waits for the items" dropped it from 22000+ to
`TAPU_WAIT_FOR_ITEMS_SCORE` (8900), under everything else on the menu.

That is an ordering rule that was costing the BODY, not the order. On the turn
after a knockout `ko_last_turn` opens Fezandipiti ex's own branch at 22000
(22500 with a hand of three), so the clamp handed the bench slot to a TWO-PRIZE
body that cannot damage the wall either:

    vs Crustle, ko_last_turn, hand = Tapu + Fez + Grass       -> Tapu Bulu
    vs Crustle, ko_last_turn, hand = Tapu + Fez + UB + Grass  -> Fezandipiti ex

SECOND HALF -- THE CHARGE (`ptcg/turn/energy.py`). The "Crustle band" (+11000)
that the active Tapu earns was written `active` because the board it was
measured on had Tapu in front. The reason it is paid -- every turn its climb to
four energies is deferred is a turn the wall lives -- says nothing about being
the active, and a benched Tapu was losing the turn's energy to exactly the body
that paragraph names:

    benched Tapu at 0, bench = Tapu + Applin   -> the APPLIN took it (28500)
    benched Tapu at 0, bench = Tapu + Dipplin  -> the DIPPLIN took it

With a Chikorita/Bayleef/Meganium anywhere on the bench the old clause paid the
band anyway (`_ctm_chikorita_bench`), which is why the hole only shows on the
Applin-line boards -- the same accident that hid it for the active Tapu.

Both halves matter together, and that is the shape of the turn the rule buys:
Tapu comes down, the manual attachment goes to it, Hydrapple ex's Ripening
Charge -- whose target is decided by this same `energy_score` -- goes to it as
well, and under Meganium's Wild Growth those two Grass are the four effective
that Wood Hammer needs. TODAY, instead of a Grass held in hand for a Tapu that
is still in there with it.

CORPUS: eleven flips on the frozen bundle, every one of them a crustle_wall
game and every one the same sentence -- Tapu Bulu played or charged where a
Chikorita, an Applin, an Ogerpon ex or (registro_022 turn 10) a Fezandipiti ex
used to go.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import Scenario, pk, G

TAPU = m.Tapu_Bulu
FEZ = m.Fezandipiti_ex
APPLIN = m.Applin
DIPPLIN = m.Dipplin
MEGANIUM = m.Meganium
OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRAPPLE = m.Hydrapple_ex

CRUSTLE = m.Crustle_Grass
DWEBBLE = m.Dwebble_Grass
SYLVEON = m.Sylveon
CORNERSTONE = m.Cornerstone_Mask_Ogerpon_ex
IRON_THORNS = m.Iron_Thorns_ex
ABRA = m.Abra                     # the ordinary matchup, our control


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m._init_cards_tracking()


def _board(hand, bench, op_active, ko_last_turn=False, active=OGERPON):
    obs = (Scenario(turn=6, step=60, first_player=1,
                    energy_played=False, supporter_played=True)
           .my_active(pk(active))
           .my_bench(*bench)
           .my_hand(*hand)
           .op_active(pk(op_active, energies=[G]))
           .op_zones(hand=4, deck=30, prizes=4)
           .menu_hand(with_attachment=(m.Basic_Grass_Energy in hand)).build())
    if ko_last_turn:
        # The turn after a knockout of ours: what switches Fezandipiti ex's
        # branch on (Flip the Script is only alive there).
        m.AGENT_STATE.ko_last_turn = True
        m.AGENT_STATE._ko_detected_this_turn = True
        m.AGENT_STATE._prev_op_prize = 6
    return obs


def _played(obs):
    """The id of the card the agent plays from hand, or None."""
    opt = obs["select"]["option"][m.agent(obs)[0]]
    if opt["type"] != int(m.OptionType.PLAY):
        return None
    return obs["current"]["players"][0]["hand"][opt["index"]]["id"]


def _charged(obs, bench_ids):
    """Who gets the turn's attachment: "ACTIVE", a benched id, or None."""
    opt = obs["select"]["option"][m.agent(obs)[0]]
    if opt["type"] != int(m.OptionType.ATTACH):
        return None
    if opt["inPlayArea"] == int(m.AreaType.ACTIVE):
        return "ACTIVE"
    return bench_ids[opt["inPlayIndex"]]


# ---------------------------------------------------------------------------
# First half: the body comes down
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("item", [m.Ultra_Ball, m.Night_Stretcher])
def test_the_wall_attacker_is_not_deferred_behind_an_item(item):
    """The clamp is an ORDER rule and it was costing the body: with the item in
    hand Tapu fell to 8900 and Fezandipiti ex (22000) took the bench slot."""
    obs = _board([TAPU, FEZ, item, m.Basic_Grass_Energy], [pk(MEGANIUM)],
                 CRUSTLE, ko_last_turn=True)
    assert _played(obs) == TAPU


@pytest.mark.parametrize("op_active", [CRUSTLE, DWEBBLE, SYLVEON,
                                       CORNERSTONE, IRON_THORNS])
def test_it_is_the_whole_wall_family_and_not_only_crustle(op_active):
    """`_op_is_crustle_like` is the condition the branches above already use:
    an opponent that cancels our ability engine or blanks our ex damage. The
    Dwebble counts -- the point is to have Tapu ready BEFORE the wall lands."""
    obs = _board([TAPU, FEZ, m.Ultra_Ball, m.Basic_Grass_Energy], [pk(MEGANIUM)],
                 op_active, ko_last_turn=True)
    assert _played(obs) == TAPU


def test_without_an_item_in_hand_nothing_had_to_change():
    """The clamp was asleep on this board and Tapu already won it: the fix does
    not move the boards that were right."""
    obs = _board([TAPU, FEZ, m.Basic_Grass_Energy], [pk(MEGANIUM)],
                 CRUSTLE, ko_last_turn=True)
    assert _played(obs) == TAPU


# ---------------------------------------------------------------------------
# Second half: the energy goes to it the same turn
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("companion", [APPLIN, DIPPLIN, HYDRAPPLE, MEGANIUM])
def test_the_benched_tapu_takes_the_turns_energy(companion):
    """A benched Tapu Bulu below four effective is the same answer to the same
    wall, one retreat away. The Applin line (28500) was taking the energy the
    only body that removes Crustle was waiting for."""
    bench = [pk(TAPU), pk(companion)]
    obs = _board([m.Basic_Grass_Energy], bench, CRUSTLE)
    assert _charged(obs, [TAPU, companion]) == TAPU


@pytest.mark.parametrize("op_active", [CRUSTLE, DWEBBLE])
def test_the_charge_reads_the_line_and_not_the_wall_itself(op_active):
    """`op_is_crustle_deck` switches on for the Dwebble too, and the band is
    owed there for the same reason: charged before the wall lands."""
    bench = [pk(TAPU), pk(APPLIN)]
    obs = _board([m.Basic_Grass_Energy], bench, op_active)
    assert _charged(obs, [TAPU, APPLIN]) == TAPU


# ---------------------------------------------------------------------------
# What it does NOT do
# ---------------------------------------------------------------------------

def test_an_ordinary_matchup_keeps_the_wait_it_had():
    """The exemption is matchup-scoped. With no wall in front, the turn after a
    knockout still opens Fezandipiti ex's branch and it still wins the slot --
    there our ex do damage and Tapu is not the only answer to anything."""
    obs = _board([TAPU, FEZ, m.Ultra_Ball, m.Basic_Grass_Energy], [pk(MEGANIUM)],
                 ABRA, ko_last_turn=True)
    assert _played(obs) == FEZ


def test_a_charged_tapu_does_not_pull_the_band_again():
    """The band is owed while the wall has NO answer on our board. Wood Hammer
    needs four effective and no more: once they are on the body, the surplus
    rules own the question of what the next energy is for."""
    bench = [pk(TAPU, energies=[G] * 4), pk(APPLIN)]
    obs = _board([m.Basic_Grass_Energy], bench, CRUSTLE)
    assert _charged(obs, [TAPU, APPLIN]) != TAPU


def test_a_search_that_outbids_the_body_still_goes_first():
    """Only the CLAMP is lifted, not the ordering itself: an item the turn
    genuinely values above Tapu's own band (a Bug Catching Set digging for the
    bodies) still wins on merit, which is what the wait was for."""
    obs = _board([TAPU, FEZ, m.Bug_Catching_Set, m.Basic_Grass_Energy],
                 [pk(MEGANIUM)], CRUSTLE, ko_last_turn=True)
    assert _played(obs) == m.Bug_Catching_Set
