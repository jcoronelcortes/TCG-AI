"""An ex-immune wall: if the active does NOT finish it and the bench relief DOES, we retreat.

Scenario (`registros/registro_018_pasos_112_hasta_113.json`, step 113, turn 18,
LOST vs Crustle -- episode 88915875):

    US (5 prizes)                               RIVAL (2 prizes)
    active **Meganium 160, 4 effective**        active  **Crustle 170**/170, 1 en.
    bench  Teal Mask Ogerpon ex 90/210, 2 eff.  bench   Mega Kangaskhan ex 160/300
           Chikorita 70                                 Crustle 150
           Teal Mask Ogerpon ex 210, 2 eff.
           Fezandipiti ex 210
           **Tapu Bulu 140, 4 effective**
    hand   Xerosic's ×2, Ultra Ball, Forest, Dipplin

The agent **attacked with Meganium**: *Solar Beam* does 140 and the Crustle has
**170 HP** -- 150 printed **+20 from the Grass Energy** it carries, which gives
+20 HP to Grass Pokémon --, so the wall survives on 30 and the turn is
given away. On the bench **Tapu Bulu was waiting already at 4 effective**: *Wood Hammer* **220**
knocks it out. Meganium's retreat costs 2 = **one** Grass card (Wild
Growth counts it double), and Wild Growth is still active from the bench, so Tapu
Bulu keeps its 4 effective.

Cause: `_nonex_active_hits_wall` **vetoed the retreat without exception** (log
86406907 step 87). Its premise -- "retreating the non-ex that hits the wall would only
promote an ex that does 0 to it" -- is false when on the bench there is **another
unblocked body that also finishes it off**.

Fix: `_wall_ko_promote` -- with a wall (immune to ex or to abilities) as the rival
active, if our active does NOT finish it and an unblocked bench body DOES,
retreat and finish (score 6700, above the veto, which also switches off). The
relief's damage is measured with the Grass that will be left **after** paying the retreat
(the same correction as `_hlp_grass_after`).

Golden corpus: two flips, both the same pattern against the same wall (step 113 and
`registro_020` step 122, with the Crustle at 150 and Tapu Bulu at 4 effective).

Self-play (n=4000/branch): cornerstone_cubchoo **77.6% vs 76.0%**;
crustle_kangaskhan 70.4% vs 70.8% (noise).
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
            / "crustle_retirar_meganium_para_tapu_step113.json")

MEGANIUM = m.Meganium
TAPU = m.Tapu_Bulu
CRUSTLE = m.Crustle_Grass


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
    """Replays the previous step (an attachment to Tapu Bulu) and then decides on 113."""
    m.agent(copy.deepcopy(_data()["observation_previa_paso112"]))
    return m.agent(o)


def _tipo_elegido(o, accion):
    return o["select"]["option"][accion[0]]["type"]


_RETREAT = 12
_ATTACK = 13


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_el_muro_aguanta_al_activo_y_cae_ante_el_relevo():
    o = _obs()
    mio = o["current"]["players"][0]
    riv = o["current"]["players"][1]

    act = mio["active"][0]
    assert act["id"] == MEGANIUM and len(act["energies"]) == 4
    assert m.ATTACK_ENERGY_REQ[MEGANIUM] == 4

    # The wall: 150 printed + 20 from the Grass Energy it carries.
    wall = riv["active"][0]
    assert wall["id"] == CRUSTLE
    assert m.card_table[CRUSTLE].hp == 150 and wall["hp"] == 170
    assert len(wall["energyCards"]) == 1

    # Solar Beam (140) does NOT get there; Wood Hammer (220) does.
    assert 140 < wall["hp"] <= 220

    # The relief is ready: 4 effective and the active's retreat is payable.
    tapu = next(b for b in mio["bench"] if b["id"] == TAPU)
    assert len(tapu["energies"]) == 4 and m.ATTACK_ENERGY_REQ[TAPU] == 4
    assert len(act["energies"]) >= m.RETREAT_COST[MEGANIUM]


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_retira_en_vez_de_atacar_por_140():
    o = _obs()
    accion = _decidir(o)
    assert _tipo_elegido(o, accion) == _RETREAT, (
        "atacar por 140 a un muro de 170 regala el turno teniendo el remate "
        "de Tapu Bulu en la banca")


def test_tras_retirar_promueve_a_tapu_bulu():
    """The other half of the line: when picking the relief, the one that finishes comes up."""
    o = _obs()
    _decidir(o)
    mio = o["current"]["players"][0]
    act = mio["active"][0]
    # It pays the retreat: cost 2 = ONE Grass card (Wild Growth doubles it).
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
    assert mio["bench"][o["select"]["option"][accion[0]]["index"]]["id"] == TAPU


# ---------------------------------------------------------------------------
# 3. The limits of the rule
# ---------------------------------------------------------------------------

def test_sin_relevo_que_remate_vuelve_el_veto_y_ataca():
    """Control: with no energy on Tapu Bulu nobody finishes the wall; then the original
    veto rules -- retreating would only promote an ex that does 0 to it -- and Meganium
    must attack even if it does not knock out."""
    o = _obs()
    tapu = next(b for b in o["current"]["players"][0]["bench"] if b["id"] == TAPU)
    tapu["energies"] = []
    tapu["energyCards"] = []
    accion = _decidir(o)
    assert _tipo_elegido(o, accion) == _ATTACK


def test_si_el_activo_YA_remata_no_se_retira():
    """Control: with the wall at 140 HP, Solar Beam knocks it out and the active attacks --
    retreating would pay energy to take the same prize."""
    o = _obs()
    wall = o["current"]["players"][1]["active"][0]
    wall["hp"] = 140
    accion = _decidir(o)
    assert _tipo_elegido(o, accion) == _ATTACK
