"""Dentro de una linea evolutiva se noquea la ETAPA MAS ALTA que se pueda.

Escenario (user, `registros/registro_008_pasos_088_hasta_097.json` paso 93,
episodio 89013104, turno 8, vs Cynthia's Garchomp ex, GANADA con error):

    NOSOTROS (asiento 1, 3 premios)          RIVAL (6 premios)
    activo  Hydrapple ex 230/330, 2e         activo  Cynthia's Gabite 100 PV,
    banca   Ogerpon ex 4e, Meganium,                 **0 energias** (Fase 1)
            Meowth ex, Ogerpon ex 2e,        banca   Cynthia's Roselia,
            Tapu Bulu                                **Cynthia's Gible 1e**,
    mano    2x Ultra Ball, Bayleef, Applin,           Roselia, Roselia
            Dipplin, Hydrapple ex, Ogerpon ex,
            Fezandipiti ex, **Boss's Orders**

El Hydrapple ex noquea a cualquiera de los dos cuerpos. El agente jugaba
**Boss's Orders** para subir el **Gible** (Basico) y noquearlo. Es un error
triple:

  * ambos KOs cobran **el mismo premio** (los dos son cuerpos de 1 premio);
  * el **Gabite ya esta de activo**: noquearlo es GRATIS -- no cuesta el Boss's
    ni el Supporter del turno, que quedan para el turno siguiente;
  * y sobre todo, el Gabite esta **un escalon mas arriba**. La linea es
    Gible -> Gabite -> **Cynthia's Garchomp ex** (Fase 2, 330 PV, 2 premios):
    el mazo rival depende de esa Fase 2 para atacar. Matando el Gabite el rival
    tiene que rehacer **dos** escalones; matando el Gible, el Gabite evoluciona
    igual el turno siguiente.

REGLA: cuando la linea rival es Basico -> Fase 1 -> Fase 2, se noquea SIEMPRE
la etapa mas alta alcanzable. Nunca se gasta Boss's Orders en bajar a la etapa
INFERIOR de una linea cuya etapa superior ya esta delante y muere igual.

Por que disparaba
-----------------
En el bucle deny-evo de la valoracion del Boss's, el Gible cumplia
`_bo_pe_is_ex_preevo_energized` (pre-evo de linea ex, con energia, premios
iguales) y con el activo DESNUDO se activaba la excepcion
`_bo_pe_is_energized_preevo_vs_bare_wall`, que saltaba el guard de "el activo
domina". Esa excepcion se escribio para el caso **INVERSO** de la linea Marnie
(activo **Impidimp** BASICO desnudo, banca **Morgrem** FASE 1 energizada): alli
gustear SI sube de escalon. Solo miraba la ENERGIA del activo, nunca su ETAPA.

El fix es un veto de etapa (`_supera_en_evolucion`, deck-agnostico: sale de
`basic`/`stage1`/`stage2` y de la cadena `evolvesFrom` del dato de carta) que
pisa a las tres excepciones cuando el activo es un eslabon mas evolucionado de
la MISMA linea y no rinde menos premios.

Censo de flips sobre las 117 decisiones del episodio 89013104: **1 flip**, el
de este paso. Corpus dorado sin cambios.
"""

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "garchomp_step93_no_gustear_el_gible_con_gabite_activo.json")

GIBLE = m.Cynthias_Gible
GABITE = m.Cynthias_Gabite
GARCHOMP = m.Cynthias_Garchomp_ex
HYDRAPPLE = m.Hydrapple_ex
BOSS = m.Boss_Orders
ROSELIA = 341
IMPIDIMP = m.Marnies_Impidimp
MORGREM = m.Marnies_Morgrem


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


def _pkm(card_id, energias=0):
    return SimpleNamespace(id=card_id, energies=[1] * energias, energyCards=[],
                           tools=[])


def _idx(obs, **campos):
    """Indice de la opcion del menu que cumple todos los campos dados."""
    return next(i for i, o in enumerate(obs["select"]["option"])
                if all(o.get(k) == v for k, v in campos.items()))


# ---------------------------------------------------------------------------
# 1. El escenario: sin el, el test no mide nada
# ---------------------------------------------------------------------------

def test_el_fixture_es_el_paso_93_con_la_fase_1_delante():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]

    assert o["current"]["turn"] == 8 and not o["current"]["supporterPlayed"]

    # Nosotros: Hydrapple ex de activo, con el Boss's en la mano y el menu
    # ofreciendo AMBAS cosas (jugarlo o atacar).
    assert mio["active"][0]["id"] == HYDRAPPLE
    assert any(c["id"] == BOSS for c in mio["hand"])
    assert _idx(o, type=13) >= 0 and _idx(o, type=7, index=8) >= 0

    # El rival: Gabite (Fase 1) de activo DESNUDO y el Gible (Basico) en banca
    # CON energia -- los dos cuerpos de la misma linea, los dos de 1 premio.
    assert riv["active"][0]["id"] == GABITE and riv["active"][0]["energies"] == []
    banca = [b["id"] for b in riv["bench"] if b]
    assert banca == [ROSELIA, GIBLE, ROSELIA, ROSELIA]
    assert len(riv["bench"][1]["energies"]) == 1
    assert (m.prize_count_op(_pkm(GABITE)) == m.prize_count_op(_pkm(GIBLE)) == 1)

    # ...y la linea acaba en un ex de 2 premios: por eso cortarla vale.
    assert m.prize_count_op(_pkm(GARCHOMP)) == 2


