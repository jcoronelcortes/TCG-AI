"""The doomed ex's retreat only denies prizes if the ex SURVIVES down there.

It is the other half of the strategy of registro_004 t4 vs Marnie's Grimmsnarl
(see `test_probabilistic_finisher_fishing.py`): if the fishing fails and the turn
closes without an attack, the user's plan is to RETREAT the doomed ex to put
in front a 1-prize body. `_doomed_ex_sac_pivot` already does that (score
6530)... but its arithmetic took for granted that the ex is safe on the bench.

Against an attacker that ALSO hits the bench it is not. Shadow Bullet of
Marnie's Grimmsnarl ex does 180 to the active AND 30 to a benched one, and our Teal
Mask Ogerpon ex was at 30 HP:

    staying    -> they knock out the active ex                   = 2 prizes
    retreating -> they knock out the promoted body (1 prize) AND
                  the snipe finishes off the hidden ex (2 prizes) = 3 prizes

Retreating never wins in that case: at best it ties (when the snipe was going to
kill another bench body of the same price anyway). The guard switches the pivot off.

It is measured with the ATTACKER in front of us (`OP_BENCH_SNIPE_DAMAGE` of the rival
active), not with the table flag `_op_bench_snipe_dmg`: that one falls to a default
30 as soon as there is any drip threat in play, and switching the pivot off
because of a sniper sitting on the rival BENCH cost -3.1 points vs crustle/Kangaskhan
in self-play (n=1500). With the narrow version the deltas go back to noise.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import Escenario, G, pk

GRIMMSNARL = 648      # Shadow Bullet: 180 to the active + 30 to a benched one
MORGREM = 647         # Corkscrew Punch: 60, no snipe
IMPIDIMP = 646
SNORUNT = 860
DARK = 7


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.meganium_in_play = False
    m.forest_in_play = False
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m._field_at_turn_start = {}
    yield
    m._init_cards_tracking()


def _turn_close(opponent_active="grimmsnarl", hp_ogerpon=30):
    """The end of a turn after a failed fishing attempt: the Supporter spent, no energy and
    the doomed Ogerpon ex in front. The menu only offers RETREAT and END,
    like the real step 55."""
    grimm = pk(GRIMMSNARL, hp=320, max_hp=320, energies=[DARK, DARK],
               pre_evo=[IMPIDIMP])
    morgrem = pk(MORGREM, hp=100, max_hp=100, energies=[DARK, DARK],
                 pre_evo=[IMPIDIMP])
    if opponent_active == "grimmsnarl":
        opponent_act, opponent_bench = grimm, morgrem
    else:
        opponent_act, opponent_bench = morgrem, grimm

    esc = (Escenario(turn=4, step=55, tac=8, first_player=1,
                     supporter_played=True)
           .my_active(pk(m.Teal_Mask_Ogerpon_ex, hp=hp_ogerpon,
                         energies=[G], fisicas=1))
           .my_bench(pk(m.Meowth_ex),
                     pk(m.Fezandipiti_ex, hp=180, energies=[G], fisicas=1),
                     pk(m.Applin),
                     pk(m.Teal_Mask_Ogerpon_ex),
                     pk(m.Bayleef, pre_evo=[m.Chikorita]))
           .my_hand(m.Ultra_Ball, m.Bug_Catching_Set, m.Night_Stretcher)
           .op_active(opponent_act)
           .op_bench(opponent_bench, pk(SNORUNT, hp=70, max_hp=70),
                     pk(IMPIDIMP, hp=70, max_hp=70, energies=[DARK, DARK]))
           .op_zonas(hand=5, deck=32, prizes=6))
    esc.deck(*sorted(esc._pool.elements())[:34]).rest_to_discard()
    obs = esc.menu_hand(with_retreat=True).build()
    obs["select"]["option"] = [
        o for o in obs["select"]["option"]
        if o["type"] in (int(m.OptionType.RETREAT), int(m.OptionType.END))]
    return obs


def _elige(obs):
    return obs["select"]["option"][m.agent(obs)[0]]["type"]


def test_the_ex_at_30_hp_cannot_hide_from_shadow_bullet():
    """With the sniper IN FRONT, retreating gives away the third prize: we hold."""
    obs = _turn_close(opponent_active="grimmsnarl", hp_ogerpon=30)
    assert m.OP_BENCH_SNIPE_DAMAGE[GRIMMSNARL] >= 30, "el snipe alcanza los 30 PV"
    assert _elige(obs) == int(m.OptionType.END)


def test_with_life_above_the_snipe_the_retreat_stays_alive():
    """Control: the SAME board with the ex at 60 HP -- the 30 snipe no longer
    kills it on the bench -- retreats again and sacrifices the 1-prize body."""
    obs = _turn_close(opponent_active="grimmsnarl", hp_ogerpon=60)
    assert _elige(obs) == int(m.OptionType.RETREAT)


def test_with_a_non_sniping_attacker_in_front_it_retreats():
    """Control: Morgrem (60 damage, no snipe) also dooms the 30 HP ex,
    but does not reach the bench -> hiding it DOES deny the prize."""
    obs = _turn_close(opponent_active="morgrem", hp_ogerpon=30)
    assert MORGREM not in m.OP_BENCH_SNIPE_DAMAGE
    assert _elige(obs) == int(m.OptionType.RETREAT)
