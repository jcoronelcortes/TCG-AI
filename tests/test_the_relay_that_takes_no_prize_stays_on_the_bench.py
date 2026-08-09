"""A retreat that only lets a bench body chip does not earn the front spot.

Scenario (user, `records/registro_004_pasos_035_hasta_040.json` step 37, turn 4,
episode 90880936 vs an Iono deck, LOST):

    US (6 prizes)                       RIVAL (6 prizes)
    active Chikorita 70/70, 1 Grass     active Iono's Bellibolt ex 280/280,
           (Growl does 0; Seed Bomb            ZERO energy
            costs two)                  bench  3x Iono's Tadbulb 60/60,
    bench  Dipplin 80/80, 1 Grass              Iono's Kilowattrel 120/120,
    hand   Hydrapple ex, Boss's Orders,        Iono's Voltorb 70/70 on TWO
           Xerosic's, 1 Basic Grass
    the turn's attachment ALREADY SPENT (it went onto the Chikorita)

The agent RETREATED. The fee discarded the Grass it had just attached, the
Dipplin came up and threw Do the Wave -- 20 damage for each of our Benched
Pokemon, and after the swap the bench holds ONE. Twenty, into 280 at full
health. The next record has the bill: the promoted Dipplin was knocked out on
the reply, Applin and Dipplin went to the discard together, the opponent took a
prize, and the Hydrapple ex stayed in hand with no body left to evolve.

Cause -- ONE pointer read by TWO menus. `plan.attacker` named the benched
Dipplin, and both consumers cashed it without asking what that body would
achieve:

1. `ptcg/turn/options/retreat.py` scored the retreat 3500 on the strength of
   `_plan_relay_can_attack`, which answers whether the relay's attack is LEGAL.
2. `ptcg/turn/options/attack.py` VETOED our own active's attack for the mirror
   reason -- "do not attack, retreat to the relay".

So fixing only the retreat leaves the turn with no play at all: the veto on the
attack survives, everything scores below zero and the menu falls through to a
Boss's Orders spent on nothing.

Fix: `_plan_relay_is_inert` (main.py), read off the turn plan and consumed by
both menus. The front spot has three things to sell and the relay here buys
none of them -- a prize (`prizes_today`, which already counts this very retreat
through `_prizes_via_promote`), a knockout within reach (`remain_hp` <= the
damage that produced it) or a cheaper body in front (`prize_count`) -- and our
active is not running from anything (`op_prizes_next`). No card id and no
matchup appear in it.

Golden corpus: 0 flips.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m
from cg.api import EnergyType, OptionType
from ptcg.state.agent_state import AGENT_STATE
from state_builder import G, Scenario, pk

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "bellibolt_the_relay_that_takes_no_prize_step37.json")

COLORLESS = int(EnergyType.COLORLESS)

CHIKORITA = m.Chikorita
APPLIN = m.Applin
DIPPLIN = m.Dipplin
HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
GRASS = m.Basic_Grass_Energy
BOSS = m.Boss_Orders

GROWL = 1322                 # Chikorita: 0 damage, -20 to their next attack
DO_THE_WAVE = 115            # Dipplin: 20 for each of OUR Benched Pokemon

BELLIBOLT_EX, TADBULB = 269, 268
FARFETCHD = 123              # a Basic whose line ENDS there, 70 HP, hits for 30
GREAT_TUSK = 58              # Giant Tusk: 160 for four, so it kills a 70 HP body


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
    yield
    m._init_cards_tracking()


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _chosen(obs):
    return obs["select"]["option"][m.agent(copy.deepcopy(obs))[0]]


# ---------------------------------------------------------------------------
# 1. The board: without this, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_mute_chikorita_in_front_of_a_280_hp_ex():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mine, rival = o["current"]["players"][yo], o["current"]["players"][1 - yo]

    active = mine["active"][0]
    assert active["id"] == CHIKORITA and active["hp"] == 70
    assert len(active["energies"]) == 1        # the fee the retreat would burn
    assert m.RETREAT_COST[CHIKORITA] == 1

    relay = mine["bench"][0]
    assert relay["id"] == DIPPLIN and relay["hp"] == 80
    assert len(relay["energies"]) == 1         # Do the Wave is already payable
    assert len([b for b in mine["bench"] if b]) == 1

    # The evolution of the relay is IN HAND, and the turn has nothing left to
    # attach: whatever is on the board is all there will be.
    assert any(c["id"] == HYDRAPPLE for c in mine["hand"])
    assert o["current"]["energyAttached"] is True

    # In front of us a 280 HP ex, and the menu really does offer both plays.
    assert rival["active"][0]["id"] == BELLIBOLT_EX
    assert rival["active"][0]["hp"] == 280
    types = [x["type"] for x in o["select"]["option"]]
    assert int(OptionType.RETREAT) in types
    assert int(OptionType.ATTACK) in types


def test_the_plan_itself_says_the_swap_takes_nothing():
    """The numbers the rule hangs on, read after the agent has run: the relay
    leaves 260 of the 280 standing, and no route takes a prize today."""
    m.agent(_obs())
    assert AGENT_STATE.plan.attacker >= 1          # the pointer names the bench
    assert AGENT_STATE.plan.remain_hp == 260       # 280 - 20 = thirteen more turns
    assert AGENT_STATE.turn_plan.prizes_today == 0
    assert AGENT_STATE.turn_plan.op_prizes_next == 0
    assert not AGENT_STATE.turn_plan.wins_this_turn


# ---------------------------------------------------------------------------
# 2. The decision of the record, and its other half
# ---------------------------------------------------------------------------

def test_the_dipplin_stays_on_the_bench():
    chosen = _chosen(_obs())
    assert chosen["type"] != int(OptionType.RETREAT), (
        "un Dipplin que quita 20 a un ex de 280 no compra el puesto activo: la "
        "tasa quema la Planta del turno y expone el unico cuerpo que el "
        "Hydrapple ex de la mano puede evolucionar")


def test_and_the_turn_is_not_left_without_a_play():
    """The half that makes the fix a fix. With the retreat gone, the veto the
    same pointer puts on OUR attack has to lift as well; otherwise every option
    scores below zero and the menu falls through to a Boss's Orders spent on
    nothing."""
    o = _obs()
    chosen = _chosen(o)
    assert chosen["type"] == int(OptionType.ATTACK), chosen
    assert chosen["attackId"] == GROWL, (
        "el Chikorita se queda delante y usa Growl: cero dano, pero -20 al "
        "ataque que viene y la linea Applin/Dipplin sigue en la banca")

    mine = o["current"]["players"][o["current"]["yourIndex"]]
    assert any(c["id"] == BOSS for c in mine["hand"]), (
        "el control de este test: la Boss's Orders es lo que el menu elegia "
        "cuando solo se arreglaba la mitad de la retirada")


# ---------------------------------------------------------------------------
# 3. The four escapes, one board each, on a different opponent
# ---------------------------------------------------------------------------
#
# The same Chikorita/Dipplin shape against a Basic whose line ends there, so
# nothing here can be read as a rule about Iono's Bellibolt ex. The hand is
# EMPTY on purpose: what is measured is retreat-versus-attack, with no card
# competing for the turn.

def _relay_board(op_active, active=None):
    return (Scenario(turn=6, step=60, tac=3, own_prizes=6,
                     supporter_played=True, energy_played=True)
            .my_active(active or pk(CHIKORITA, energies=[G], fisicas=1))
            .my_bench(pk(DIPPLIN, energies=[G], fisicas=1, pre_evo=[APPLIN]))
            .op_active(op_active)
            .op_bench(pk(FARFETCHD))
            .op_zones(hand=5, deck=25, prizes=6)
            .my_hand()
            .deck()
            .rest_to_discard()
            .menu_hand(with_retreat=True, with_attack=True)
            .build())


def test_the_rule_itself_a_relay_out_of_reach_of_the_knockout():
    """The board the rule is for, rebuilt: 20 against 280 is not an instalment,
    it is a number."""
    chosen = _chosen(_relay_board(pk(BELLIBOLT_EX, hp=280, pre_evo=[TADBULB])))
    assert chosen["type"] == int(OptionType.ATTACK), chosen


def test_control_a_relay_that_takes_the_prize_keeps_the_retreat():
    """PRIZE gate. The same board against a 20 HP body: Do the Wave knocks it
    out, `prizes_today` is 1 and the swap pays for itself."""
    chosen = _chosen(_relay_board(pk(FARFETCHD, hp=20)))
    assert chosen["type"] == int(OptionType.RETREAT), chosen


def test_control_a_relay_with_the_knockout_within_reach_keeps_the_retreat():
    """REACH gate. Thirty HP left and the relay hits for 20: `remain_hp` comes
    out at 10, one more of the same finishes it, so today's chip is the first
    instalment of tomorrow's prize."""
    chosen = _chosen(_relay_board(pk(FARFETCHD, hp=30)))
    assert chosen["type"] == int(OptionType.RETREAT), chosen


