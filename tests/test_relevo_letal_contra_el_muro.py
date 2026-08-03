"""Muro inmune a ex: si el activo NO remata y el relevo de banca SÍ, se retira.

Escenario (`registros/registro_018_pasos_112_hasta_113.json`, paso 113, turno 18,
PERDIDA vs Crustle -- episodio 88915875):

    NOSOTROS (5 premios)                        RIVAL (2 premios)
    activo **Meganium 160, 4 efectivas**        activo  **Crustle 170**/170, 1 en.
    banca  Teal Mask Ogerpon ex 90/210, 2 ef.   banca   Mega Kangaskhan ex 160/300
           Chikorita 70                                 Crustle 150
           Teal Mask Ogerpon ex 210, 2 ef.
           Fezandipiti ex 210
           **Tapu Bulu 140, 4 efectivas**
    mano   Xerosic's ×2, Ultra Ball, Forest, Dipplin

El agente **atacaba con Meganium**: *Solar Beam* hace 140 y el Crustle tiene
**170 PV** -- 150 impresos **+20 de la Grass Energy** que lleva encima, que da
+20 PV a los Pokémon Planta --, así que el muro sobrevive a 30 y el turno se
regala. En banca esperaba **Tapu Bulu ya a 4 efectivas**: *Wood Hammer* **220**
lo noquea. La retirada de Meganium cuesta 2 = **una** carta de Planta (Wild
Growth la cuenta doble), y Wild Growth sigue activo desde la banca, así que Tapu
Bulu conserva sus 4 efectivas.

Causa: `_nonex_active_hits_wall` **vetaba la retirada sin excepción** (log
86406907 paso 87). Su premisa -- "retirar al no-ex que golpea al muro solo
promovería un ex que le hace 0" -- es falsa cuando en la banca hay **otro cuerpo
no bloqueado que además remata**.

Arreglo: `_wall_ko_promote` -- con un muro (inmune a ex o a habilidad) de activo
rival, si nuestro activo NO lo remata y un cuerpo de banca no bloqueado SÍ,
retirar y rematar (score 6700, por encima del veto, que además se apaga). El daño
del relevo se mide con el Grass que quedará **después** de pagar la retirada
(misma corrección que `_hlp_grass_after`).

Corpus dorado: dos flips, ambos el mismo patrón contra el mismo muro (paso 113 y
`registro_020` paso 122, con el Crustle a 150 y Tapu Bulu a 4 efectivas).

Self-play (n=4000/rama): cornerstone_cubchoo **77.6% vs 76.0%**;
crustle_kangaskhan 70.4% vs 70.8% (ruido).
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
    m._init_cartas_tracking()
    m._cartas_first_scan_done = False
    m._cartas_prizes_identified = False
    m._cartas_last_turn = -1
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
    m._init_cartas_tracking()


def _datos():
    return json.load(open(_FIXTURE, encoding="utf-8"))


def _obs():
    return copy.deepcopy(_datos()["observation"])


def _decidir(o):
    """Reproduce el paso previo (adjunte a Tapu Bulu) y luego decide en el 113."""
    m.agent(copy.deepcopy(_datos()["observation_previa_paso112"]))
    return m.agent(o)


def _tipo_elegido(o, accion):
    return o["select"]["option"][accion[0]]["type"]


_RETIRAR = 12
_ATACAR = 13


# ---------------------------------------------------------------------------
# 1. El escenario: sin él, el test no mide nada
# ---------------------------------------------------------------------------

def test_el_muro_aguanta_al_activo_y_cae_ante_el_relevo():
    o = _obs()
    mio = o["current"]["players"][0]
    riv = o["current"]["players"][1]

    act = mio["active"][0]
    assert act["id"] == MEGANIUM and len(act["energies"]) == 4
    assert m.ATTACK_ENERGY_REQ[MEGANIUM] == 4

    # El muro: 150 impresos + 20 de la Grass Energy que lleva encima.
    muro = riv["active"][0]
    assert muro["id"] == CRUSTLE
    assert m.card_table[CRUSTLE].hp == 150 and muro["hp"] == 170
    assert len(muro["energyCards"]) == 1

    # Solar Beam (140) NO llega; Wood Hammer (220) sí.
    assert 140 < muro["hp"] <= 220

    # El relevo está listo: 4 efectivas y la retirada del activo es pagable.
    tapu = next(b for b in mio["bench"] if b["id"] == TAPU)
    assert len(tapu["energies"]) == 4 and m.ATTACK_ENERGY_REQ[TAPU] == 4
    assert len(act["energies"]) >= m.RETREAT_COST[MEGANIUM]


# ---------------------------------------------------------------------------
# 2. La decisión
# ---------------------------------------------------------------------------

def test_retira_en_vez_de_atacar_por_140():
    o = _obs()
    accion = _decidir(o)
    assert _tipo_elegido(o, accion) == _RETIRAR, (
        "atacar por 140 a un muro de 170 regala el turno teniendo el remate "
        "de Tapu Bulu en la banca")


def test_tras_retirar_promueve_a_tapu_bulu():
    """La otra mitad de la línea: al elegir el relevo sube el que remata."""
    o = _obs()
    _decidir(o)
    mio = o["current"]["players"][0]
    act = mio["active"][0]
    # Paga la retirada: coste 2 = UNA carta de Planta (Wild Growth la dobla).
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
# 3. Los límites de la regla
# ---------------------------------------------------------------------------

def test_sin_relevo_que_remate_vuelve_el_veto_y_ataca():
    """Control: sin energía en Tapu Bulu nadie remata al muro; entonces el veto
    original manda -- retirar solo promovería un ex que le hace 0 -- y Meganium
    debe atacar aunque no noquee."""
    o = _obs()
    tapu = next(b for b in o["current"]["players"][0]["bench"] if b["id"] == TAPU)
    tapu["energies"] = []
    tapu["energyCards"] = []
    accion = _decidir(o)
    assert _tipo_elegido(o, accion) == _ATACAR


def test_si_el_activo_YA_remata_no_se_retira():
    """Control: con el muro a 140 PV, Solar Beam lo noquea y el activo ataca --
    retirar pagaría energía para cobrar el mismo premio."""
    o = _obs()
    muro = o["current"]["players"][1]["active"][0]
    muro["hp"] = 140
    accion = _decidir(o)
    assert _tipo_elegido(o, accion) == _ATACAR
