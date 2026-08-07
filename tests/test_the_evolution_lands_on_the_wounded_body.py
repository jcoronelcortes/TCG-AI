"""Two copies of the same Basic: the evolution goes onto the WOUNDED one.

Scenario (user, turn 8 vs Marnie's Grimmsnarl ex -- Shadow Bullet snipes 30 to
one benched Pokemon EVERY turn):

    US                                     RIVAL
    active  Teal Mask Ogerpon ex           active  Grimmsnarl ex 320
    bench   **Applin 40/40**                       (Shadow Bullet: 180 + 30
            **Applin 10/40**                        to one of our benched)
            Teal Mask Ogerpon ex
    hand    Dipplin / Hydrapple ex, Forest of Vitality

The agent evolved the **healthy** Applin and left the one at 10 HP on the bench,
where the automatic snipe cashes it in for free. The right play is the opposite:
evolving does NOT heal -- the damage carries over and only the maximum goes up
(Applin 10/40 -> Dipplin 50/80 -> Hydrapple ex 300/330) -- so the wounded copy is
the one that GAINS from evolving, and the intact copy is the one that can wait.

Cause: `ptcg/turn/options/evolve.py` scores the CARD being played (Hydrapple ex
33000, Meganium 35000, Dipplin 31500...) plus, at most, the SPECIES of the body
(`pokemon.id == Applin` -> +500). Life never entered the score, so both options
came out identical and the argmax fell on whichever the menu listed first.

Fix: `evolution_body_bias` (ptcg/calc/damage.py), a bounded term (<= 260, below
the 500 that separates two deliberate bands) added at the END of the evolve
scoring and reused as the tie-break between Grand Tree plans. It is
deck-agnostic: it reads current life, `_ventana_de_regalo` and prizes, never a
card id.
"""

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from cg.api import OptionType
from tests.state_builder import Scenario, pk, G

APPLIN = m.Applin
DIPPLIN = m.Dipplin
HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
GRIMMSNARL = m.Grimmsnarl_ex
MORGREM = 647          # Grimmsnarl ex's pre-evolution (no snipe of its own)
FOREST = m.Forest_of_Vitality


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
    m.op_is_starmie_deck = False
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._ub_fez_pending = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


# ---------------------------------------------------------------------------
# The board
# ---------------------------------------------------------------------------

# The line the bench is built with, for each evolution in hand.
_LINE = {DIPPLIN: (APPLIN, 40, ()),
         HYDRAPPLE: (DIPPLIN, 80, (APPLIN,))}


def _board(evolution=DIPPLIN, wounded_first=False, wounded_hp=10,
           op_active=GRIMMSNARL):
    """Two copies of the same pre-evolution on the bench, one of them wounded,
    and the evolution in hand.

    `wounded_first` swaps the order of the two copies: the choice has to be the
    same body, otherwise what is being measured is the order of the menu.
    """
    body, full_hp, pre = _LINE[evolution]
    healthy = pk(body, hp=full_hp, pre_evo=pre)
    wounded = pk(body, hp=min(wounded_hp, full_hp), pre_evo=pre)
    pair = ([wounded, healthy] if wounded_first else [healthy, wounded])
    op = (pk(GRIMMSNARL, hp=320, max_hp=320, energies=[G, G], pre_evo=[MORGREM])
          if op_active == GRIMMSNARL
          else pk(MORGREM, hp=110, max_hp=110, energies=[G]))
    return (Scenario(turn=8, step=70, tac=3, own_prizes=6,
                     supporter_played=True, stadium_played=True)
            .my_active(pk(OGERPON, energies=[G, G, G], fisicas=3))
            .my_bench(*pair, pk(OGERPON, energies=[G], fisicas=1))
            .stadium(FOREST)
            .op_active(op)
            .op_bench(pk(MORGREM, hp=110, max_hp=110))
            .op_zones(hand=5, deck=25, prizes=6)
            .my_hand(evolution)
            .deck()
            .rest_to_discard()
            .menu_evolve()
            .build())


def _chosen(obs):
    return obs["select"]["option"][m.agent(copy.deepcopy(obs))[0]]


