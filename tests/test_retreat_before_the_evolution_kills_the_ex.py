"""The finisher that is not on the board yet, and which body we hand over.

Scenario (`records/registro_002_pasos_016_hasta_025.json`, step 25, episode
89628162 vs Mega Lucario ex -- LOST):

    US                                     RIVAL (Mega Lucario ex)
    active  Meowth ex 170 (1 Grass)        active  Riolu 80 (1 Fighting)
    bench   Chikorita 70                   bench   --
            Teal Mask Ogerpon ex 210 (1)
            Applin 40
    hand    Lillie's, Ultra Ball, Xerosic x2, Tapu Bulu, Grass, **Dipplin**

Turn 2. The Meowth ex needs three energies to attack and carries one, so the
turn has no attack in it. The retreat DID exist in the menu (the single Grass
pays its cost of 1) and the agent chose to END THE TURN. Their turn 3: the Riolu
evolved into Mega Lucario ex and Aura Jab took 320 damage and two prizes off a
body that was never going to attack.

WHY NOTHING FIRED. `_doomed_ex_sac_pivot` is built for exactly this -- retreat
the ex that is going to die, put a 1-prize body in front, concede one prize
instead of two -- and every one of its gates was satisfied except the one that
matters: it asks `_op_active_attack_damage_to`, which reads the body IN FRONT.
Accelerating Stab projects 60 against 170 HP, so the board looked quiet. The
card that kills us was in their hand.

THE FIX, in three parts:

  * `_op_evolution_attack_damage_to` (ptcg/calc/damage.py) runs the same
    projection against what the opposing active can BECOME in one step, keeping
    the energies and tools it already carries. Deck-agnostic: it reads the
    reverse index of `evolvesFrom`, so Riolu answers Mega Lucario ex and a final
    stage answers 0. It is OPT-IN, like `scaled=True`, and its only consumer is
    this pivot;
  * the POSTPONEMENT stopped being a cancellation. The pivot waits while a
    development play is pending, which is right -- but here the pending play was
    a Tapu Bulu that the turn-2 rule vetoes, so it never happened and the pivot
    stayed off for the whole turn. It is now a score floor of 1: the retreat
    still yields to every real play (they score in the thousands, and putting a
    Pokemon down also outranks it by TIER) and never to ENDING THE TURN;
  * the promotion after that retreat is choosing a body to LOSE, so the order is
    the user's: **Chikorita, then Applin** -- the Applin is the first link of
    Dipplin -> Hydrapple ex, the deck's attacker -- **unless its evolution is
    already in hand**, in which case that body is next turn's play and the other
    one goes. In the record we hold a Dipplin, so the Chikorita is the sacrifice.
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
from cg.api import OptionType
from tests.state_builder import Escenario, pk, C, G

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "lucario_t2_retreat_before_the_evolution_step25.json")

MEOWTH = m.Meowth_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
APPLIN = m.Applin
DIPPLIN = m.Dipplin
TAPU = m.Tapu_Bulu
RIOLU = m.Riolu
MEGA_LUCARIO = m.Mega_Lucario_ex
GRASS = m.Basic_Grass_Energy
LILLIE = m.Lillie_Determination


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
    m._ub_fez_pending = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _obs_fixture():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _chosen(obs):
    """(option type, the card it points at) of the agent's decision."""
    o = obs["select"]["option"][m.agent(copy.deepcopy(obs))[0]]
    return o.get("type"), o


