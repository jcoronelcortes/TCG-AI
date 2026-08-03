"""Promoción tras KO: no subir un muro CLAVADO teniendo el casi-atacante móvil.

Escenario (`registros/registro_008_pasos_110_hasta_122.json`, paso 122, turno 8,
PERDIDA vs Dragapult -- episodio 88912610). El Dragapult ex acaba de noquear a
nuestro Hydrapple ex con Phantom Dive y hay que promover:

    NOSOTROS (4 premios)                       RIVAL (4 premios)
    banca  Teal Mask Ogerpon ex 100/210, 2 en. activo  Dragapult ex **50**/320, 2 en.
           Meganium 160, 0 en.                 banca   Fezandipiti ex 210,
           Teal Mask Ogerpon ex **200**/210, 2 en.     Dragapult ex 320, Drakloak 90
           Teal Mask Ogerpon ex 200/210, 2 en.
           Tapu Bulu 140, **0 energías**       estadio Team Rocket's Watchtower
    mano   Ogerpon ex, Ultra Ball, **Fezandipiti ex**, Dipplin, Meganium,
           Hydrapple ex, Tapu Bulu   (ni una Planta)

El agente subía **Tapu Bulu**: 0 de 4 energías —no ataca— y **retirada 3** que no
puede pagar —no se puede cambiar—. Es un cuerpo CLAVADO: regala el turno entero y
encima cede un premio. Enfrente, el Dragapult ex está a **50 PV**: un Ogerpon ex
con una energía más hace *Myriad Leaf Shower* 30 + 30·(4+2) = **210** y cobra 2
premios.

Causa: `_promote_setup_ko_attacker` (subir al atacante que está a UNA adjunción de
rematar) exige poder conseguir esa energía, y su lista de vías —Lillie's/Dawn en
mano, Lana's Aid, motor Meowth ex— **no incluía Flip the Script**. Aquí las tres
fallaban (mano sin Supporters; el motor Meowth además está muerto: Team Rocket's
Watchtower anula las habilidades de los Pokémon {C}). Sin vía, el override no
disparaba y mandaba `_ko_prefer_basic_general`, que elige el muro de 1 premio por
VIDA (8500 + 140/10) sin mirar si ese muro puede hacer algo.

Arreglo, en dos mitades que se sostienen la una a la otra:

1. **Ruta (d): Fezandipiti ex → Flip the Script (roba 3).** Es la vía que
   faltaba, y la única cuyo disparador está *garantizado* en esta rama: estamos
   promoviendo porque nos acaban de noquear, que es exactamente lo que enciende
   Flip the Script. Watchtower no la apaga (solo mata habilidades {C}; Fezandipiti
   ex es {D}); quien sí la mata es Iron Thorns, que anula toda habilidad con Rule
   Box. Vale con el Fezandipiti ya en juego o en la mano con hueco de banca.

2. **`_ps_conserva_salida`: la ruta (d) exige que el promovido pueda RETIRARSE**
   con la energía que ya lleva. Robar 3 no *busca* la Planta, así que el plan
   puede fallar — y por eso solo se acepta cuando sigue siendo reversible: si la
   Planta no aparece, el turno siguiente se retira el Ogerpon (coste 1, lleva 2)
   y **entonces** sube el muro. *El sacrificio es una decisión diferible;
   quedarse clavado no.* Con las vías de BÚSQUEDA (a/b/c) la energía está
   prácticamente asegurada y no se pide movilidad.

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
            / "dragapult_promover_ogerpon_no_tapu_step122.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu
FEZ = m.Fezandipiti_ex
DRAGAPULT = m.Dragapult_ex


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


# ---------------------------------------------------------------------------
# 1. El escenario: sin él, el test no mide nada
# ---------------------------------------------------------------------------

def test_el_fixture_es_la_promocion_forzada_tras_el_ko():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]

    # Promoción forzada: no tenemos activo.
    assert not mio["active"]
    assert o["select"]["context"] == 4

    # El muro que se subía está CLAVADO: 0 energías y retirada 3.
    tapu = next(b for b in mio["bench"] if b["id"] == TAPU)
    assert len(tapu["energies"]) == 0
    assert m.RETREAT_COST[TAPU] == 3
    assert m.ATTACK_ENERGY_REQ[TAPU] == 4

    # El casi-atacante SÍ conserva la salida: retirada 1 y lleva 2 energías.
    oger = [b for b in mio["bench"] if b["id"] == OGERPON]
    assert len(oger) == 3 and all(len(b["energies"]) == 2 for b in oger)
    assert m.RETREAT_COST[OGERPON] == 1
    assert max(b["hp"] for b in oger) == 200

    # A UNA adjunción de rematar: Myriad = 30 + 30·(4 + 2) = 210 >= 50.
    act = riv["active"][0]
    assert act["id"] == DRAGAPULT and act["hp"] == 50
    assert 30 + 30 * (4 + len(act["energies"])) >= act["hp"]

    # El motor que lo hace posible está en la MANO, y ningún Supporter lo está.
    assert any(c["id"] == FEZ for c in mio["hand"])
    for _supp in (m.Lillie_Determination, m.Dawn, m.Lanas_Aid, m.Meowth_ex):
        assert not any(c["id"] == _supp for c in mio["hand"])
    # Y no hay ni una Planta en mano: la energía hay que robarla.
    assert not any(c["id"] == m.Basic_Grass_Energy for c in mio["hand"])

    # El registro confirma que ahí se subió el Tapu Bulu.
    assert json.load(open(_FIXTURE, encoding="utf-8"))["accion_registrada"] == [4]


def test_watchtower_mata_el_motor_meowth_pero_no_el_de_fezandipiti():
    """Por qué las vías viejas fallaban y la nueva no: Watchtower solo anula
    las habilidades de los Pokémon {C} (Meowth ex), no las de Fezandipiti ex."""
    o = _obs()
    assert o["current"]["stadium"][0]["id"] == m.Team_Rockets_Watchtower
    assert m.card_table[m.Meowth_ex].energyType != m.card_table[FEZ].energyType


# ---------------------------------------------------------------------------
# 2. La decisión
# ---------------------------------------------------------------------------

def test_promueve_el_ogerpon_cargado_y_no_el_tapu_clavado():
    o = _obs()
    tapu_opt = _opt_de(o, lambda b: b["id"] == TAPU)
    assert m.agent(_obs()) != [tapu_opt], (
        "Tapu Bulu a 0/4 con retirada 3 no ataca ni se puede cambiar: "
        "regala el turno entero")


def test_promueve_el_ogerpon_con_MAS_vida():
    """Entre los tres Ogerpon ex a la misma distancia del remate, sube el de
    200 PV, no el de 100: el desempate por vida ya vive en `_ps_key`."""
    o = _obs()
    elegido = m.agent(_obs())[0]
    banca = _banca(o)
    pk = banca[o["select"]["option"][elegido]["index"]]
    assert pk["id"] == OGERPON and pk["hp"] == 200


# ---------------------------------------------------------------------------
# 3. Los límites de la regla
# ---------------------------------------------------------------------------

def test_sin_fezandipiti_no_hay_motor_y_vuelve_el_muro():
    """Control: quitado el Fezandipiti ex de la mano no queda ninguna vía para
    conseguir la Planta, y la promoción vuelve a la lógica de muro barato."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    mio["hand"] = [c for c in mio["hand"] if c["id"] != FEZ]
    mio["handCount"] = len(mio["hand"])
    assert m.agent(o) == [_opt_de(o, lambda b: b["id"] == TAPU)]


