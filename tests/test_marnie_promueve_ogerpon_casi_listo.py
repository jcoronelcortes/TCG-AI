"""Promoción tras KO: el motor de la MANO cuenta como vía de energía.

Escenario (`registros/registro_007_pasos_101_hasta_127.json`, paso 126, turno 7,
PERDIDA vs Marnie's Grimmsnarl ex):

    NOSOTROS (3 premios)                     RIVAL (5 premios)
    activo  -- (nos acaban de noquear        activo  Marnie's Grimmsnarl ex
            el Hydrapple ex)                         310/320, 3 energías,
    banca   Ogerpon ex 2/3 energías                  **debilidad {G}**
            Ogerpon ex 2/3 energías
            Ogerpon ex 0/3
            Tapu Bulu 1/4, 80 PV
    mano    Meowth ex + Meganium
    descarte  1 Energía Planta

La promoción se resuelve al FINAL del turno rival: el siguiente turno es NUESTRO
y el cuerpo que subamos ataca PRIMERO. Un Ogerpon ex a 2/3 está a **una sola**
energía de *Myriad Leaf Shower* — 30+30·(3 propias + 3 del rival) = 210, ×2 por
debilidad a Planta = **420 ≥ 310**: remata al Grimmsnarl ex y cobra 2 premios
(3 → 1). Y esa energía es alcanzable: bajar **Meowth ex** dispara *Last-Ditch
Catch*, que trae del mazo **Lana's Aid** (levanta la Planta del descarte) o
Lillie's/Dawn.

El agente subía el **Tapu Bulu** a 1/4: no puede atacar (*Wood Hammer* cuesta 4),
no puede retirarse (coste 3 sin energía para pagarlo) y regala el turno.

Dos causas encadenadas:

1. `_promote_setup_ko_attacker` (promover al atacante casi listo) exigía un
   Supporter de robo **ya en la mano** (`Lillie's`/`Dawn`). Una mano que solo
   tiene el MOTOR que consigue ese Supporter — Meowth ex — quedaba fuera. Se
   enumeran ahora todas las vías reales: Supporter de robo en mano, Lana's Aid
   en mano con Planta en el descarte, y el motor Meowth ex (hueco en banca +
   habilidad viva + Supporter útil aún oculto en mazo/premios).

2. Aun disparando, el ajuste TERMINAL de promoción le restaba
   `PROMO_PRIZE_PENALTY` por ser un ex de 2 premios (9500 → 8000) y lo dejaba
   por debajo del muro básico de `_ko_prefer_basic_general` (8500 + vida/10 =
   8508). La premisa de esa penalización — "no sobrevive nadie, cede los menos
   premios" — **no aplica** a un cuerpo que remata primero: el rival no llega a
   golpearlo. Se exime, igual que ya se exime al que noquea en el acto.

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
            / "marnie_promote_ogerpon_setup_ko_step126.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu
MEOWTH = m.Meowth_ex
GRIMMSNARL = 648                # Marnie's Grimmsnarl ex, 320 PV, debilidad {G}


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


def _obs(**mut):
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    if mut.get("sin_meowth"):
        mio["hand"] = [c for c in mio["hand"] if c["id"] != MEOWTH]
        mio["handCount"] = len(mio["hand"])
    if mut.get("sin_supporter_alcanzable"):
        # El fetch del Meowth ex no puede traer nada util: la ultima Lillie's y
        # la Dawn ya estan en el descarte y no queda Planta que levantar con
        # Lana's Aid.
        mio["discard"] = [c for c in mio["discard"]
                          if c["id"] != m.Basic_Grass_Energy]
        for cid in (m.Lillie_Determination, m.Dawn):
            mio["discard"].append({"id": cid, "playerIndex": yo, "serial": 999})
    return o


def _elegido(obs, eleccion):
    """Carta de banca que corresponde a la opción elegida."""
    yo = obs["current"]["yourIndex"]
    opt = obs["select"]["option"][eleccion[0]]
    return obs["current"]["players"][yo]["bench"][opt["index"]]


# ---------------------------------------------------------------------------
# 1. El escenario: sin él, el test no mide nada
# ---------------------------------------------------------------------------

def test_el_fixture_es_la_promocion_tras_el_ko():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    rival = o["current"]["players"][1 - yo]

    assert not mio["active"]                       # nos noquearon el activo
    assert o["select"]["context"] == 4             # menu de promocion
    assert rival["active"][0]["id"] == GRIMMSNARL
    assert rival["active"][0]["hp"] == 310

    # Debilidad a Planta: el Ogerpon ex pega doble.
    assert m.card_table[GRIMMSNARL].weakness == m.card_table[OGERPON].energyType

    # Ogerpon ex a UNA energia de Myriad; Tapu Bulu a tres de Wood Hammer.
    oger = [b for b in mio["bench"] if b["id"] == OGERPON and len(b["energies"]) == 2]
    tapu = next(b for b in mio["bench"] if b["id"] == TAPU)
    assert oger, "el fixture debe tener un Ogerpon ex a 2/3"
    assert m.ATTACK_ENERGY_REQ[OGERPON] - 2 == 1
    assert m.ATTACK_ENERGY_REQ[TAPU] - len(tapu["energies"]) == 3
    # ...y ademas el Tapu quedaria clavado: retirada 3 sin energia para pagarla.
    assert m.RETREAT_COST[TAPU] > len(tapu["energies"])

    # El motor de la mano: Meowth ex + Planta en el descarte.
    assert any(c["id"] == MEOWTH for c in mio["hand"])
    assert sum(1 for c in mio["discard"]
               if c["id"] == m.Basic_Grass_Energy) >= 1
    # Ningun Supporter de robo en mano: la regla vieja no disparaba.
    assert not any(c["id"] in (m.Lillie_Determination, m.Dawn)
                   for c in mio["hand"])


def test_el_ogerpon_completado_remata_al_grimmsnarl():
    """El premio de la jugada: 30+30*(3+3) = 210, x2 debilidad = 420 >= 310."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    rival_act = o["current"]["players"][1 - yo]["active"][0]
    base = 30 + 30 * (m.ATTACK_ENERGY_REQ[OGERPON] + len(rival_act["energies"]))
    assert base * 2 >= rival_act["hp"]


# ---------------------------------------------------------------------------
# 2. La decision
# ---------------------------------------------------------------------------

def test_promueve_el_ogerpon_casi_listo_y_no_el_tapu_clavado():
    obs = _obs()
    elegido = _elegido(obs, m.agent(obs))
    assert elegido["id"] == OGERPON
    assert len(elegido["energies"]) == 2       # el que esta a UNA energia


# ---------------------------------------------------------------------------
# 3. Los limites: sin motor de energia, el muro barato sigue siendo correcto
# ---------------------------------------------------------------------------

def test_sin_meowth_no_hay_via_de_energia_y_vuelve_el_muro_de_1_premio():
    obs = _obs(sin_meowth=True)
    assert _elegido(obs, m.agent(obs))["id"] == TAPU


def test_sin_supporter_util_que_buscar_el_meowth_no_es_motor():
    obs = _obs(sin_supporter_alcanzable=True)
    assert _elegido(obs, m.agent(obs))["id"] == TAPU
