"""The retreat fee is paid BEFORE the promotion is asked who comes up.

Scenario (`records/registro_002_pasos_014_hasta_034.json`, steps 31-33, turn 2
-- our first turn, going second, vs Marnie -- episode 90361829, WON):

    US (6 prizes)                             RIVAL (Marnie)
    active  Teal Mask Ogerpon ex 210 (1 {G})   active  Marnie's Impidimp 70 (1)
    bench   Meowth ex 170                      bench   Marnie's Impidimp 70 x2
            Chikorita 70
            Applin 40
            Teal Mask Ogerpon ex 210 (1 {G})
            Tapu Bulu 140 (1 {G})

The turn was spent -- Supporter played, energy attached, both Teal Dances used,
the bench full -- and the menu held two options: RETREAT and END. The agent
retreated, the Grass went to the discard... and the promotion brought up the
OTHER Teal Mask Ogerpon ex. Same body in front, one energy less. Nothing was
bought with it.

WHAT WAS BROKEN, and it was not the retreat. `_ft_wall_pivot` (main.py) decides
the retreat with the fee still on the active, and one observation later the same
flag was asked again to decide WHO comes up. By then the simulator has already
discarded the retreat cost, so its affordability test -- `_physical_energy >=
RETREAT_COST` -- reads the energy that is LEFT on a body that just paid. In the
canonical case of this rule, the one Grass of our first turn against a cost of
one, that is 0 >= 1: False on exactly the menu where the second half of the rule
had to act. The generic ranking (prizes x 1000 + HP) then does what it always
does and brings up the biggest body: the 2-prize ex the pivot exists to hide.

The affordability question belongs to the retreat and only to it. Once the fee
is spent, asking again whether we can afford it is asking about money already
handed over -- that is `_ft_wall_promote`.

WHY NO TEST CAUGHT IT: `promote_after_retreat()` in the scenario builder left
the fee on the active, so every synthetic board of this family was one the
simulator never emits. The builder now discounts it (see `_pay_the_retreat`),
which is what turns the two promotion tests of this family into controls: with
the flag reverted they fail with `96 == 920`, the record's own error.
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

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_step33_the_wall_takes_the_front_after_paying.json")

TAPU = m.Tapu_Bulu
OGERPON = m.Teal_Mask_Ogerpon_ex


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


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _promoted(obs):
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    opt = obs["select"]["option"][m.agent(copy.deepcopy(obs))[0]]
    return mine["bench"][opt["index"]]["id"]


def test_the_fixture_is_the_promotion_of_the_record():
    o = _obs()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]

    # Our first turn, going second, and the retreat is already paid for.
    assert cur["turn"] == 2 and cur["firstPlayer"] != cur["yourIndex"]
    assert cur["retreated"] is True
    assert o["select"]["context"] == int(m.SelectContext.SWITCH)

    # The active is the ex that just retreated, with NOTHING left on it: the
    # Grass that paid is in the discard. That is the board the flag misread.
    assert mine["active"][0]["id"] == OGERPON
    assert mine["active"][0]["energies"] == []
    assert any(c["id"] == m.Basic_Grass_Energy for c in mine["discard"])

    # And the bench holds both candidates: the wall and the ex's own twin.
    bench = [b["id"] for b in mine["bench"]]
    assert TAPU in bench and OGERPON in bench


def test_the_promotion_brings_up_the_wall_and_not_the_twin():
    assert _promoted(_obs()) == TAPU, (
        "la tasa ya esta pagada cuando se pregunta quien sube: el muro de 1 "
        "premio toma el frente, no el gemelo del mismo ex que se acaba de "
        "retirar (el registro subio el ex y solo perdio la energia)")


def test_control_with_no_wall_on_the_bench_the_ladder_decides():
    # The flag names ONE body. Without it on the bench there is nothing to
    # promote in its place and the generic ranking owns the decision again --
    # which is what makes the assertion above about the wall and not about
    # "anything except the ex".
    o = _obs()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    tapu_i = next(i for i, b in enumerate(mine["bench"]) if b["id"] == TAPU)
    mine["bench"] = [b for i, b in enumerate(mine["bench"]) if i != tapu_i]
    o["select"]["option"] = [
        {**opt, "index": opt["index"] - (1 if opt["index"] > tapu_i else 0)}
        for opt in o["select"]["option"] if opt["index"] != tapu_i]
    assert _promoted(o) == OGERPON, (
        "sin muro en banca la promocion vuelve a la escalera de siempre")


def test_control_a_damaged_wall_is_not_a_wall():
    # The premise of the pivot is that the body taking the front ENDURES. A
    # Tapu that already took a hit is not the body that buys turns, and the
    # flag stops naming it.
    o = _obs()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    for b in mine["bench"]:
        if b["id"] == TAPU:
            b["hp"] = 60
    assert _promoted(o) != TAPU, (
        "un muro ya golpeado no es el cuerpo que compra turnos")
