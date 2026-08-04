"""Boss's Orders: "attacking the active is enough" does not hold if the chip takes nothing.

Scenario (`records/registro_020_pasos_121_hasta_122.json`, step 122, turn 20,
LOST vs Crustle -- episode 88915875):

    US (5 prizes)                               RIVAL (2 prizes)
    active **Meganium 160, 4 effective**        active  Crustle **150**/150, 0 en.
    bench  Teal Mask Ogerpon ex 90/210, 2 eff.  bench   **Mega Kangaskhan ex 160**/300
           Chikorita 70                                 **Crustle 30**/170, 2 en.
           Teal Mask Ogerpon ex 210, 2 eff.
           Fezandipiti ex 210
           **Tapu Bulu 140, 4 effective**
    hand   Xerosic's ×2, Ultra Ball, Dipplin, **Boss's Orders**

The agent **attacked with Meganium**: *Solar Beam* 140 on 150 HP leaves the wall at
10 and **takes nothing** -- and the rival simply rotates the wounded body to the bench
(which is what they did in the game). Across the table there were two prizes on a plate: the
**Mega Kangaskhan ex at 160/300** (3 prizes, which *Wood Hammer* 220 knocks out after
retreating) and the **Crustle at 30 HP** (1 prize, which *Solar Beam* itself knocks out).

Cause: `_bo_active_attack_sufficient`. The rule "if the attack on the active leaves it
below 100 HP, keep the Boss's" set `values[Boss_Orders] = 0` **and**
cancelled `_boss_prize_rank`, leaving the Supporter at `sin_valor` -> VETO. That
erasure overrode the **970** the scoring itself had already given it through
`_bo_best_bench_prize (1) > _bo_active_prize (0)`. The rule had exceptions for
deny_evo / key_bench / defensive / win_via_bench, but not for the most basic one:
**the gust takes a prize that the attack on the active does not take**. A chip is not a
prize.

Fix: `_bo_bench_prize_beats_active` -- the same predicate that grants the 960+
-- exempts it from the rule. And `_wall_ko_promote` (the lethal relief against the wall, see
`test_relevo_letal_contra_el_muro`) yields when the gust gets the KO with the
ACTIVE: the same prize without paying the retreat.

The full line that now comes out: **Boss's -> gust the Mega Kangaskhan ex ->
retreat Meganium -> promote Tapu Bulu -> Wood Hammer 220 = a 3-prize KO**
(5 -> 2), better still than the wounded Crustle's prize.

Golden corpus: a single flip, this step's. Self-play: neutral across 7 matchups
(crustle 71.5% vs 71.9% with 4 runs of n=4000 per branch; the rest level).
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
            / "crustle_boss_gustea_kangaskhan_step122.json")

MEGANIUM = m.Meganium
TAPU = m.Tapu_Bulu
CRUSTLE = m.Crustle_Grass
KANGASKHAN = m.Mega_Kangaskhan_ex
BOSS = m.Boss_Orders

_PLAY = 7
_ATTACK = 13
_RETREAT = 12


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


def _data():
    return json.load(open(_FIXTURE, encoding="utf-8"))


def _obs():
    return copy.deepcopy(_data()["observation"])


def _decidir(o):
    """Replays the turn's previous step and decides on 122."""
    m.agent(copy.deepcopy(_data()["observation_previa_paso121"]))
    return m.agent(o)


def _opcion(o, accion):
    return o["select"]["option"][accion[0]]


