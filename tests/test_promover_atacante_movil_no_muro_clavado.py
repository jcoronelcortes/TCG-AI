"""Promotion after a KO: do not bring up a NAILED-DOWN wall when the mobile near-attacker is there.

Scenario (`registros/registro_008_pasos_110_hasta_122.json`, step 122, turn 8,
LOST vs Dragapult -- episode 88912610). The Dragapult ex has just knocked out
our Hydrapple ex with Phantom Dive and we have to promote:

    US (4 prizes)                              OPPONENT (4 prizes)
    bench  Teal Mask Ogerpon ex 100/210, 2 en. active  Dragapult ex **50**/320, 2 en.
           Meganium 160, 0 en.                 bench   Fezandipiti ex 210,
           Teal Mask Ogerpon ex **200**/210, 2 en.     Dragapult ex 320, Drakloak 90
           Teal Mask Ogerpon ex 200/210, 2 en.
           Tapu Bulu 140, **0 energies**       stadium Team Rocket's Watchtower
    hand   Ogerpon ex, Ultra Ball, **Fezandipiti ex**, Dipplin, Meganium,
           Hydrapple ex, Tapu Bulu   (not a single Grass)

The agent brought up **Tapu Bulu**: 0 of 4 energies -- it does not attack -- and **retreat 3**
which it cannot pay -- it cannot be swapped out. It is a NAILED-DOWN body: it gives away the whole
turn and on top of that concedes a prize. Across the table, the Dragapult ex is at **50 HP**: an
Ogerpon ex with one more energy does *Myriad Leaf Shower* 30 + 30x(4+2) = **210** and takes 2
prizes.

Cause: `_promote_setup_ko_attacker` (bring up the attacker that is ONE attachment away from
finishing) requires being able to get that energy, and its list of routes -- Lillie's/Dawn in
hand, Lana's Aid, the Meowth ex engine -- **did not include Flip the Script**. Here all three
failed (a hand with no Supporters; and the Meowth engine is dead on top of that: Team Rocket's
Watchtower cancels the abilities of {C} Pokémon). With no route the override did not
fire and it handed over to `_ko_prefer_basic_general`, which picks the 1-prize wall by
LIFE (8500 + 140/10) without looking at whether that wall can do anything.

Fix, in two halves that hold each other up:

1. **Route (d): Fezandipiti ex → Flip the Script (draw 3).** It is the route that was
   missing, and the only one whose trigger is *guaranteed* in this branch: we are
   promoting because we have just been knocked out, which is exactly what lights up
   Flip the Script. Watchtower does not switch it off (it only kills {C} abilities; Fezandipiti
   ex is {D}); what does kill it is Iron Thorns, which cancels every ability with a Rule
   Box. It counts with the Fezandipiti already in play or in hand with a bench slot free.

2. **`_ps_conserva_salida`: route (d) requires the promoted body to be able to RETREAT**
   with the energy it already carries. Drawing 3 does not *search out* the Grass, so the
   plan may fail -- and that is why it is only accepted while it stays reversible: if
   the Grass does not show up, next turn the Ogerpon retreats (cost 1, it carries 2)
   and **then** the wall comes up. *The sacrifice is a deferrable decision;
   getting nailed down is not.* With the SEARCH routes (a/b/c) the energy is
   practically assured and no mobility is required.

Golden corpus: a single flip, this step's.
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
            / "dragapult_promover_ogerpon_no_tapu_step122.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu
FEZ = m.Fezandipiti_ex
DRAGAPULT = m.Dragapult_ex


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


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _bench(obs):
    yo = obs["current"]["yourIndex"]
    return obs["current"]["players"][yo]["bench"]


def _opt_de(obs, pred):
    bench = _bench(obs)
    return next(i for i, o in enumerate(obs["select"]["option"])
                if pred(bench[o["index"]]))


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_forced_promotion_after_the_ko():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]

    # Forced promotion: we have no active.
    assert not mio["active"]
    assert o["select"]["context"] == 4

    # The wall that was being brought up is NAILED DOWN: 0 energies and retreat 3.
    tapu = next(b for b in mio["bench"] if b["id"] == TAPU)
    assert len(tapu["energies"]) == 0
    assert m.RETREAT_COST[TAPU] == 3
    assert m.ATTACK_ENERGY_REQ[TAPU] == 4

    # The near-attacker DOES keep its way out: retreat 1 and it carries 2 energies.
    oger = [b for b in mio["bench"] if b["id"] == OGERPON]
    assert len(oger) == 3 and all(len(b["energies"]) == 2 for b in oger)
    assert m.RETREAT_COST[OGERPON] == 1
    assert max(b["hp"] for b in oger) == 200

    # ONE attachment away from finishing: Myriad = 30 + 30x(4 + 2) = 210 >= 50.
    act = riv["active"][0]
    assert act["id"] == DRAGAPULT and act["hp"] == 50
    assert 30 + 30 * (4 + len(act["energies"])) >= act["hp"]

    # The engine that makes it possible is in HAND, and no Supporter is.
    assert any(c["id"] == FEZ for c in mio["hand"])
    for _supp in (m.Lillie_Determination, m.Dawn, m.Lanas_Aid, m.Meowth_ex):
        assert not any(c["id"] == _supp for c in mio["hand"])
    # And there is not a single Grass in hand: the energy has to be drawn.
    assert not any(c["id"] == m.Basic_Grass_Energy for c in mio["hand"])

    # The record confirms that the Tapu Bulu was brought up there.
    assert json.load(open(_FIXTURE, encoding="utf-8"))["accion_registrada"] == [4]


def test_watchtower_kills_the_meowth_engine_but_not_the_fezandipiti_one():
    """Why the old routes failed and the new one does not: Watchtower only cancels
    the abilities of {C} Pokémon (Meowth ex), not those of Fezandipiti ex."""
    o = _obs()
    assert o["current"]["stadium"][0]["id"] == m.Team_Rockets_Watchtower
    assert m.card_table[m.Meowth_ex].energyType != m.card_table[FEZ].energyType


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_it_promotes_the_charged_ogerpon_not_the_nailed_down_tapu():
    o = _obs()
    tapu_opt = _opt_de(o, lambda b: b["id"] == TAPU)
    assert m.agent(_obs()) != [tapu_opt], (
        "Tapu Bulu a 0/4 con retirada 3 no ataca ni se puede cambiar: "
        "regala el turno entero")


def test_it_promotes_the_ogerpon_with_more_life():
    """Among the three Ogerpon ex at the same distance from the finisher, it brings up the
    200 HP one, not the 100: the life tie-break already lives in `_ps_key`."""
    o = _obs()
    elegido = m.agent(_obs())[0]
    bench = _bench(o)
    pk = bench[o["select"]["option"][elegido]["index"]]
    assert pk["id"] == OGERPON and pk["hp"] == 200


# ---------------------------------------------------------------------------
# 3. The limits of the rule
# ---------------------------------------------------------------------------

def test_with_no_fezandipiti_there_is_no_engine_and_the_wall_returns():
    """Control: with the Fezandipiti ex removed from hand there is no route left to
    get the Grass, and the promotion goes back to the cheap-wall logic."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    mio["hand"] = [c for c in mio["hand"] if c["id"] != FEZ]
    mio["handCount"] = len(mio["hand"])
    assert m.agent(o) == [_opt_de(o, lambda b: b["id"] == TAPU)]


