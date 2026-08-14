"""The double wave does not take a prize, it takes the GAME.

Scenario (user, `records/registro_020_pasos_145_hasta_153.json`, episode
92849968, turn 20 vs *Festival Lead* -- WON, and won several turns later than
it had to be):

    US (2 prizes)                          RIVAL (3 prizes)
    active  Teal Mask Ogerpon ex           active  Applin    40/40, no energy
            150/210, 6 {G}                 bench   Thwackey 100/100
    bench   Fezandipiti ex 170                     Thwackey 100/100
            Meganium       160
            Teal Mask Ogerpon ex 210, 4 {G}
            Teal Mask Ogerpon ex 210, 4 {G}
            **Applin 40**
    hand    Hydrapple ex, **Dipplin**, 2 {G}
    stadium **Festival Grounds** (theirs)

THE TURN THAT WAS AVAILABLE, and it was the whole game. Evolve the benched
Applin into Dipplin (the agent did do this), put a Grass on it, and RETREAT the
Ogerpon ex into it. A retreat SWAPS bodies, so the bench is still five and *Do
the Wave* is 20 x 5 = **100**: their 40 HP Applin dies, they promote a Thwackey,
and because Festival Grounds is on the field the SAME wave lands again --
100 >= 100, the Thwackey dies too. Two prizes, and we were on two. Game over on
turn 20.

WHAT THE AGENT PLAYED. It evolved the Applin, spent both Grass on Teal Dance
into two BENCHED Ogerpon ex, played its Supporter and finished the 40 HP Applin
from the front with Myriad Leaf Shower for 210. **One prize** out of a turn
that held two, and the game went on.

WHY NOTHING SAW IT -- three readings, none of them missing, none of them
allowed to reach this board:

  1. `_festival_sac_pivot` is this exact swap and it is DEFENSIVE: it fires only
     when the ex in front is already doomed (`active_ko_likely`). Here the ex
     sat at 150/210 facing a 40 HP Applin with nothing at all to fear, so the
     one rule written for this board stood aside.
  2. `festival_lead_pays_us_now` only holds the counter-stadium back. It knows
     the wave is lethal and its whole job is to not throw the stadium away.
  3. `prizes_today` DID count the second wave -- it read **2** on this very
     board, correctly. But `prizes_today` labels a turn, it does not execute
     one. The flag that executes is `_win_ko_active_via_promote`, fed by
     `_promote_ko_active_prizes`, which answered `prize_count_op(op_active)`:
     ONE. The plan said RACE, and a RACE turn cashes the prize it can see.

THE FIX is one sentence in two places, because the stadium changes the prize
count of a route and not the damage of an attack:

  * `_festival_promote_wave_prizes` -- the PROMOTE route cashes the body it kills
    AND the body that replaces it. It is asked BEFORE the "the active already
    knocks it out" guard, whose premise (both routes cash the same prize, and the
    one in front is free) is true of every route we own except this one.
  * `_festival_active_wave_prizes` -- the same reading from the Active spot, for
    the board where the Dipplin is already in front. It carries its own damage
    because the inline copy behind `_active_already_kos` does not know Dipplin
    at all.

AND `_festival_second_wave_prizes` NOW READS THE CHEAPEST CORPSE. It already
refused the second prize when one body survives; it was taking the MAXIMUM among
the bodies that die, and which of them comes up is the opponent's choice, made
against us. On a bench holding a Thwackey and an ex that both die, the wave is
worth one prize, not two -- and now that a WIN route reads this number, the
difference is the difference between a lethal turn and a turn that says so.

INERT WITHOUT THE STADIUM, by construction: every path added here is behind
`_festival_double_wave`, which is false unless Festival Grounds is on the field,
and we do not carry it in `deck.csv`. `test_without_the_stadium_the_record_line_is_unchanged`
pins that.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m  # noqa: E402
import golden_corpus as gc  # noqa: E402
from state_builder import Scenario, pk, G  # noqa: E402
from ptcg.turn.game_plan import MODE_WIN_NOW, ROUTE_ACTIVE, ROUTE_PROMOTE  # noqa: E402

THWACKEY = 90            # 100 HP: exactly what a 5-body wave kills
FEZANDIPITI = m.Fezandipiti_ex
MEGANIUM = m.Meganium
OGERPON = m.Teal_Mask_Ogerpon_ex
DO_THE_WAVE = m.DO_THE_WAVE_ATTACK_ID
MYRIAD = 120


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _record_board(with_stadium=True, op_bench=None):
    """registro_020 turn 20 at turnActionCount 2: the benched Applin is already
    a Dipplin (the one thing the record got right) and the retreat is still
    available."""
    gc.reset_agent(m)
    sc = (Scenario(turn=20, step=146, tac=2, own_prizes=2)
          .my_active(pk(OGERPON, hp=150, energies=[G] * 6, fisicas=3))
          .my_bench(pk(FEZANDIPITI, hp=170, max_hp=170),
                    pk(MEGANIUM, hp=160, max_hp=160),
                    pk(OGERPON, energies=[G] * 4, fisicas=2),
                    pk(OGERPON, energies=[G] * 4, fisicas=2),
                    pk(m.Dipplin))
          .my_hand(m.Basic_Grass_Energy, m.Basic_Grass_Energy)
          .op_active(pk(m.Applin, hp=40, max_hp=40))
          .op_bench(*(op_bench or [pk(THWACKEY, hp=100, max_hp=100),
                                   pk(THWACKEY, hp=100, max_hp=100)]))
          .op_zones(hand=3, deck=10, prizes=3))
    if with_stadium:
        sc = sc.stadium(m.Festival_Grounds, of_the_opponent=True)
    return sc.menu_hand(with_retreat=True, with_attachment=True,
                        with_attack=True).build()


def _decide(obs):
    choice = list(m.agent(obs))
    return obs["select"]["option"][choice[0]]


def _sides(obs):
    """(ours, theirs) as the agent's own state objects."""
    cur = obs["current"]
    players = m.to_observation_class(obs).current.players
    return players[cur["yourIndex"]], players[1 - cur["yourIndex"]]