def _promoted_id(obs):
    cur = obs["current"]
    bench = cur["players"][cur["yourIndex"]]["bench"]
    _, opt = _chosen(obs)
    return bench[opt["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. The projection: what the body in front is going to become
# ---------------------------------------------------------------------------

def test_the_riolu_projects_the_hit_of_the_lucario_it_becomes():
    """80 HP and a 30-damage attack in front; 540 on the way (Mega Brave 270,
    doubled by the {F} weakness of the Meowth ex)."""
    riolu = m._ProjTarget(RIOLU, (), (int(m.EnergyType.FIGHTING),))
    meowth = m._ProjTarget(MEOWTH)
    assert m._op_active_attack_damage_to(riolu, meowth, 7) < 170
    assert m._op_evolution_attack_damage_to(riolu, meowth, 7) >= 170


def test_a_final_stage_projects_nothing_extra():
    """The reading costs nothing where there is no line to read: every caller
    takes max() of the two without a special case."""
    lucario = m._ProjTarget(MEGA_LUCARIO, (), (int(m.EnergyType.FIGHTING),))
    assert m._op_evolution_attack_damage_to(lucario, m._ProjTarget(MEOWTH), 7) == 0


# ---------------------------------------------------------------------------
# 2. The record: it retreats instead of ending the turn
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_turn_2_that_was_lost():
    o = _obs_fixture()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert cur["turn"] == 2 and cur["firstPlayer"] != cur["yourIndex"]
    assert mine["active"][0]["id"] == MEOWTH
    assert len(mine["active"][0]["energies"]) == 1      # it cannot attack (needs 3)
    assert theirs["active"][0]["id"] == RIOLU
    assert len(theirs["active"][0]["energies"]) == 1
    assert sorted(b["id"] for b in mine["bench"] if b) == sorted(
        [CHIKORITA, OGERPON, APPLIN])
    assert DIPPLIN in [c["id"] for c in mine["hand"]]
    assert any(op["type"] == int(OptionType.RETREAT)
               for op in o["select"]["option"]), "el paso ofrecia retirarse"


def test_it_retreats_the_doomed_meowth_instead_of_ending_the_turn():
    """The regression of the record: it used to choose END."""
    assert _chosen(_obs_fixture())[0] == int(OptionType.RETREAT)


# ---------------------------------------------------------------------------
# 3. Which body we hand over
# ---------------------------------------------------------------------------

def _promotion(hand, bench=(CHIKORITA, APPLIN, OGERPON)):
    """The SWITCH prompt right after retreating the doomed Meowth ex, with the
    board of the record: a charged Riolu in front and nothing ready to attack."""
    return (Escenario(turn=2, step=25, tac=10, first_player=1,
                      energy_played=True, supporter_played=True)
            .my_active(pk(MEOWTH, energies=[G]))
            .my_bench(*[b if isinstance(b, dict)
                        else pk(b, energies=[G]) if b == OGERPON else pk(b)
                        for b in bench])
            .my_hand(*hand)
            .op_active(pk(RIOLU, energies=[int(m.EnergyType.FIGHTING)]))
            .op_zonas(hand=7, deck=42, prizes=6)
            .promote_after_retreat()
            .build())


def test_with_the_dipplin_in_hand_the_chikorita_is_the_sacrifice():
    """The case in the record: the Applin has a Dipplin waiting for it, so the
    Applin is next turn's play and the Chikorita is what we can spare."""
    assert _promoted_id(_promotion([DIPPLIN, GRASS])) == CHIKORITA


def test_with_the_bayleef_in_hand_the_applin_goes_instead():
    """The exception the user named: now it is the Chikorita that has its
    evolution waiting, so the order flips."""
    assert _promoted_id(_promotion([BAYLEEF, GRASS])) == APPLIN


def test_holding_both_evolutions_nothing_distinguishes_them():
    """Neither body is spare, so the base order decides again: Chikorita."""
    assert _promoted_id(_promotion([BAYLEEF, DIPPLIN])) == CHIKORITA


def test_with_neither_evolution_in_hand_the_base_order_rules():
    """Chikorita before Applin: the Applin line ends in Hydrapple ex, the
    attacker the deck is built around."""
    assert _promoted_id(_promotion([GRASS, LILLIE])) == CHIKORITA


def test_the_two_prize_ogerpon_is_never_the_one_that_goes_up():
    """The whole point of the pivot is conceding ONE prize."""
    for hand in ([DIPPLIN, GRASS], [BAYLEEF, GRASS], [GRASS, LILLIE]):
        assert _promoted_id(_promotion(hand)) != OGERPON


# ---------------------------------------------------------------------------
# 4. The boundaries: when the sacrifice must NOT fire
# ---------------------------------------------------------------------------

def _main_menu(op_active, my_bench=(CHIKORITA, APPLIN), hand=(DIPPLIN, GRASS)):
    return (Escenario(turn=2, step=25, tac=10, first_player=1,
                      energy_played=True, supporter_played=True)
            .my_active(pk(MEOWTH, energies=[G]))
            .my_bench(*[pk(b) if not isinstance(b, dict) else b
                        for b in my_bench])
            .my_hand(*hand)
            .op_active(op_active)
            .op_zonas(hand=7, deck=42, prizes=6)
            .menu_hand(with_retreat=True)
            .build())


def test_an_opponent_whose_evolution_does_not_finish_us_does_not_move_us():
    """The control: the same doomed-looking board with a Chikorita in front --
    a line whose evolutions (Bayleef, Meganium) do not reach 170 -- ends the
    turn as it always did. The pivot reads the DAMAGE, not the fact that there
    is a line."""
    obs = _main_menu(pk(CHIKORITA, energies=[G]))
    assert _chosen(obs)[0] != int(OptionType.RETREAT)


def test_with_a_ready_attacker_on_the_bench_we_do_not_sacrifice():
    """`_bench_attacker_ready`: with a body that can attack there is a better
    plan than handing a corpse over, and the promotion has its own logic."""
    obs = _main_menu(pk(RIOLU, energies=[int(m.EnergyType.FIGHTING)]),
                     my_bench=(CHIKORITA, APPLIN,
                               pk(OGERPON, energies=[G, G, G])))
    assert _chosen(obs)[0] != int(OptionType.RETREAT)


def test_with_no_one_prize_body_on_the_bench_there_is_nothing_to_sacrifice():
    """Retreating to put another 2-prize ex in front concedes the same two
    prizes and loses the tempo as well."""
    obs = _main_menu(pk(RIOLU, energies=[int(m.EnergyType.FIGHTING)]),
                     my_bench=(pk(OGERPON, energies=[G]),))
    assert _chosen(obs)[0] != int(OptionType.RETREAT)


def test_a_two_prize_ex_never_beats_a_one_prize_body_in_the_sacrifice():
    """With neither Chikorita nor Applin on the bench the rule still has to
    concede the CHEAPEST body: the flip audit caught an earlier version handing
    over a Hydrapple ex because every unnamed body scored the same.

    The Hydrapple is WOUNDED on purpose. At full HP it survives Mega Brave, and
    a body that endures is not a sacrifice board at all -- that case is the test
    below."""
    obs = _promotion([GRASS, LILLIE],
                     bench=(pk(m.Hydrapple_ex, hp=200), pk(BAYLEEF, hp=100)))
    assert _promoted_id(obs) == BAYLEEF


def test_a_body_that_endures_switches_the_sacrifice_ordering_off():
    """The premise of a sacrifice is that whoever goes up falls, so the rule
    only speaks when NOBODY endures. A healthy Hydrapple ex (330) takes Mega
    Brave and keeps attacking: there the promotion goes back to its own measured
    logic -- which answers Applin -- and the Chikorita-first order does not
    apply. Wound that same Hydrapple below the hit and the rule takes over.

    The contrast is the point: the same bench, the same hand, and the only thing
    that moves is whether anything survives.
    """
    endures = _promotion([GRASS, LILLIE],
                         bench=(CHIKORITA, APPLIN, m.Hydrapple_ex))
    all_doomed = _promotion([GRASS, LILLIE],
                            bench=(CHIKORITA, APPLIN,
                                   pk(m.Hydrapple_ex, hp=200)))
    assert _promoted_id(endures) == APPLIN
    assert _promoted_id(all_doomed) == CHIKORITA
