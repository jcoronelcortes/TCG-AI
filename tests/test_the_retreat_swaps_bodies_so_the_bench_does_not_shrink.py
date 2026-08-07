"""A retreat SWAPS two bodies, so our bench does not lose one.

`_promo_kos_op` and `_promo_damage_to_op` (main.py, next to `_promo_survivors`)
project what a promoted body does to the opposing active. The number that scales
Dipplin's *Do the Wave* is how many Pokemon our bench holds AFTER the promotion,
and the two menus that promote do not agree on it:

    TO_ACTIVE   the active was knocked out and is gone. The candidate leaves the
                bench and nothing takes its slot   ->  bench_count - 1
    SWITCH      our voluntary retreat SWAPS the two bodies: the candidate leaves
                the bench and the retreating active takes its slot
                                                   ->  bench_count

Both projections subtracted 1 in BOTH menus. On the knockout path the
subtraction is what it is there for (log 88971843 step 117: without it a Dipplin
projected 20x4 = 80, "knocked out" the opposing 80 HP Dipplin, collected the
PROMO_KO_BONUS and skipped the doomed penalty, bringing an 80 HP body up against
a hit of 100). On the retreat path it is the mirror error, and it hides damage
instead of inventing it: the Dipplin of `records/registro_008` step 78 was
projected at 20x4 = 80 when it hits the Crustle for 20x5 = 100.

There it changed nothing -- 80 > 0 was already enough for `_promo_wall_relief`,
which is why it was written down as measured-but-untouched -- but `_promo_kos_op`
is a THRESHOLD with 20000 behind it. Under-counting one body silences a finisher
that is really on the board.

The scenario below is that threshold, taken from the boards where the flip
actually fires in self-play (Thwackey at 100 HP, Dipplin, a full bench):

    US                                        THEM
    active **Chikorita**, retreating          active **Thwackey 100**/100
    bench  **Dipplin 40**/80, 1 energy                (it hits for 50)
           **Tapu Bulu 140**, 0 en.
           Meowth ex 170, 0 en.
           Fezandipiti ex 210, 0 en.
           Applin 40, 0 en.

*Do the Wave* is 20 x our bench. With the subtraction it projects 20x4 = **80**
against 100 HP: no knockout, and the Dipplin -- which the Thwackey kills, 50
against its 40 remaining -- falls to the doomed band and yields to the Tapu Bulu
that endures and does nothing. Without it, 20x5 = **100**: it takes the prize.

MEASUREMENT. Shadow (`utils/shadow.py`, widened to six opposing decks):
**4 flips in 157,507 decisions** (0.0025%), ALL of them in `SelectContext.SWITCH`
-- no collateral anywhere else. All four are the same pattern and the same
direction: a Dipplin whose *Do the Wave* really does reach takes the promotion
from a 2-prize ex.

    festival_lead        Thwackey 100 HP, bench 5   -> ex Ogerpon at 50/210 yields
    cornerstone_cubchoo  Cubchoo   70 HP, bench 4   -> ex Ogerpon (2 prizes) yields
    dragapult            Drakloak  90 HP, bench 5   -> ex Ogerpon with TEN energies yields
    alakazam             Kadabra   80 HP, bench 4   -> ex Ogerpon yields, which is
                                                       also the one-prize rule vs Alakazam

At that frequency the winrate gate cannot arbitrate, so the verdict is the audit.
Golden corpus: 0 flips. Harness validated with a deliberate mutant
(`_promo_bench_after = bench_count + 2`): 3 flips in 21,432 decisions through
this same code path, in contexts 3 and 4 -- shadow is not blind to it.

Related: `test_the_mute_ex_yields_to_the_body_that_hits_the_wall` (the rule this
projection serves, where the miscount was first written down) and
`test_festival_lead_double_attack_promotion` (the knockout path it protects).
"""

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m  # noqa: E402
from state_builder import Scenario, pk  # noqa: E402

THWACKEY = 90            # 100 HP: exactly 20 x a full bench
DIPPLIN = m.Dipplin
TAPU = m.Tapu_Bulu


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    yield
    m._init_cards_tracking()