def test_sin_planta_alcanzable_no_hay_motor():
    """Control: con TODAS las Plantas ya visibles (mano vacía de ellas +
    descarte) no queda ninguna oculta que robar, y el motor no dispara."""
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
    """`_ps_conserva_salida` aislado: mismo tablero, misma distancia al remate,
    pero con la retirada del Ogerpon ex encarecida a 3 (no la puede pagar con
    sus 2 energías). El plan deja de ser reversible -si el robo falla nos
    quedamos clavados igual- y el robo a ciegas ya no basta: vuelve el muro."""
    o = _obs()
    monkeypatch.setitem(m.RETREAT_COST, OGERPON, 3)
    assert m.agent(o) == [_opt_de(o, lambda b: b["id"] == TAPU)]


def test_con_supporter_de_busqueda_no_se_exige_movilidad(monkeypatch):
    """Contraparte: con una Lillie's en mano (vía de BÚSQUEDA, no de robo a
    ciegas) la energía está prácticamente asegurada, así que la movilidad deja
    de ser condición y el Ogerpon ex sube aunque su retirada sea impagable."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    mio["hand"] = mio["hand"] + [{"id": m.Lillie_Determination,
                                  "playerIndex": yo, "serial": 999}]
    mio["handCount"] = len(mio["hand"])
    monkeypatch.setitem(m.RETREAT_COST, OGERPON, 3)
    assert m.agent(o) != [_opt_de(o, lambda b: b["id"] == TAPU)]
