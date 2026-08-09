"""An evolution played in front must attack or take the hit; otherwise it goes
on the bench.

Scenario (`records/registro_004_pasos_033_hasta_045.json` step 44, turn 4,
episode 90875023 vs Abra/Kadabra/Alakazam, WON in spite of this):

    US (6 prizes)                          RIVAL (6 prizes)
    active  Bayleef **80/110, 0 energy**   active  Kadabra 80/80, 1 Psychic
    bench   Bayleef **110/110, 1 Grass**           (Super Psy Bolt: 30)
            Applin 40/40, 1 Grass          bench   Kadabra, Kadabra,
            Teal Mask Ogerpon ex, 1 Grass          Dunsparce, Dunsparce
    hand    1 Basic Grass, **Meganium**, 2 items   (hand: 9 cards)
    turn's attachment and Supporter ALREADY SPENT

The agent put the Meganium on the ACTIVE Bayleef. Up there it is a body that
does nothing: Solar Beam costs four and it inherits zero, its retreat costs two
and the turn's Grass is gone, and 130 HP does not survive the Alakazam that
three Kadabra are one card away from. The bench copy inherits a Grass instead
and starts at two of the four it needs.

Cause -- two of them, and the second is the one that decided the turn:

1. `ptcg/turn/options/evolve.py` demoted an evolution in the active spot only
   under `active_ko_likely`, exempted Meganium by card id, and read "can it
   attack" off an if/elif of three card ids. Here `active_ko_likely` was False
   (the Bayleef survives the 30 in front of it) and the card was Meganium, so
   the gate never ran. Its survival half was dead code besides: it read
   `getattr(attack_id, 'damage')` over `card.attacks`, which holds ints, so it
   always projected 0 damage and always concluded the body survives.

2. With no gate the two options scored the same 35000, and the +16 damage
   gradient of `evolution_body_bias` -- which exists to move counters into a
   bigger pool -- sent the Stage 2 to the body that could not use it.

Fix: one deck-agnostic gate. `energy_after_evolution` + `ATTACK_ENERGY_REQ`
answer "does it attack", `_op_window_against_evolution` answers "does it
survive" (and it reads the opposing line's NEXT step, which is what a projection
spanning one opposing turn owes), and the menu itself answers "is there
somewhere else to put it". No card id and no matchup appear in it.

Golden corpus: 1 flip, this one.
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
from cg.api import AreaType, OptionType
from state_builder import G, Scenario, pk

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_the_stage_goes_to_the_bench_step44.json")

BAYLEEF = m.Bayleef
MEGANIUM = m.Meganium
CHIKORITA = m.Chikorita
APPLIN = m.Applin
DIPPLIN = m.Dipplin
OGERPON = m.Teal_Mask_Ogerpon_ex

ABRA, KADABRA, ALAKAZAM = 741, 742, 743
FARFETCHD = 123          # a Basic with no evolution and a 30 damage attack


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

def test_the_fixture_is_the_empty_bayleef_in_front_of_the_kadabra():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mine, rival = o["current"]["players"][yo], o["current"]["players"][1 - yo]

    active = mine["active"][0]
    assert active["id"] == BAYLEEF and active["hp"] == 80 and active["maxHp"] == 110
    assert active["energies"] == []

    twin = mine["bench"][0]
    assert twin["id"] == BAYLEEF and twin["hp"] == twin["maxHp"] == 110
    assert len(twin["energies"]) == 1

    # The Stage 2 is in hand and the turn has nothing left to pay with: the
    # attachment is spent, so whatever the body carries is all it will have.
    assert any(c["id"] == MEGANIUM for c in mine["hand"])
    assert o["current"]["energyAttached"] is True
    assert m.ATTACK_ENERGY_REQ_BASE[MEGANIUM] == 4
    assert m.RETREAT_COST[MEGANIUM] == 2

    # In front of us a Kadabra that hits for 30 -- and behind it, two more.
    assert rival["active"][0]["id"] == KADABRA
    assert sum(1 for b in rival["bench"] if b and b["id"] == KADABRA) == 2
    assert ALAKAZAM in m._direct_evolution_ids(KADABRA)

    # And the menu really does offer the same card on both bodies.
    evolves = [x for x in o["select"]["option"]
               if x["type"] == int(OptionType.EVOLVE)]
    assert {x["inPlayArea"] for x in evolves} == {int(AreaType.ACTIVE),
                                                 int(AreaType.BENCH)}


# ---------------------------------------------------------------------------
# 2. The decision of the record
# ---------------------------------------------------------------------------

def test_the_meganium_goes_on_the_bayleef_that_carries_the_grass():
    chosen = _chosen(_obs())
    assert chosen["type"] == int(OptionType.EVOLVE), chosen
    assert chosen["inPlayArea"] == int(AreaType.BENCH), (
        "un Meganium delante con cero energia no ataca (Solar Beam cuesta 4), "
        "no se retira (cuesta 2 y la Planta del turno ya se gasto) y no aguanta "
        "al Alakazam: la copia de la banca hereda la Planta y sigue viva")


def test_the_projection_reads_the_alakazam_the_kadabra_is_about_to_be():
    """The number the gate hangs on. The body in front hits for 30 and a 130 HP
    Meganium laughs at it; the threat is the one that is not on the board."""
    o = _obs()
    rival = o["current"]["players"][1 - o["current"]["yourIndex"]]

    class _Body:
        id = KADABRA
        energies = [5]
        tools = ()

    window = m._op_window_against_evolution(_Body(), MEGANIUM,
                                            rival["handCount"])
    assert window >= 160, window          # 20 x (9 + 2), Powerful Hand
    assert m.card_table[MEGANIUM].hp - 30 < window


# ---------------------------------------------------------------------------
# 3. The three gates, on a different line and a different deck
# ---------------------------------------------------------------------------
#
# Applin -> Dipplin, so nothing here can be read as a Meganium special case.
# Dipplin costs ONE energy and has 80 HP; the active Applin carries 20 of
# damage, so the body it becomes starts at 60. `active_ko_likely` is deliberately
# OUT of the picture on every board (the active is at half life and the opposing
# active holds a single energy), which is what makes these boards measure the
# NEW gate and not the demotion that already existed.

def _two_applin(op_active, active_energy=(), with_twin=True):
    bench = [pk(APPLIN, hp=40, energies=list(active_energy))] if with_twin else []
    bench.append(pk(OGERPON, energies=[G], fisicas=1))
    return (Scenario(turn=6, step=60, tac=4, own_prizes=6,
                     supporter_played=True, energy_played=True)
            .my_active(pk(APPLIN, hp=20, max_hp=40,
                          energies=list(active_energy)))
            .my_bench(*bench)
            .op_active(op_active)
            .op_bench(pk(FARFETCHD, hp=70, max_hp=70))
            .op_zones(hand=5, deck=25, prizes=6)
            .my_hand(DIPPLIN)
            .deck()
            .rest_to_discard()
            .menu_evolve()
            .build())


def _kadabra():
    return pk(KADABRA, hp=80, max_hp=80, energies=[G], pre_evo=[ABRA])


def _farfetchd():
    return pk(FARFETCHD, hp=70, max_hp=70, energies=[G])


def test_a_body_that_neither_attacks_nor_survives_hands_the_card_to_the_bench():
    """The rule itself. The Dipplin would come out at 60 HP with no energy, and
    what is about to be in front of it hits for 20 x their hand."""
    chosen = _chosen(_two_applin(_kadabra()))
    assert chosen["type"] == int(OptionType.EVOLVE), chosen
    assert chosen["inPlayArea"] == int(AreaType.BENCH), chosen


def test_control_a_body_that_attacks_keeps_the_front_spot():
    """ATTACK gate. The same board with one energy on each Applin: the Dipplin
    swings the turn it arrives, so it is not a card buried under a corpse -- and
    the wounded copy is still the one that gains from evolving."""
    chosen = _chosen(_two_applin(_kadabra(), active_energy=[G]))
    assert chosen["type"] == int(OptionType.EVOLVE), chosen
    assert chosen["inPlayArea"] == int(AreaType.ACTIVE), chosen


def test_control_a_body_that_takes_the_hit_keeps_the_front_spot():
    """SURVIVE gate. The same board against a Basic whose line ENDS there and
    which hits for 30: 60 HP takes it, so the front spot costs nothing."""
    chosen = _chosen(_two_applin(_farfetchd()))
    assert chosen["type"] == int(OptionType.EVOLVE), chosen
    assert chosen["inPlayArea"] == int(AreaType.ACTIVE), chosen


def test_control_with_nowhere_else_to_put_it_the_card_still_goes_down():
    """ELSEWHERE gate. This rule moves an evolution, it does not cancel one: with
    no second body in the menu, a Stage in front still beats a Stage in hand."""
    chosen = _chosen(_two_applin(_kadabra(), with_twin=False))
    assert chosen["type"] == int(OptionType.EVOLVE), chosen
    assert chosen["inPlayArea"] == int(AreaType.ACTIVE), chosen


# ---------------------------------------------------------------------------
# 4. The two readings the gate is built on
# ---------------------------------------------------------------------------

class _Body:
    """The three fields `energy_after_evolution` reads."""
    def __init__(self, energies, physical_grass):
        self.energies = list(energies)
        self.energyCards = [type("C", (), {"id": m.Basic_Grass_Energy})()
                            for _ in range(physical_grass)]


def test_the_evolution_that_doubles_the_grass_counts_its_own_ability():
    """A Bayleef with two physical Grass reads 2 today and attacks with 4 the
    instant it is a Meganium: Wild Growth arrives WITH the card."""
    body = _Body([G, G], 2)
    assert m.energy_after_evolution(body, MEGANIUM) == 4
    assert m.energy_after_evolution(body, BAYLEEF) == 2
    # And the attachment the turn can still make is converted at the same rate.
    assert m.energy_after_evolution(body, MEGANIUM, 1) == 6
    assert m.energy_after_evolution(body, BAYLEEF, 1) == 3


def test_a_body_with_no_grass_gains_nothing_from_the_doubling():
    assert m.energy_after_evolution(_Body([], 0), MEGANIUM) == 0


def test_the_window_falls_back_to_the_body_in_front_when_the_line_ends():
    """`_op_window_against_evolution` takes the maximum of the two readings, so
    a final stage answers exactly what it hits for today."""
    class _Op:
        id = FARFETCHD
        energies = [0]
        tools = ()
    assert m._op_window_against_evolution(_Op(), DIPPLIN, 5) == 30