def _bench_index_of(obs, body_id, hp):
    yo = obs["current"]["yourIndex"]
    return next(k for k, b in enumerate(obs["current"]["players"][yo]["bench"])
                if b and b["id"] == body_id and b["hp"] == hp)


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_board_has_two_applin_at_different_life():
    obs = _board()
    yo = obs["current"]["yourIndex"]
    applin = [b for b in obs["current"]["players"][yo]["bench"]
              if b and b["id"] == APPLIN]
    assert sorted(b["hp"] for b in applin) == [10, 40]
    assert all(b["maxHp"] == 40 for b in applin)

    # Both bodies are legal targets: the menu emits ONE evolve per copy.
    evolves = [o for o in obs["select"]["option"]
               if o["type"] == int(OptionType.EVOLVE)]
    assert len(evolves) == 2

    # And the opponent snipes the bench: the 10 HP copy is a prize they cash in
    # whenever they like.
    assert m.OP_BENCH_SNIPE_DAMAGE[GRIMMSNARL] >= 10


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("wounded_first", [False, True])
@pytest.mark.parametrize("evolution", [DIPPLIN, HYDRAPPLE])
def test_it_evolves_the_wounded_applin(evolution, wounded_first):
    obs = _board(evolution=evolution, wounded_first=wounded_first)
    body = _LINE[evolution][0]
    chosen = _chosen(obs)
    assert chosen["type"] == int(OptionType.EVOLVE), chosen
    assert chosen["inPlayIndex"] == _bench_index_of(obs, body, 10), (
        "evolucionar cura nada: el cuerpo herido es el que gana la vida y el "
        "sano es el que puede esperar en la banca")


@pytest.mark.parametrize("wounded_first", [False, True])
def test_without_a_sniper_the_damaged_one_still_goes_first(wounded_first):
    """No threat on the board: the gradient decides on its own.

    Nobody is inside the window, so the rescue does not fire -- but moving the
    counters into the bigger pool and leaving the intact copy behind is still
    strictly better.
    """
    obs = _board(wounded_hp=30, wounded_first=wounded_first,
                 op_active=MORGREM)
    chosen = _chosen(obs)
    assert chosen["type"] == int(OptionType.EVOLVE), chosen
    assert chosen["inPlayIndex"] == _bench_index_of(obs, APPLIN, 30), chosen


def test_two_intact_copies_do_not_move_the_score():
    """The bias is a TIE-BREAK: with nothing to tell the bodies apart it is 0
    and the decision goes back to being whatever it was."""
    obs = _board(wounded_hp=40)
    chosen = _chosen(obs)
    assert chosen["type"] == int(OptionType.EVOLVE), chosen


# ---------------------------------------------------------------------------
# 3. The calculation, body to body
# ---------------------------------------------------------------------------

class _Body:
    """The four fields `evolution_body_bias` reads."""
    def __init__(self, card_id, hp, max_hp):
        self.id, self.hp, self.maxHp = card_id, hp, max_hp


def test_the_rescue_beats_the_gradient():
    """A body inside the window that leaves it is worth more than one that is
    merely more damaged but was never in danger."""
    snipe = m.OP_BENCH_SNIPE_DAMAGE[GRIMMSNARL]      # 30
    rescued = m.evolution_body_bias(_Body(APPLIN, 10, 40), DIPPLIN, False, snipe)
    hurt = m.evolution_body_bias(_Body(APPLIN, 31, 40), DIPPLIN, False, snipe)
    assert rescued > hurt > 0
    assert rescued <= m.EVO_BODY_RESCUE + m.EVO_BODY_DAMAGE


def test_the_intact_body_gets_nothing():
    assert m.evolution_body_bias(
        _Body(APPLIN, 40, 40), DIPPLIN, False, 30) == 0


def test_it_does_not_upgrade_the_prize_of_a_body_that_dies_anyway():
    """The evolution does not take it out of the window and hands over MORE
    prizes: evolving there does not save a body, it raises the opponent's prize
    from one to two."""
    # An active Dipplin at 20/80 becomes a 270/330 Hydrapple ex -- and their
    # projected damage against the active is above that.
    doomed = m.evolution_body_bias(_Body(DIPPLIN, 20, 80), HYDRAPPLE, True, 310)
    assert doomed == -m.EVO_BODY_EXPOSURE
    # The same body with a hit it survives is the usual rescue.
    saved = m.evolution_body_bias(_Body(DIPPLIN, 20, 80), HYDRAPPLE, True, 180)
    assert saved > 0


def test_the_swing_never_crosses_a_band():
    """The whole point of the bounds: this orders BODIES, it never decides
    which CARD is played (the bands of evolve.py are 500 apart)."""
    assert (m.EVO_BODY_RESCUE + m.EVO_BODY_DAMAGE) + m.EVO_BODY_EXPOSURE < 500