def _board(menu, bench_size=5, dipplin_hp=40):
    """The promotion menu with `bench_size` bodies, the Dipplin among them.

    The filler bodies carry no energy, so none of them attacks: the only
    question the menu asks is whether the Dipplin reaches the Thwackey.
    """
    filler = [pk(m.Meowth_ex, energies=0),
              pk(m.Fezandipiti_ex, energies=0),
              pk(m.Applin, energies=0)]
    bench = ([pk(DIPPLIN, hp=dipplin_hp, energies=1), pk(TAPU, energies=0)]
             + filler[:bench_size - 2])
    s = (Scenario(turn=8, energy_played=True, supporter_played=True)
         .my_active(pk(m.Chikorita, energies=0))
         .my_bench(*bench)
         .op_active(pk(THWACKEY, energies=1))
         .op_bench(pk(m.Applin, energies=0)))
    # `fee=0`: the swap costs nothing here, so the board carries no trace of a
    # payment that would muddy the rules reading the active's energy.
    return (s.promote_from_bench() if menu == "to_active"
            else s.promote_after_retreat(fee=0)).build()


def _promoted(obs):
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    action = m.agent(copy.deepcopy(obs))
    return mine["bench"][obs["select"]["option"][action[0]]["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. The scenario: without these numbers the test measures nothing
# ---------------------------------------------------------------------------

def test_the_dipplin_is_doomed_and_the_tapu_endures():
    """The doomed band is what the knockout has to override."""
    from cg.api import to_observation_class

    obs = to_observation_class(_board("switch"))
    cur = obs.current
    mine = cur.players[cur.yourIndex]
    wall = cur.players[1 - cur.yourIndex].active[0]
    dipplin = next(b for b in mine.bench if b is not None and b.id == DIPPLIN)
    tapu = next(b for b in mine.bench if b is not None and b.id == TAPU)

    assert m._op_active_attack_damage_to(wall, dipplin) >= dipplin.hp
    assert m._op_active_attack_damage_to(wall, tapu) < tapu.hp
    assert wall.hp == 100


def test_do_the_wave_reaches_only_with_the_whole_bench():
    """20 x 5 = 100 lands; 20 x 4 = 80 does not. The fix is that one body."""
    from cg.api import to_observation_class

    obs = to_observation_class(_board("switch"))
    cur = obs.current
    mine = cur.players[cur.yourIndex]
    wall = cur.players[1 - cur.yourIndex].active[0]
    dipplin = next(b for b in mine.bench if b is not None and b.id == DIPPLIN)
    bench = [b for b in mine.bench if b is not None]

    def wave(bodies):
        return m._attacker_base_damage(
            dipplin.id, wall, len(dipplin.energies) * m._grass_mult(),
            grass_scale=0, teal_self_energy=0, bench_count=bodies)

    assert wave(len(bench)) >= (wall.hp or 0)          # the swap: 100
    assert wave(len(bench) - 1) < (wall.hp or 0)       # the subtraction: 80


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_the_retreat_promotes_the_dipplin_that_finishes():
    assert _promoted(_board("switch")) == DIPPLIN, (
        "on a retreat the active GOES BACK to the bench and takes the slot of "
        "the body coming up: the count does not drop, and over a whole bench "
        "Do the Wave reaches 100 and finishes the 100 HP Thwackey"
    )


# ---------------------------------------------------------------------------
# 3. The limits of the fix
# ---------------------------------------------------------------------------

def test_the_forced_promotion_keeps_the_subtraction():
    """TO_ACTIVE: the active was knocked out, nothing fills the slot.

    The same board, the same bodies -- and here 20x4 = 80 really is the number.
    The Dipplin does not finish, so it stays in the doomed band and the Tapu
    Bulu that endures is promoted, exactly as before the fix.
    """
    assert _promoted(_board("to_active")) == TAPU, (
        "after a knockout nobody goes back to the bench: there the subtraction "
        "is right and the Dipplin does not finish"
    )


@pytest.mark.parametrize("bench_size,wave", [(3, 60), (4, 80)])
def test_a_short_bench_does_not_reach_and_nothing_moves(bench_size, wave):
    """It is the bench count doing the work, not some other band.

    With four bodies or fewer the corrected *Do the Wave* still falls short of
    the 100 HP, and the promotion goes back to the body that endures.
    """
    assert wave < 100
    assert _promoted(_board("switch", bench_size=bench_size)) == TAPU


def test_a_healthy_dipplin_was_already_winning_the_menu():
    """The fix only speaks where the doomed band was burying the finisher.

    With the Dipplin at full HP it survives the Thwackey and is a 1-prize body:
    it took the promotion on those grounds alone, before and after.
    """
    assert _promoted(_board("switch", dipplin_hp=80)) == DIPPLIN
    assert _promoted(_board("to_active", dipplin_hp=80)) == DIPPLIN