def test_with_no_reachable_grass_there_is_no_engine():
    """Control: with ALL the Grass already visible (a hand empty of them +
    the discard) there is none hidden left to draw, and the engine does not fire."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    total = sum(1 for _l in open(ROOT / "deck.csv") if _l.strip() == "1")
    ya = sum(1 for c in mio["discard"] if c["id"] == m.Basic_Grass_Energy)
    ya += sum(1 for b in mio["bench"] if b
              for e in b["energyCards"] if e["id"] == m.Basic_Grass_Energy)
    mio["discard"] = mio["discard"] + [
        {"id": m.Basic_Grass_Energy, "playerIndex": yo, "serial": 900 + i}
        for i in range(total - ya)]
    assert m.agent(o) == [_opt_de(o, lambda b: b["id"] == TAPU)]


def test_si_el_casi_atacante_quedaria_clavado_el_motor_de_robo_no_basta(monkeypatch):
    """`_ps_conserva_salida` in isolation: the same board, the same distance to the finisher,
    but with the Ogerpon ex's retreat raised to 3 (it cannot pay it with
    its 2 energies). The plan stops being reversible -if the draw fails we
    get nailed down all the same- and the blind draw is no longer enough: the wall returns."""
    o = _obs()
    monkeypatch.setitem(m.RETREAT_COST, OGERPON, 3)
    assert m.agent(o) == [_opt_de(o, lambda b: b["id"] == TAPU)]


def test_with_a_search_supporter_mobility_is_not_required(monkeypatch):
    """The counterpart: with a Lillie's in hand (a SEARCH route, not a blind
    draw) the energy is practically assured, so mobility stops
    being a condition and the Ogerpon ex comes up even if its retreat is unpayable."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    mio["hand"] = mio["hand"] + [{"id": m.Lillie_Determination,
                                  "playerIndex": yo, "serial": 999}]
    mio["handCount"] = len(mio["hand"])
    monkeypatch.setitem(m.RETREAT_COST, OGERPON, 3)
    assert m.agent(o) != [_opt_de(o, lambda b: b["id"] == TAPU)]
