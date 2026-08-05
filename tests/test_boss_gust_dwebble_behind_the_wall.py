"""With the Crustle wall in front, the bench Dwebble IS gusted.

Scenario (user, episode 88620891 step 78 vs Crustle, LOST): Hydrapple ex
ACTIVE with 12 units of Grass on the field -- Syrup Storm hits for 390 -- but the
rival active is a Crustle, whose *Mysterious Rock Inn* ability cancels ALL the
damage from our Pokemon ex. Attacking head-on does 0. On the rival bench wait
TWO non-ex Dwebble (70 and 90 HP), and in hand we have Boss's Orders. The right
play is a three-step one:

    Boss's Orders -> gust a Dwebble -> Syrup Storm -> KO (1 prize)

The agent played Xerosic's Machinations and closed the turn with no prizes, with
Boss's trapped in hand (only one Supporter fits per turn).

Cause: TWO coupled rules from log 86339758, which assume that vs Crustle a
Dwebble never deserves the gust (it is wall fodder: it evolves into Crustle):

1. `_ADJUST_GUST_NUISANCE / forbid_dwebble_vs_crustle` -> SCORE_FORBID on the
   Dwebble as the gust TARGET.
2. In `evaluate_supporters`, the cut-off `_cru_has_nondwebble_bench` set
   `values[Boss_Orders] = 0` if the rival bench held only Dwebble -- so as not to
   play the card chasing a KO that (1) then vetoed.

Cut-off (2) silently overrode `crustle_gust_worth_it`, the branch that ALREADY
detected exactly this case and raised Boss's to `BOSS_PRIORITY_CRUSTLE_GUST` (990).

The exemption is deck-agnostic at its core: `wall_blocks_active` measures that
our ACTIVE does 0 effective damage to the rival active via `_our_effective_damage`
(it holds for Mysterious Rock Inn, Cornerstone Stance, Sylveon...), not a list of
ids. Only the veto's exemption is still bounded to `op_is_crustle_deck`, which is
where the veto lives.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import G, Scenario, pk

HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
MEGANIUM = m.Meganium
MEOWTH = m.Meowth_ex
BOSS = m.Boss_Orders
XEROSIC = m.Xerosic_Machinations
ULTRA_BALL = m.Ultra_Ball

CRUSTLE = m.Crustle_Grass      # 345: Mysterious Rock Inn (cancels ex damage)
DWEBBLE = m.Dwebble_Grass      # 344: 70 HP, non-ex -> 1 prize
KANGASKHAN = m.Mega_Kangaskhan_ex


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
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _scenario(op_active=None, op_bench=None, hand=(BOSS, XEROSIC, ULTRA_BALL)):
    """The board of step 78: an active Hydrapple ex with Grass to spare
    (Syrup Storm 390) and a rival bench with only Dwebble."""
    op_active = op_active if op_active is not None else pk(CRUSTLE)
    op_bench = op_bench if op_bench is not None else [pk(DWEBBLE), pk(DWEBBLE)]
    return (Scenario(turn=8, step=78, energy_played=True)
            .my_active(pk(HYDRAPPLE, hp=210, energies=[G, G], fisicas=1))
            .my_bench(pk(MEGANIUM),
                      pk(OGERPON, energies=[G] * 4, fisicas=2),
                      pk(OGERPON, energies=[G] * 6, fisicas=3),
                      pk(MEOWTH))
            .my_hand(*hand)
            .op_active(op_active)
            .op_bench(*op_bench)
            .op_zonas(hand=8, deck=30, prizes=6))


def _play(obs, choice, hand):
    o = obs["select"]["option"][choice[0]]
    if o["type"] == int(m.OptionType.PLAY):
        return ("PLAY", hand[o["index"]])
    if o["type"] == int(m.OptionType.ATTACK):
        return ("ATTACK", None)
    if o["type"] == int(m.OptionType.END):
        return ("END", None)
    return (o["type"], None)


# ---------------------------------------------------------------------------
# The record's failure: play Boss's and gust the Dwebble
# ---------------------------------------------------------------------------

def test_with_the_wall_in_front_boss_orders_is_played():
    """The exact case of step 78: Boss's was VETOED (value 0) and Xerosic
    won. With the active cancelled by the wall, the gust is the only prize."""
    hand = [BOSS, XEROSIC, ULTRA_BALL]
    obs = _scenario(hand=hand).menu_hand().build()
    assert _play(obs, m.agent(obs), hand) == ("PLAY", BOSS)


def test_the_gust_target_is_the_dwebble_not_the_second_wall():
    """The other half of the chain: without this we would play Boss's and then the
    selector would veto the Dwebble (the failure that motivated log 86339758).

    The bench carries a knockout-able Dwebble AND a second Crustle, which we also do
    not damage: it is the pair that DISCRIMINATES. With the record's two Dwebble both
    fell into SCORE_FORBID and the argmax picked index 0 anyway, so
    the assertion passed even without the correction."""
    obs = (_scenario(op_bench=[pk(DWEBBLE), pk(CRUSTLE)])
           .menu_gust().build())
    idx = obs["select"]["option"][m.agent(obs)[0]]["index"]
    assert obs["current"]["players"][1]["bench"][idx]["id"] == DWEBBLE


def test_the_gusted_dwebble_dies_to_syrup_storm():
    """The gust is only worth it if the KO is real: 30 + 30x12 = 390 on 70 HP."""
    obs = _scenario().menu_gust().build()
    st = m.to_observation_class(obs).current
    mio, riv = st.players[0], st.players[1]
    m.meganium_in_play = True
    target = riv.bench[0]
    dmg = m.calc_syrup_storm_damage(mio, True)
    assert m._our_effective_damage(mio.active[0], target, dmg, True, False) \
        >= (target.hp or 0)


# ---------------------------------------------------------------------------
# Boundaries: the exemption does NOT disarm the original veto of log 86339758
# ---------------------------------------------------------------------------

def test_without_the_wall_the_dwebble_is_still_a_vetoed_target():
    """Boundary: if the rival active does NOT cancel us (here a Mega Kangaskhan ex we
    DO hit), the Dwebble goes back to being fodder and is not gusted."""
    obs = (_scenario(op_active=pk(KANGASKHAN, hp=300),
                      op_bench=[pk(DWEBBLE), pk(CRUSTLE)])
           .menu_gust().build())
    idx = obs["select"]["option"][m.agent(obs)[0]]["index"]
    assert obs["current"]["players"][1]["bench"][idx]["id"] != DWEBBLE


def test_with_the_wall_but_no_ko_the_dwebble_is_still_vetoed():
    """Boundary: the exemption requires a REAL KO. With our own active lacking enough
    energy to attack, the Dwebble is not a prize and the veto holds."""
    obs = (Scenario(turn=8, step=78, energy_played=True)
           .my_active(pk(HYDRAPPLE, hp=210))          # 0 energies: it does not attack
           .my_bench(pk(MEOWTH))
           .my_hand(BOSS, ULTRA_BALL)
           .op_active(pk(CRUSTLE))
           .op_bench(pk(DWEBBLE), pk(CRUSTLE))
           .op_zonas(hand=8, deck=30, prizes=6)
           .menu_gust().build())
    idx = obs["select"]["option"][m.agent(obs)[0]]["index"]
    assert obs["current"]["players"][1]["bench"][idx]["id"] != DWEBBLE