def test_control_a_cheaper_body_in_front_keeps_the_retreat():
    """PRICE gate. The same 280 HP ex, out of reach exactly as before, but now
    the body in front is a 2-prize ex of ours: handing the spot to a 1-prize
    Dipplin is worth the fee with no damage at all."""
    chosen = _chosen(_relay_board(pk(BELLIBOLT_EX, hp=280, pre_evo=[TADBULB]),
                                  active=pk(OGERPON, energies=[G], fisicas=1)))
    assert chosen["type"] == int(OptionType.RETREAT), chosen


def test_control_a_doomed_active_keeps_the_retreat():
    """RESCUE gate. A Great Tusk on four energies throws Giant Tusk for 160 and
    our 70 HP active does not survive it: the swap is an escape, and what pays
    for it is the body it saves, not the relay's damage."""
    chosen = _chosen(_relay_board(pk(GREAT_TUSK, energies=[COLORLESS] * 4)))
    assert chosen["type"] == int(OptionType.RETREAT), chosen


def test_the_boundary_of_the_rescue_gate_is_their_damage():
    """And the pair that proves it is `op_prizes_next` doing the work: the same
    Great Tusk two energies short cannot pay Giant Tusk, our active survives,
    and the veto is back."""
    chosen = _chosen(_relay_board(pk(GREAT_TUSK, energies=[COLORLESS] * 2)))
    assert chosen["type"] == int(OptionType.ATTACK), chosen


# ---------------------------------------------------------------------------
# 4. The relay's attack, so the numbers above are not read off a table
# ---------------------------------------------------------------------------

def test_do_the_wave_counts_the_bench_the_swap_leaves_behind():
    """Twenty is not a constant: Do the Wave scales with OUR bench, and after
    this retreat the bench holds the one body the retreat put there."""
    assert m.attack_table[DO_THE_WAVE].name == "Do the Wave"
    assert m.attack_table[DO_THE_WAVE].damage == 0        # it is all scaling
    assert m.attack_table[GROWL].damage == 0              # and Growl adds none
