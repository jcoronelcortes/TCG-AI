"""Boss's Orders: "atacar al activo es suficiente" no vale si el chip no cobra.

Escenario (`registros/registro_020_pasos_121_hasta_122.json`, paso 122, turno 20,
PERDIDA vs Crustle -- episodio 88915875):

    NOSOTROS (5 premios)                        RIVAL (2 premios)
    activo **Meganium 160, 4 efectivas**        activo  Crustle **150**/150, 0 en.
    banca  Teal Mask Ogerpon ex 90/210, 2 ef.   banca   **Mega Kangaskhan ex 160**/300
           Chikorita 70                                 **Crustle 30**/170, 2 en.
           Teal Mask Ogerpon ex 210, 2 ef.
           Fezandipiti ex 210
           **Tapu Bulu 140, 4 efectivas**
    mano   Xerosic's ×2, Ultra Ball, Dipplin, **Boss's Orders**

El agente **atacaba con Meganium**: *Solar Beam* 140 sobre 150 PV deja al muro a
10 y **no cobra nada** -- y el rival simplemente rota el cuerpo herido a la banca
(es lo que hizo en la partida). Enfrente había dos premios servidos: el
**Mega Kangaskhan ex a 160/300** (3 premios, que *Wood Hammer* 220 noquea tras
retirar) y el **Crustle a 30 PV** (1 premio, que el propio *Solar Beam* noquea).

Causa: `_bo_active_attack_sufficient`. La regla "si el ataque al activo lo deja
por debajo de 100 PV, guarda el Boss's" ponía `values[Boss_Orders] = 0` **y**
anulaba `_boss_prize_rank`, dejando el Supporter en `sin_valor` -> VETO. Ese
borrado pisaba el **970** que el propio scoring ya le había dado por
`_bo_best_bench_prize (1) > _bo_active_prize (0)`. La regla tenía exenciones para
deny_evo / key_bench / defensivo / win_via_bench, pero no para la más básica:
**el gusteo cobra un premio que el ataque al activo no cobra**. Un chip no es un
premio.

Arreglo: `_bo_bench_prize_beats_active` -- el mismo predicado que otorga el 960+
-- exime a la regla. Y `_wall_ko_promote` (el relevo letal contra el muro, ver
`test_relevo_letal_contra_el_muro`) cede cuando el gusteo consigue el KO con el
ACTIVO: el mismo premio sin pagar la retirada.

La línea completa que sale ahora: **Boss's -> gustear al Mega Kangaskhan ex ->
retirar Meganium -> promover Tapu Bulu -> Wood Hammer 220 = KO de 3 premios**
(5 -> 2), mejor todavía que el premio del Crustle herido.

Corpus dorado: un único flip, el de este paso. Self-play: neutro en 7 matchups
(crustle 71.5% vs 71.9% con 4 corridas de n=4000 por rama; el resto a la par).
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
_ATACAR = 13
_RETIRAR = 12


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
    """Reproduce el paso previo del turno y decide en el 122."""
    m.agent(copy.deepcopy(_datos()["observation_previa_paso121"]))
    return m.agent(o)


def _opcion(o, accion):
    return o["select"]["option"][accion[0]]


def _carta_jugada(o, accion):
    opt = _opcion(o, accion)
    if opt["type"] != _PLAY:
        return None
    return o["current"]["players"][0]["hand"][opt["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. El escenario: sin él, el test no mide nada
# ---------------------------------------------------------------------------

def test_el_chip_al_activo_no_cobra_y_la_banca_tiene_dos_premios():
    o = _obs()
    mio = o["current"]["players"][0]
    riv = o["current"]["players"][1]

    act = mio["active"][0]
    assert act["id"] == MEGANIUM and len(act["energies"]) == 4

    # El activo rival aguanta el Solar Beam... por 10 PV: justo el hueco donde
    # la regla "atacar es suficiente" (remanente <= 100) se activaba.
    muro = riv["active"][0]
    assert muro["id"] == CRUSTLE and muro["hp"] == 150
    assert 0 < muro["hp"] - 140 <= 100

    # Dos premios servidos en la banca rival.
    kang = next(b for b in riv["bench"] if b["id"] == KANGASKHAN)
    crus = next(b for b in riv["bench"] if b["id"] == CRUSTLE)
    assert kang["hp"] == 160 and 220 >= kang["hp"]      # Wood Hammer lo noquea
    assert crus["hp"] == 30 and 140 >= crus["hp"]       # Solar Beam lo noquea

    # ...y el Kangaskhan vale TRES premios.
    assert m.card_table[KANGASKHAN].megaEx

    # El Supporter está libre y el Boss's en la mano.
    assert not o["current"]["supporterPlayed"]
    assert any(c["id"] == BOSS for c in mio["hand"])


# ---------------------------------------------------------------------------
# 2. La decisión
# ---------------------------------------------------------------------------

def test_juega_bosss_orders_en_vez_de_pegar_por_140():
    o = _obs()
    accion = _decidir(o)
    assert _carta_jugada(o, accion) == BOSS, (
        "con dos premios noqueables en la banca rival, gastar el turno en un "
        "chip que no cobra nada es regalar la partida")


def test_gustea_al_mega_kangaskhan_de_tres_premios():
    """El objetivo: el cuerpo de 3 premios que el relevo remata, no el de 1."""
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


def test_tras_el_gusteo_retira_y_promueve_al_rematador():
    """La otra mitad de la línea: gusteado el Kangaskhan a 160, el KO lo da Tapu
    Bulu (220) tras retirar -- Meganium (140) no llega."""
    o = _obs()
    _decidir(o)
    mio = o["current"]["players"][0]
    riv = o["current"]["players"][1]
    mio["hand"] = [c for c in mio["hand"] if c["id"] != BOSS]
    mio["handCount"] = len(mio["hand"])
    o["current"]["supporterPlayed"] = True
    # el gusteo: el Kangaskhan pasa al activo y el muro a la banca
    kang = riv["bench"].pop(next(i for i, b in enumerate(riv["bench"])
                                 if b["id"] == KANGASKHAN))
    riv["bench"].append(riv["active"][0])
    riv["active"] = [kang]
    o["select"]["option"] = [{"index": 1, "type": _PLAY},
                             {"attackId": 1028, "type": _ATACAR},
                             {"type": _RETIRAR}, {"type": 14}]
    accion = m.agent(o)
    assert _opcion(o, accion)["type"] == _RETIRAR

    # ...y el relevo que sube es Tapu Bulu.
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
# 3. Los límites de la regla
# ---------------------------------------------------------------------------

def test_sin_premio_en_la_banca_rival_el_bosss_se_guarda():
    """Control: con la banca rival SANA no hay premio que cobrar gusteando, así
    que la regla 'atacar al activo es suficiente' vuelve a mandar y el Boss's se
    conserva."""
    o = _obs()
    riv = o["current"]["players"][1]
    for b in riv["bench"]:
        b["hp"] = b["maxHp"]
    accion = _decidir(o)
    assert _carta_jugada(o, accion) != BOSS


def test_si_el_ataque_al_activo_cobra_el_mismo_premio_no_se_gasta_el_bosss():
    """Control: con el muro activo a 140 PV, Solar Beam ya lo noquea y cobra el
    mismo premio que el mejor objetivo de banca alcanzable por el activo; el
    gusteo no aporta nada y el Supporter se guarda."""
    o = _obs()
    riv = o["current"]["players"][1]
    riv["active"][0]["hp"] = 140
    accion = _decidir(o)
    assert _carta_jugada(o, accion) != BOSS