def _promote_prizes(obs):
    """`_promote_ko_active_prizes` asked exactly the way `agent()` asks it on
    this board: the retreat is payable and the turn's Grass is unspent."""
    mine, theirs = _sides(obs)
    return m._promote_ko_active_prizes(
        mine, theirs.active[0], True, False, True,
        m.count_total_grass_energy(mine), len(mine.bench),
        m.AGENT_STATE.meganium_in_play, False, op_state=theirs)


# ---------------------------------------------------------------------------
# 1. The reading: the promote route cashes two bodies, not one
# ---------------------------------------------------------------------------

def test_the_promote_route_counts_the_body_that_replaces_the_one_it_kills():
    obs = _record_board()
    _decide(obs)                       # builds AGENT_STATE off this board
    assert _promote_prizes(obs) == 2


def test_the_wave_that_leaves_a_survivor_is_worth_one_prize():
    """The claim that is NOT made: a 4-body wave is 80, the Thwackey lives, and
    the second prize is one the opponent can decline."""
    obs = _record_board()
    _decide(obs)
    _, theirs = _sides(obs)
    koed = theirs.active[0]
    assert m._festival_second_wave_prizes(theirs, 100, koed) == 1
    assert m._festival_second_wave_prizes(theirs, 80, koed) == 0


def test_the_second_wave_pays_the_cheapest_corpse_they_can_promote():
    """Both bodies die to the wave, so WHICH one comes up is still their
    choice: an ex behind a Thwackey does not make the wave worth two."""
    obs = _record_board(op_bench=[pk(THWACKEY, hp=100, max_hp=100),
                                  pk(OGERPON, hp=100, max_hp=210,
                                     energies=[G])])
    _decide(obs)
    _, theirs = _sides(obs)
    assert m._festival_second_wave_prizes(theirs, 100, theirs.active[0]) == 1


# ---------------------------------------------------------------------------
# 2. The turn: WIN_NOW, and the retreat is what it spends the turn on
# ---------------------------------------------------------------------------

def test_the_turn_reads_win_now_by_promoting():
    obs = _record_board()
    _decide(obs)
    plan = m.AGENT_STATE.turn_plan
    assert plan.mode == MODE_WIN_NOW and plan.win_route == ROUTE_PROMOTE, plan
    assert plan.prizes_today >= plan.my_prize


def test_the_record_step_retreats_instead_of_cashing_one_prize():
    """The step the game was long at: not Teal Dance, not Myriad -- the swap."""
    opt = _decide(_record_board())
    assert opt["type"] == m.OptionType.RETREAT, opt


