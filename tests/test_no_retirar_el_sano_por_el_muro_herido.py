"""El muro HERIDO no es un muro: se mide la vida ACTUAL, no el HP impreso.

Escenario (`registros/registro_014_pasos_160_hasta_173.json`, paso 166, turno 14,
GANADA vs Alakazam -- episodio 88911400):

    NOSOTROS (3 premios)                    RIVAL (2 premios)
    activo  Teal Mask Ogerpon ex            activo  Alakazam 140/140, 1 energia
            **210/210**, 4 energias                 (Powerful Hand: 20 x mano)
    banca   Hydrapple ex **90/330**, 2 en.  banca   Shaymin 80, Dunsparce 70,
            Meowth ex x2, Fezandipiti ex,           Abra 50, Abra 50
            Meganium

El agente **retiraba el Ogerpon de 210/210** -- descartando una energia para pagar
el coste -- y promovia el **Hydrapple ex a 90 PV** para atacar con el. Los dos
noquean al Alakazam (Myriad Leaf Shower: 30 + 30*(4+1) = 180; Syrup Storm: 150),
los dos son ex de 2 premios: el cambio no gana nada y deja delante el cuerpo que
muere al turno siguiente. Lo correcto era **atacar con el Ogerpon**.

Causa: TRES sitios daban por hecho que "Hydrapple ex es el muro de 330 PV" usando
el **HP IMPRESO**, que es una constante de la carta y no sabe nada del dano ya
recibido:

  1. `base_score` del bucle greedy de atacante: +200 a Hydrapple ex y -100 a Teal
     Mask Ogerpon ex. Esos 300 puntos superaban al +220 de "soy el activo" y el
     plan elegia el atacante de BANCA por 78 puntos (13342 vs 13264). Con
     `plan.attacker >= 1` el ataque del activo queda VETADO.
  2. `_promote_hydra = _hydra_can_ko or (not _act_can_ko)`: si el Hydrapple de
     banca noquea, promueve -- aunque el activo tambien noquee.
  3. `_active_ex_fragile_pivot` (score 9000 de la RETIRADA): mide la fragilidad
     del activo con `maxHp < 330`, nunca con la vida del candidato.

Arreglo: en los tres, la comparacion se hace con la vida ACTUAL y se exige mejora
ESTRICTA -- el cambio cuesta ademas la energia de la retirada. Los dos primeros
piden tambien que el relevo no NIEGUE premios (`prize_count`), para que un no-ex
de banca pueda seguir relevando a un ex activo aunque aguante menos: ahi el cuerpo
peor se paga con 1 premio en vez de 2 (`_alakazam_pivot_1prize`).

Lo que NO cambia: con el Hydrapple SANO el pivote sigue vivo (330 > 210), que es
el caso que lo creo (log 86412738 p145 vs Hops, log 86505760 p55 vs Alakazam). Y
la rama de activo ESTANCADO (`not _act_can_ko`) no se toca: ahi el pivote compra
el KO que no teniamos.

Corpus dorado: un unico flip, el de este paso (RETREAT -> ATTACK id120).
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
            / "alakazam_no_retirar_ogerpon_sano_por_hydrapple_a_90_step166.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRAPPLE = m.Hydrapple_ex
ALAKAZAM = 743  # Alakazam Fase 2 (no-ex): 140 PV, Powerful Hand


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
# 1. El escenario: sin el, el test no mide nada
# ---------------------------------------------------------------------------

def test_el_fixture_es_el_muro_herido_a_90_pv():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]

    activo = mio["active"][0]
    hydra = next(b for b in mio["bench"] if b and b["id"] == HYDRAPPLE)

    # El de delante esta INTACTO; el "muro" de banca, a 90 de 330.
    assert activo["id"] == OGERPON and activo["hp"] == activo["maxHp"] == 210
    assert hydra["maxHp"] == 330 and hydra["hp"] == 90

    # Los dos pueden atacar YA: Ogerpon con 4 energias (req 3), Hydrapple con 2.
    assert len(activo["energies"]) == 4
    assert len(hydra["energies"]) == 2

    # Los dos son ex: el cambio NO niega ningun premio (2 en ambos casos).
    clase = m.to_observation_class(o)
    assert m.prize_count(clase.current.players[yo].active[0]) == 2
    assert m.prize_count(
        next(b for b in clase.current.players[yo].bench
             if b is not None and b.id == HYDRAPPLE)) == 2

    # Su Alakazam muere a Myriad Leaf Shower: 30 + 30*(4 propias + 1 suya) = 180.
    rival = riv["active"][0]
    assert rival["id"] == ALAKAZAM and rival["hp"] == 140
    assert 30 + 30 * (4 + len(rival["energies"])) >= rival["hp"]


# ---------------------------------------------------------------------------
# 2. La decision
# ---------------------------------------------------------------------------

def test_no_se_retira_el_ogerpon_intacto():
    o = _obs()
    retirar = _opcion(o, int(m.OptionType.RETREAT))
    assert m.agent(o) != [retirar], (
        "el activo de 210/210 ya noquea al Alakazam; retirarlo para subir un "
        "Hydrapple ex a 90 PV cuesta una energia, no niega ningun premio y "
        "deja delante el cuerpo que muere")


def test_se_ataca_con_el_ogerpon_activo():
    o = _obs()
    atacar = _opcion(o, int(m.OptionType.ATTACK))
    assert m.agent(o) == [atacar]
    # Y el plan apunta al ACTIVO (indice 0): con `plan.attacker >= 1` el
    # scorer VETA el ataque del activo y el turno se va por la retirada.
    assert m.plan.attacker == 0
    assert m.plan.remain_hp is not None and m.plan.remain_hp <= 0


# ---------------------------------------------------------------------------
# 3. El discriminante: la vida ACTUAL, no el HP impreso
# ---------------------------------------------------------------------------

def test_con_el_hydrapple_SANO_el_pivote_sigue_vivo():
    """El muro de verdad (330 > 210) sigue relevando al ex fragil."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    hydra = next(b for b in o["current"]["players"][yo]["bench"]
                 if b and b["id"] == HYDRAPPLE)
    hydra["hp"] = 330  # curado: ahora SI aguanta mas que el Ogerpon de 210

    retirar = _opcion(o, int(m.OptionType.RETREAT))
    assert m.agent(o) == [retirar], (
        "con el Hydrapple ex a 330 el pivote es el de siempre: mismo KO pero "
        "deja delante al cuerpo que aguanta mas")


def test_empatados_en_vida_no_se_paga_la_retirada():
    """Mejora ESTRICTA: a igual vida, el cambio solo cuesta una energia."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    hydra = next(b for b in o["current"]["players"][yo]["bench"]
                 if b and b["id"] == HYDRAPPLE)
    hydra["hp"] = o["current"]["players"][yo]["active"][0]["hp"]  # 210 = 210

    retirar = _opcion(o, int(m.OptionType.RETREAT))
    assert m.agent(o) != [retirar]
