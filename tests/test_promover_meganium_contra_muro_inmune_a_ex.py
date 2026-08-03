"""Promoción tras KO: el que PUEDE dañar al activo rival, aunque cargue mañana.

Escenario (`registros/registro_013_pasos_069_hasta_071.json`, paso 71, turno 13,
PERDIDA vs Crustle -- episodio 88915875). Superb Scissors noquea a nuestro
Dipplin y hay que promover:

    NOSOTROS (6 premios)                        RIVAL (3 premios)
    banca  Teal Mask Ogerpon ex 210, 2 efect.   activo  Crustle **70**/150, 3 en.
           **Meganium 160, 2 efectivas**        banca   Mega Kangaskhan ex 300
           Chikorita 70, 0 en.
           Teal Mask Ogerpon ex 210, 2 efect.
           Fezandipiti ex 210, 0 en.
    mano   Dipplin, Xerosic's, Tapu Bulu, **1 Planta**

El agente subía **Teal Mask Ogerpon ex**, que contra este activo es un cuerpo
mudo: *Mysterious Rock Inn* anula todo el daño de los Pokémon ex del rival, así
que Ogerpon ex y Fezandipiti ex pegan **0** al Crustle.

El único que lo remata es **Meganium** (no-ex): lleva 1 Planta = **2 efectivas**
(su propio Wild Growth) y queda otra Planta en la mano -> el próximo turno
adjunta (2+2 = **4**) y *Solar Beam* hace **140** sobre un Crustle a **70 PV**.

Causa -- dos medidas de "listo para atacar" que miran el turno equivocado. La
promoción forzada ocurre en el turno RIVAL: el cuerpo que sube **no ataca hoy**,
ataca MAÑANA. `_best_promote_card` ya lo hacía bien (contempla el adjunte del
próximo turno, la inmunidad a ex, la de habilidad y la debilidad) y elegía
Meganium... pero dos reglas del bucle de opciones lo tumbaban:

1. El veto "la línea Meganium no va al activo" (`SCORE_NEVER` = -10000, protege
   el motor Wild Growth desde la banca) solo se levantaba con `len(energies) >=
   4`, es decir, energía de HOY. Meganium a 2/4 lo comía entero: -10000 + 150 +
   4000 del bono de mejor promovible = **-5850**.
2. La rama de activo inmune a ex daba su +6000 al "atacante no-ex" medido con
   `_can_attack_now`; sin él, el Ogerpon ex cobraba el +3000 de *muro con
   energía* y ganaba la plaza con **3343**.

Arreglo: en promoción FORZADA (`_forced_ko_promote`) ambas medidas pasan al
próximo turno -- el veto de la línea Meganium cede cuando el selector consciente
del KO señala a ese cuerpo (`card is _best_promote_card`), y el atacante no-ex
contra el muro inmune se reconoce con `_can_attack_with_attach`. Deck-agnóstico:
vale para cualquier activo que inmunice a nuestros ex (Crustle / Sylveon).

Corpus dorado: un único flip, el de este paso.
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
            / "crustle_promover_meganium_step71.json")

MEGANIUM = m.Meganium
OGERPON = m.Teal_Mask_Ogerpon_ex
FEZ = m.Fezandipiti_ex
CHIKORITA = m.Chikorita
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


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _banca(obs):
    yo = obs["current"]["yourIndex"]
    return obs["current"]["players"][yo]["bench"]


def _opt_de(obs, pred):
    banca = _banca(obs)
    return next(i for i, o in enumerate(obs["select"]["option"])
                if pred(banca[o["index"]]))


def _promovido(obs, accion):
    return _banca(obs)[obs["select"]["option"][accion[0]]["index"]]


# ---------------------------------------------------------------------------
# 1. El escenario: sin él, el test no mide nada
# ---------------------------------------------------------------------------

def test_el_fixture_es_la_promocion_forzada_con_el_crustle_a_rematar():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]

    # Promoción forzada: nos quedamos sin activo.
    assert not mio["active"]
    assert o["select"]["context"] == 4

    # El activo rival es el muro inmune a ex, y está a UN golpe.
    act = riv["active"][0]
    assert act["id"] == CRUSTLE and act["hp"] == 70

    # Meganium: 2 efectivas (1 Planta x Wild Growth) de las 4 que pide Solar Beam.
    meg = next(b for b in mio["bench"] if b["id"] == MEGANIUM)
    assert len(meg["energyCards"]) == 1 and len(meg["energies"]) == 2
    assert m.ATTACK_ENERGY_REQ[MEGANIUM] == 4

    # ...y la Planta que le falta está en la mano: mañana llega a 4 y hace 140.
    assert sum(1 for c in mio["hand"] if c["id"] == m.Basic_Grass_Energy) >= 1

    # Los ex de la banca son cuerpos MUDOS contra este activo.
    assert any(b["id"] == OGERPON for b in mio["bench"])
    assert any(b["id"] == FEZ for b in mio["bench"])


def test_la_habilidad_del_crustle_anula_el_dano_de_nuestros_ex():
    """Por qué subir un ex regala el turno: Mysterious Rock Inn."""
    o = _obs()
    m.agent(_obs())  # deja el estado global sincronizado con el tablero
    assert OGERPON in m.OUR_EX_IDS and FEZ in m.OUR_EX_IDS
    assert CRUSTLE in m.EX_IMMUNE_IDS


# ---------------------------------------------------------------------------
# 2. La decisión
# ---------------------------------------------------------------------------

def test_promueve_meganium_y_no_el_ex_mudo():
    o = _obs()
    accion = m.agent(_obs())
    pk = _promovido(o, accion)
    assert pk["id"] == MEGANIUM, (
        "contra un activo que inmuniza a nuestros ex hay que subir al no-ex que "
        "SI puede rematar el proximo turno, no un ex que hace 0")


def test_no_sube_ni_ogerpon_ni_fezandipiti_ni_chikorita():
    o = _obs()
    accion = m.agent(_obs())
    assert accion != [_opt_de(o, lambda b: b["id"] == OGERPON)]
    assert accion != [_opt_de(o, lambda b: b["id"] == FEZ)]
    # Chikorita puede atacar mañana (Seed Bomb, 2 efectivas) pero por 30: no remata.
    assert accion != [_opt_de(o, lambda b: b["id"] == CHIKORITA)]


# ---------------------------------------------------------------------------
# 3. Los límites de la regla
# ---------------------------------------------------------------------------

def test_sin_la_planta_en_mano_meganium_no_llega_y_no_se_fuerza():
    """Control: quitada la Planta de la mano, Meganium se queda en 2/4 -- no
    ataca ni mañana --, así que el veto de la línea Meganium vuelve a mandar y
    la promoción no lo elige."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    mio["hand"] = [c for c in mio["hand"] if c["id"] != m.Basic_Grass_Energy]
    mio["handCount"] = len(mio["hand"])
    accion = m.agent(o)
    assert _promovido(o, accion)["id"] != MEGANIUM


def test_sin_el_muro_inmune_delante_la_promocion_no_cambia_de_criterio():
    """Control: con el Mega Kangaskhan ex de activo (no inmuniza a nuestros ex)
    el bono de atacante no-ex ni siquiera aplica; la promoción vuelve a la
    lógica general y no se ve arrastrada por este arreglo."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    riv = o["current"]["players"][1 - yo]
    riv["active"], riv["bench"] = riv["bench"], riv["active"]
    accion = m.agent(o)
    assert _promovido(o, accion)["id"] != CHIKORITA
