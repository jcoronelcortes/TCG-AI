"""The ex does not wait in front of the Mega Starmie line.

Scenario (`records/registro_002_pasos_009_hasta_028.json`, step 28, episode
90583594, turn 2 -- our first turn, going second, vs Mega Starmie ex, LOST):

    US (6 prizes)                              RIVAL (Mega Starmie ex)
    active  Teal Mask Ogerpon ex 210 (1 {G})   active  Staryu 70 (1 {W})
    bench   Applin 40 (1 {G})                  bench   --
            Meowth ex 170
            Teal Mask Ogerpon ex 210 (1 {G})
            Applin 40
    hand    Ultra Ball x2, Forest of Vitality, Lillie's, Grass, Meganium,
            Boss's Orders          (the Supporter and the attachment are spent)

The turn closed in END with the 2-prize ex in front. Nothing on the board said
it was in danger, and every pivot that could have moved it agreed:

  * `_ft_wall_pivot` looks for an undamaged one-prize WALL on the bench
    (`is_one_prize_wall`: a Basic, one prize, >= FIRST_TURN_WALL_MIN_HP and a
    real attacker). Two 40 HP Applin are not that, so it never found a body.
  * `_doomed_sac_context` and `_doomed_ex_sac_pivot` ask the damage projector,
    the evolution included. It answers 120 -- Jetting Blow, the only Mega
    Starmie attack a Staryu with one energy plus the projector's "+1 next turn"
    can pay -- and 120 does not knock out 210 HP, so nobody is doomed.

Both readings miss the SECOND attack printed on that card: Nebula Beam, 210 for
three energies, which is exactly the HP of our Ogerpon ex -- and the deck runs
Ignition Energy to get there in one turn. The projector is right about what
they can pay today and wrong about what this line IS, which is why the rule is
stated as a MATCHUP and not as an arithmetic threshold.

THE RULE (user): against the Staryu -> Mega Starmie ex line, if we canNOT
attack and the active is a 2-prize ex, retreat it and put a ONE-prize body in
front, so the opening knockout pays one prize and not two. The order of who
goes in front is STARMIE_SAC_PROMOTE_ORDER: Tapu Bulu (played from hand this
turn if that is where it is), then an Applin -- the copy WITHOUT energy first,
so the charged one keeps its attachment on the bench -- then Chikorita,
Dipplin, Bayleef, Meowth ex, and finally any other option.

IT IS AN OPENING RULE, AND THE GATE IS WHY (ago 2026, n=1000 per arm against
`deck/real_opponents/mega_starmie_1.csv` and `_2.csv`, two arms differing ONLY
in `op_is_starmie_deck`, control `alakazam.csv` at -0.5 points):

    rule OFF                     88.3% / 88.6%   prizes +2.95 / +2.66
    every turn we cannot attack  84.0% / 81.3%   prizes +2.41 / +1.97
    OUR FIRST TURN only          88.5% / 85.7%   prizes +2.90 / +2.48

"We cannot attack" is the ordinary shape of a turn spent developing: stated for
any turn the pivot fires 9.8-11.4 times PER GAME, and each firing discards an
energy and hands a 40 HP Applin to a deck happy to take it. Bounded to the
opening -- which is the rule's own motivation, "to avoid giving away two prizes
at the START of the game" -- it fires once, fixes step 28, and costs nothing the
gate can measure.

`_our_first_turn` also subsumes the seat exemption `_prize_mismatch_matchup`
carries: on turn 1 going FIRST the player cannot attack by rule, so without it
the pivot would burn the only Grass of the turn in every single game.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import Scenario, pk

_FIXTURE = ROOT / "tests" / "fixtures" / "starmie_hide_the_ex_step28.json"

G = int(m.EnergyType.GRASS)
W = int(m.EnergyType.WATER)

STARYU = m.Staryu
MEGA_STARMIE = m.Mega_Starmie_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
APPLIN = m.Applin
CHIKORITA = m.Chikorita
DIPPLIN = m.Dipplin
BAYLEEF = m.Bayleef
TAPU = m.Tapu_Bulu
MEOWTH = m.Meowth_ex
HYDRAPPLE = m.Hydrapple_ex
ALAKAZAM = 743          # another matchup, to pin that the rule is deck-specific


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
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _obs_fixture():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _scenario(active=None, bench=(), hand=(), op_active=None,
              turn=2, first_player=1, energy_played=True,
              supporter_played=True):
    """The record's board, parameterised. `first_player=1` = we go SECOND,
    which is the seat of the record and the one the rule fires in."""
    active = active if active is not None else pk(OGERPON, energies=[G])
    op_active = op_active if op_active is not None else pk(STARYU, energies=[W])
    sc = (Scenario(turn=turn, step=28, first_player=first_player,
                   energy_played=energy_played,
                   supporter_played=supporter_played)
          .my_active(active)
          .op_active(op_active)
          .op_zones(hand=7, deck=33, prizes=6))
    if bench:
        sc = sc.my_bench(*bench)
    if hand:
        sc = sc.my_hand(*hand)
    return sc


def _chosen(obs):
    return obs["select"]["option"][m.agent(obs)[0]]


def _promoted(obs):
    idx = _chosen(obs)["index"]
    return obs["current"]["players"][0]["bench"][idx]


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------

def test_step28_the_record_turn_retreats_instead_of_ending():
    """The failing decision of episode 90583594, replayed as it was served."""
    obs = _obs_fixture()
    assert _chosen(obs)["type"] == int(m.OptionType.RETREAT)


def test_step28_the_applin_without_energy_takes_the_front():
    """Both Applin pay the same single prize; what separates them is what stays
    behind. Sending the charged one throws its Grass away with the body."""
    obs = _scenario(
        bench=(pk(APPLIN, energies=[G]), pk(MEOWTH),
               pk(OGERPON, energies=[G]), pk(APPLIN)),
        hand=(m.Ultra_Ball,)).promote_after_retreat().build()
    body = _promoted(obs)
    assert body["id"] == APPLIN and not body["energies"]


# ---------------------------------------------------------------------------
# The order the user gave
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bench,expected", [
    # Tapu Bulu heads the list even against the cheapest bodies we own.
    ((pk(APPLIN), pk(CHIKORITA), pk(TAPU), pk(MEOWTH)), TAPU),
    # Applin before Chikorita: the reverse of the generic sacrifice order,
    # because this menu is not choosing which evolution line to spend.
    ((pk(CHIKORITA), pk(APPLIN), pk(MEOWTH)), APPLIN),
    ((pk(DIPPLIN), pk(CHIKORITA), pk(MEOWTH)), CHIKORITA),
    ((pk(BAYLEEF), pk(DIPPLIN), pk(MEOWTH)), DIPPLIN),
    ((pk(MEOWTH), pk(BAYLEEF)), BAYLEEF),
])
def test_the_promotion_follows_the_order(bench, expected):
    obs = _scenario(bench=bench, hand=(m.Ultra_Ball,)) \
        .promote_after_retreat().build()
    assert _promoted(obs)["id"] == expected


def test_the_tapu_bulu_in_hand_goes_down_so_it_can_come_up():
    """The one rung of the order that can be missing from the board and still
    be arranged for: a Basic goes down and comes up in the same turn."""
    obs = _scenario(bench=(pk(APPLIN), pk(MEOWTH)),
                    hand=(TAPU, m.Ultra_Ball)).menu_hand(with_retreat=True).build()
    chosen = _chosen(obs)
    assert chosen["type"] == int(m.OptionType.PLAY)
    assert obs["current"]["players"][0]["hand"][chosen["index"]]["id"] == TAPU


# ---------------------------------------------------------------------------
# What the rule does NOT do
# ---------------------------------------------------------------------------

def test_a_turn_that_can_attack_takes_its_attack():
    """`not can_attack` is the whole gate on the offensive side: with the
    Ogerpon charged enough to fire, the retreat is not the play."""
    obs = _scenario(active=pk(OGERPON, energies=[G] * 3),
                    bench=(pk(APPLIN), pk(MEOWTH)),
                    hand=(m.Ultra_Ball,)) \
        .menu_hand(with_retreat=True, with_attack=True).build()
    assert _chosen(obs)["type"] == int(m.OptionType.ATTACK)


def test_with_no_one_prize_body_on_the_bench_it_does_not_retreat():
    """A retreat into a bench of nothing but ex spends the fee and changes
    which two prizes we are offering."""
    obs = _scenario(bench=(pk(MEOWTH), pk(HYDRAPPLE)),
                    hand=(m.Ultra_Ball,)).menu_hand(with_retreat=True).build()
    assert _chosen(obs)["type"] == int(m.OptionType.END)


def test_with_the_fee_unpaid_it_does_not_retreat():
    """The engine only offers the retreat once the cost is on the body; with a
    bare active there is nothing for the pivot to spend."""
    obs = _scenario(active=pk(OGERPON),
                    bench=(pk(APPLIN), pk(MEOWTH)),
                    hand=(m.Ultra_Ball,)).menu_hand(with_retreat=True).build()
    assert _chosen(obs)["type"] != int(m.OptionType.RETREAT)


def test_a_one_prize_active_is_already_the_body_we_want():
    """The rule hides an EX. With an Applin already in front there is nothing
    for it to hide, so the matchup changes nothing: whatever the rest of the
    ladder decides on that board it decides the same way with the Staryu there
    and with any other opponent."""
    def _answer(op_active):
        m.AGENT_STATE.reset()
        m._init_cards_tracking()
        obs = _scenario(active=pk(APPLIN, energies=[G]),
                        bench=(pk(CHIKORITA), pk(OGERPON)),
                        hand=(m.Ultra_Ball,),
                        op_active=op_active).menu_hand(with_retreat=True).build()
        return _chosen(obs)["type"]

    assert _answer(pk(STARYU, energies=[W])) == _answer(pk(ALAKAZAM, energies=[G]))


def test_turn_1_going_first_does_not_sacrifice():
    """The player going first cannot attack on turn 1 by rule, so without this
    exemption the pivot would fire in every single game, before the opponent
    has played a card."""
    obs = _scenario(turn=1, first_player=0,
                    bench=(pk(APPLIN), pk(MEOWTH)),
                    hand=(m.Ultra_Ball,)).menu_hand(with_retreat=True).build()
    assert _chosen(obs)["type"] != int(m.OptionType.RETREAT)


def test_it_is_an_opening_rule_and_does_not_fire_later():
    """The same board four turns on. "We cannot attack" is the ordinary shape
    of a developing turn: left unbounded the pivot fires ten times a game and
    the gate charges 3 to 6 points for it."""
    obs = _scenario(turn=6,
                    bench=(pk(APPLIN), pk(MEOWTH)),
                    hand=(m.Ultra_Ball,)).menu_hand(with_retreat=True).build()
    assert _chosen(obs)["type"] != int(m.OptionType.RETREAT)


def test_the_rule_is_deck_specific():
    """Against another deck the same board keeps the answer it had before."""
    obs = _scenario(op_active=pk(ALAKAZAM, energies=[G]),
                    bench=(pk(APPLIN, energies=[G]), pk(MEOWTH), pk(APPLIN)),
                    hand=(m.Ultra_Ball,)).menu_hand(with_retreat=True).build()
    assert not m.AGENT_STATE.op_is_starmie_deck
    assert _chosen(obs)["type"] == int(m.OptionType.END)


# ---------------------------------------------------------------------------
# The matchup flag
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("where", ["active", "bench", "discard"])
def test_the_line_is_recognised_wherever_it_shows_up(where):
    """A 70 HP Staryu threatens nothing, and the point of the rule is to have
    acted BEFORE the 330 HP body arrives -- so the flag is sticky and reads the
    line off the active spot, the bench and the discard alike."""
    sc = _scenario(bench=(pk(APPLIN),), hand=(m.Ultra_Ball,),
                   op_active=pk(ALAKAZAM, energies=[G]))
    if where == "active":
        sc = _scenario(bench=(pk(APPLIN),), hand=(m.Ultra_Ball,))
    elif where == "bench":
        sc = sc.op_bench(pk(STARYU))
    else:
        sc = sc.op_discard(MEGA_STARMIE)
    m.agent(sc.menu_hand(with_retreat=True).build())
    assert m.AGENT_STATE.op_is_starmie_deck