def _promotion_menu(with_stadium=True):
    """The prompt the engine emits right AFTER the retreat fee is paid: who
    comes up. The fee is already gone from the active, which is why the
    Ogerpon that pays it is not on this board carrying what it spent."""
    gc.reset_agent(m)
    sc = (Scenario(turn=20, step=146, tac=3, own_prizes=2)
          .my_active(pk(OGERPON, hp=150, energies=[G] * 6, fisicas=3))
          .my_bench(pk(FEZANDIPITI, hp=170, max_hp=170),
                    pk(MEGANIUM, hp=160, max_hp=160),
                    pk(OGERPON, energies=[G] * 4, fisicas=2),
                    pk(OGERPON, energies=[G] * 4, fisicas=2),
                    pk(m.Dipplin))
          .my_hand(m.Basic_Grass_Energy, m.Basic_Grass_Energy)
          .op_active(pk(m.Applin, hp=40, max_hp=40))
          .op_bench(pk(THWACKEY, hp=100, max_hp=100),
                    pk(THWACKEY, hp=100, max_hp=100))
          .op_zones(hand=3, deck=10, prizes=3))
    if with_stadium:
        sc = sc.stadium(m.Festival_Grounds, of_the_opponent=True)
    return sc.promote_after_retreat().build()


def test_the_retreat_that_is_paid_is_the_retreat_that_is_cashed():
    """The hole the rules-level oracle found in the first version of this fix.

    Upstream said ROUTE_PROMOTE and the retreat got chosen -- and then this menu
    brought up an Ogerpon ex, because its own "promote the finisher that wins"
    rung asks the same one-prize question. The fee was paid and never cashed,
    which is strictly worse than the line the record played."""
    obs = _promotion_menu()
    opt = _decide(obs)
    mine, _ = _sides(obs)
    assert mine.bench[opt["index"]].id == m.Dipplin, opt


def test_without_the_stadium_the_promotion_is_the_one_it_always_was():
    obs = _promotion_menu(with_stadium=False)
    opt = _decide(obs)
    mine, _ = _sides(obs)
    assert mine.bench[opt["index"]].id != m.Dipplin, opt


def test_the_dipplin_already_in_front_knows_it_has_won():
    """The same law from the Active spot, where `_active_already_kos` is blind
    because its inline damage copy does not know Dipplin."""
    gc.reset_agent(m)
    obs = (Scenario(turn=20, step=146, tac=4, own_prizes=2)
           .my_active(pk(m.Dipplin, energies=[G], fisicas=1))
           .my_bench(pk(FEZANDIPITI, hp=170, max_hp=170),
                     pk(MEGANIUM, hp=160, max_hp=160),
                     pk(OGERPON, energies=[G] * 4, fisicas=2),
                     pk(OGERPON, energies=[G] * 4, fisicas=2),
                     pk(OGERPON, hp=150, energies=[G] * 4, fisicas=2))
           .op_active(pk(m.Applin, hp=40, max_hp=40))
           .op_bench(pk(THWACKEY, hp=100, max_hp=100),
                     pk(THWACKEY, hp=100, max_hp=100))
           .op_zones(hand=3, deck=10, prizes=3)
           .stadium(m.Festival_Grounds, of_the_opponent=True)
           .menu_hand(with_attack=True).build())
    opt = _decide(obs)
    plan = m.AGENT_STATE.turn_plan
    assert plan.mode == MODE_WIN_NOW and plan.win_route == ROUTE_ACTIVE, plan
    assert opt.get("attackId") == DO_THE_WAVE, opt


# ---------------------------------------------------------------------------
# 3. Dated to the stadium: with Festival Grounds gone nothing here exists
# ---------------------------------------------------------------------------

def test_without_the_stadium_the_record_line_is_unchanged():
    """No stadium, no second wave, no route: the promotion is a chip that gives
    up a prize the Myriad already cashes, and the agent goes back to the line
    the record played."""
    obs = _record_board(with_stadium=False)
    opt = _decide(obs)
    plan = m.AGENT_STATE.turn_plan
    assert plan.mode != MODE_WIN_NOW and not plan.win_route, plan
    assert opt["type"] != m.OptionType.RETREAT, opt


def test_without_the_stadium_the_promote_route_reads_zero():
    obs = _record_board(with_stadium=False)
    _decide(obs)
    assert _promote_prizes(obs) == 0