def test_el_hydrapple_noquea_a_los_dos_cuerpos():
    """El veto solo tiene sentido si el KO del activo es REAL: si el Gabite no
    muriera, gustear el Gible seguiria siendo la unica via a un premio."""
    o = _obs()
    riv = o["current"]["players"][1 - o["current"]["yourIndex"]]
    assert riv["active"][0]["hp"] == 100 and riv["bench"][1]["hp"] == 70


# ---------------------------------------------------------------------------
# 2. La decision
# ---------------------------------------------------------------------------

def test_no_se_gustea_el_gible_teniendo_el_gabite_de_activo():
    o = _obs()
    assert m.agent(o) == [_idx(o, type=13)], (
        "con la Fase 1 de la linea ya de activo y noqueable, se ATACA: mismo "
        "premio, corta la linea mas arriba y no gasta el Boss's ni el Supporter")


def test_control_con_el_basico_delante_el_boss_si_se_juega():
    """Control (el caso Marnie, invertido sobre el mismo tablero): si el que
    esta de activo es el BASICO desnudo y la FASE 1 energizada esta en la banca,
    gustear SI sube de escalon -- y el Boss's vuelve a jugarse."""
    o = _obs()
    riv = o["current"]["players"][1 - o["current"]["yourIndex"]]
    activo, banca = riv["active"][0], riv["bench"][1]
    activo["id"], banca["id"] = GIBLE, GABITE
    activo["hp"] = activo["maxHp"] = 70
    banca["hp"] = banca["maxHp"] = 100
    activo["preEvolution"] = []
    banca["preEvolution"] = [{"id": GIBLE, "playerIndex": 0, "serial": 4}]

    assert m.agent(o) == [_idx(o, type=7, index=8)], (
        "activo Basico desnudo + Fase 1 energizada en banca: el gusteo corta la "
        "linea un escalon MAS ARRIBA, que es justo lo que motiva el deny-evo")


# ---------------------------------------------------------------------------
# 3. Los predicados de etapa/linea, en aislamiento (deck-agnosticos)
# ---------------------------------------------------------------------------

def test_la_etapa_sale_del_dato_de_carta():
    assert m._etapa_evolutiva(GIBLE) == 0
    assert m._etapa_evolutiva(GABITE) == 1
    assert m._etapa_evolutiva(GARCHOMP) == 2
    # Nuestra propia linea y la de Marnie, sin tocar EVO_LINES.
    assert [m._etapa_evolutiva(c) for c in (m.Applin, m.Dipplin, HYDRAPPLE)] == [0, 1, 2]
    assert [m._etapa_evolutiva(c) for c in (IMPIDIMP, MORGREM,
                                            m.Grimmsnarl_ex)] == [0, 1, 2]
    # Lo que no es un Pokemon (o no existe) no tiene etapa.
    assert m._etapa_evolutiva(BOSS) is None
    assert m._etapa_evolutiva(-12345) is None


def test_la_linea_se_reconstruye_subiendo_por_evolves_from():
    assert m._misma_linea_evolutiva(GIBLE, GARCHOMP)
    assert m._misma_linea_evolutiva(GARCHOMP, GABITE)
    assert m._misma_linea_evolutiva(GIBLE, GIBLE)
    # Cynthia's Roselia -> Roserade es OTRA linea del MISMO mazo.
    assert not m._misma_linea_evolutiva(GIBLE, ROSELIA)
    # Y las lineas homonimas de otro entrenador no se mezclan con la nuestra.
    assert not m._misma_linea_evolutiva(GABITE, m.Dipplin)


def test_supera_en_evolucion_exige_misma_linea_y_etapa_mayor():
    assert m._supera_en_evolucion(_pkm(GABITE), _pkm(GIBLE))
    assert m._supera_en_evolucion(_pkm(GARCHOMP), _pkm(GIBLE))
    assert m._supera_en_evolucion(_pkm(MORGREM), _pkm(IMPIDIMP))
    # Al reves NO: es justo el caso que motiva el deny-evo.
    assert not m._supera_en_evolucion(_pkm(GIBLE), _pkm(GABITE))
    # Misma etapa, o etapas de LINEAS distintas: no hay escalon que comparar.
    assert not m._supera_en_evolucion(_pkm(GABITE), _pkm(GABITE))
    assert not m._supera_en_evolucion(_pkm(GABITE), _pkm(ROSELIA))
    assert not m._supera_en_evolucion(_pkm(m.Dipplin), _pkm(GIBLE))
    assert not m._supera_en_evolucion(None, _pkm(GIBLE))
    assert not m._supera_en_evolucion(_pkm(GABITE), None)
