"""El que AGUANTA va delante: no retirar un ex sano por otro ex a 50 PV.

Escenario (`registros/registro_012_pasos_163_hasta_180.json`, paso 174, turno 12,
PERDIDA vs Alakazam -- episodio 88906640):

    NOSOTROS (2 premios)                     RIVAL (2 premios)
    activo  Teal Mask Ogerpon ex             activo  Alakazam 140/140, 1 energía
            **210/210**, 4 energías                  (Powerful Hand: 20 × mano)
    banca   Teal Mask Ogerpon ex **50/210**, 4 en.   banca  Fezandipiti ex (0 en.),
            Meganium 160, Fezandipiti ex,                   Kadabra, Dunsparce ×2
            Meowth ex, Hydrapple ex 330

El agente **retiraba el Ogerpon de 210** (pagando una energía) para promover el de
**50 PV**, y atacaba con ése. El KO era idéntico -- *Myriad Leaf Shower* cuenta la
energía de AMBOS activos: 30 + 30·(4+1) = 180 ≥ 140 -- así que el cambio no ganaba
nada y dejaba delante un cuerpo que muere a cualquier cosa, con los mismos 2
premios en juego.

Causa: el **FALLBACK EX** de `_prize_denial_pivot`. Ese fallback busca un ex de
banca que (a) NOQUEE al activo rival y (b) SOBREVIVA al mejor golpe proyectado de
la banca rival, y elige por MARGEN de vida. Cumplía las dos: 180 ≥ 140, y 50 PV >
30 (Kadabra) → margen 20. Pero **comparaba candidatos entre sí y nunca contra el
ACTIVO**, que hacía el mismo KO con margen 210 − 30 = **180**.

Arreglo: `_pdx_act_margin`. Se calcula el KO y el margen del propio activo (para
eso se saca el daño del activo fuera del gate de "ganar ya") y se exige que el
candidato lo mejore **estrictamente** -- el cambio cuesta además la energía de la
retirada. Ambos lados son ex por construcción (el bucle solo mira `OUR_EX_IDS`),
así que los premios empatan y lo único que decide es cuánto aguanta.

Lo que NO cambia: el pivote de negación de premios sigue vivo cuando de verdad
niega algo. El caso que lo creó (`registro_013` paso 139: Hydrapple ex a 10 PV
activo, Ogerpon ex sano en banca) mejora el margen del activo y sigue disparando.

Corpus dorado: un único flip, el de este paso (RETREAT → jugar Xerosic).
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
            / "alakazam_retirada_al_cuerpo_de_50pv_step174.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
ALAKAZAM = m.Alakazam_ex
KADABRA = m.Kadabra


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


def _opcion(obs, tipo):
    return next(i for i, o in enumerate(obs["select"]["option"])
                if o.get("type") == tipo)


# ---------------------------------------------------------------------------
# 1. El escenario: sin él, el test no mide nada
# ---------------------------------------------------------------------------

def test_el_fixture_es_el_cambio_por_el_cuerpo_de_50pv():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]

    activo = mio["active"][0]
    banca = [b for b in mio["bench"] if b]
    gemelo = next(b for b in banca if b["id"] == OGERPON)

    # El de delante está SANO; el de banca, a 50 de 210.
    assert activo["id"] == OGERPON and activo["hp"] == 210
    assert gemelo["id"] == OGERPON and gemelo["hp"] == 50
    # Los dos tienen las mismas 4 energías efectivas: mismo ataque.
    assert len(activo["energies"]) == len(gemelo["energies"]) == 4

    # Los dos son ex: el cambio NO niega ningún premio (2 en ambos casos).
    assert m.prize_count_op(
        m.to_observation_class(o).current.players[yo].active[0]) == 2

    # Su Alakazam muere a Myriad: 30 + 30*(4 propias + 1 suya) = 180 >= 140.
    assert riv["active"][0]["id"] == ALAKAZAM and riv["active"][0]["hp"] == 140
    assert 30 + 30 * (4 + len(riv["active"][0]["energies"])) >= 140

    # La única amenaza que queda tras el KO es su banca: Kadabra pega 30.
    assert any(b and b["id"] == KADABRA for b in riv["bench"])
    assert (m.attack_table[m.card_table[KADABRA].attacks[0]].damage or 0) == 30


def test_no_se_retira_el_ogerpon_sano():
    o = _obs()
    retirar = _opcion(o, int(m.OptionType.RETREAT))
    assert m.agent(o) != [retirar], (
        "el activo de 210 PV ya noquea al Alakazam; retirarlo para subir el "
        "gemelo de 50 PV cuesta una energía y deja delante el cuerpo que muere")


# ---------------------------------------------------------------------------
# 2. El margen: lo que decide, medido sobre el tablero real
# ---------------------------------------------------------------------------

def test_el_activo_aguanta_nueve_veces_mas_que_el_candidato():
    o = _obs()
    cur = m.to_observation_class(o).current
    yo = o["current"]["yourIndex"]
    mio = cur.players[yo]
    riv = cur.players[1 - yo]

    def margen(pkm):
        amenaza = max((m._op_active_attack_damage_to(b, pkm, riv.handCount)
                       for b in riv.bench if b is not None), default=0)
        return (pkm.hp or 0) - amenaza

    activo = mio.active[0]
    gemelo = next(b for b in mio.bench if b is not None and b.id == OGERPON)
    assert margen(gemelo) == 20        # 50 - 30 (Kadabra)
    assert margen(activo) == 180       # 210 - 30
    assert margen(activo) > margen(gemelo)