def _played_card(o, accion):
    opt = _opcion(o, accion)
    if opt["type"] != _PLAY:
        return None
    return o["current"]["players"][0]["hand"][opt["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_chip_takes_nothing_and_the_bench_holds_two_prizes():
    o = _obs()
    mio = o["current"]["players"][0]
    riv = o["current"]["players"][1]

    act = mio["active"][0]
    assert act["id"] == MEGANIUM and len(act["energies"]) == 4

    # The rival active survives the Solar Beam... by 10 HP: exactly the gap where
    # the rule "attacking is enough" (remainder <= 100) switched on.
    wall = riv["active"][0]
    assert wall["id"] == CRUSTLE and wall["hp"] == 150
    assert 0 < wall["hp"] - 140 <= 100

    # Two prizes on a plate on the rival bench.
    kang = next(b for b in riv["bench"] if b["id"] == KANGASKHAN)
    crus = next(b for b in riv["bench"] if b["id"] == CRUSTLE)
    assert kang["hp"] == 160 and 220 >= kang["hp"]      # Wood Hammer knocks it out
    assert crus["hp"] == 30 and 140 >= crus["hp"]       # Solar Beam knocks it out

    # ...and the Kangaskhan is worth THREE prizes.
    assert m.card_table[KANGASKHAN].megaEx

    # The Supporter slot is free and the Boss's is in hand.
    assert not o["current"]["supporterPlayed"]
    assert any(c["id"] == BOSS for c in mio["hand"])


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_plays_bosss_orders_instead_of_hitting_for_140():
    o = _obs()
    accion = _decidir(o)
    assert _played_card(o, accion) == BOSS, (
        "con dos premios noqueables en la banca rival, gastar el turno en un "
        "chip que no cobra nada es regalar la partida")


def test_gusts_the_three_prize_mega_kangaskhan():
    """The target: the 3-prize body the relief finishes off, not the 1-prize one."""
    o = _obs()
    _decidir(o)
    mio = o["current"]["players"][0]
    riv = o["current"]["players"][1]
    mio["hand"] = [c for c in mio["hand"] if c["id"] != BOSS]
    mio["handCount"] = len(mio["hand"])
    o["current"]["supporterPlayed"] = True
    o["select"] = {
        "context": int(m.SelectContext.TO_ACTIVE), "contextCard": None, "deck": None,
        "effect": None, "maxCount": 1, "minCount": 1,
        "option": [{"area": 5, "index": i, "playerIndex": 1, "type": 3}
                   for i in range(len(riv["bench"]))],
        "remainDamageCounter": 0, "remainEnergyCost": 0, "type": 1,
    }
    accion = m.agent(o)
    assert riv["bench"][_opcion(o, accion)["index"]]["id"] == KANGASKHAN


def test_after_the_gust_it_retreats_and_promotes_the_finisher():
    """The other half of the line: with the Kangaskhan gusted at 160, the KO comes from Tapu
    Bulu (220) after retreating -- Meganium (140) does not get there."""
    o = _obs()
    _decidir(o)
    mio = o["current"]["players"][0]
    riv = o["current"]["players"][1]
    mio["hand"] = [c for c in mio["hand"] if c["id"] != BOSS]
    mio["handCount"] = len(mio["hand"])
    o["current"]["supporterPlayed"] = True
    # the gust: the Kangaskhan goes to the active spot and the wall to the bench
    kang = riv["bench"].pop(next(i for i, b in enumerate(riv["bench"])
                                 if b["id"] == KANGASKHAN))
    riv["bench"].append(riv["active"][0])
    riv["active"] = [kang]
    o["select"]["option"] = [{"index": 1, "type": _PLAY},
                             {"attackId": 1028, "type": _ATTACK},
                             {"type": _RETREAT}, {"type": 14}]
    accion = m.agent(o)
    assert _opcion(o, accion)["type"] == _RETREAT

    # ...and the relief that comes up is Tapu Bulu.
    act = mio["active"][0]
    act["energyCards"] = act["energyCards"][:1]
    act["energies"] = [1, 1]
    o["current"]["retreated"] = True
    o["select"] = {
        "context": int(m.SelectContext.SWITCH), "contextCard": None, "deck": None,
        "effect": None, "maxCount": 1, "minCount": 1,
        "option": [{"area": 5, "index": i, "playerIndex": 0, "type": 3}
                   for i in range(len(mio["bench"]))],
        "remainDamageCounter": 0, "remainEnergyCost": 0, "type": 1,
    }
    accion = m.agent(o)
    assert mio["bench"][_opcion(o, accion)["index"]]["id"] == TAPU


# ---------------------------------------------------------------------------
# 3. The limits of the rule
# ---------------------------------------------------------------------------

def test_with_no_prize_on_the_opponent_bench_the_bosss_is_kept():
    """Control: with the rival bench HEALTHY there is no prize to take by gusting, so
    the rule 'attacking the active is enough' rules again and the Boss's is
    kept."""
    o = _obs()
    riv = o["current"]["players"][1]
    for b in riv["bench"]:
        b["hp"] = b["maxHp"]
    accion = _decidir(o)
    assert _played_card(o, accion) != BOSS


def test_if_attacking_the_active_takes_the_same_prize_the_bosss_is_kept():
    """Control: with the wall active at 140 HP, Solar Beam already knocks it out and takes the
    same prize as the best bench target reachable by the active; the
    gust adds nothing and the Supporter is kept."""
    o = _obs()
    riv = o["current"]["players"][1]
    riv["active"][0]["hp"] = 140
    accion = _decidir(o)
    assert _played_card(o, accion) != BOSS
