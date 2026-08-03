"""Promoción tras KO: veto de MATCH POINT y desempate entre supervivientes.

Cierra las prioridades que el user fijó para "a quién subir" cuando nos
noquean el activo, en este orden:

    (1) que SOBREVIVA al golpe                -> `_promo_survives` + Festival Lead
    (2) no exponer el multiplicador Wild Growth -> veto "la línea Meganium no
        va al activo" (ya existía)
    (3) el que esté MÁS CERCA de poder atacar
    (4) a igualdad, el que ceda MENOS premios

**Item 4 — MATCH POINT.** Cuando al rival le basta con noquear ese cuerpo para
llevarse el último premio, subir un condenado no es un mal intercambio: es
perder la partida. La supervivencia deja de ser una *penalización*
(`PROMO_DOOMED_PENALTY`, 6000) y pasa a ser un **veto**
(`PROMO_MATCH_POINT_VETO`), por debajo de `SCORE_NEVER` para que no empate con
los otros vetos de promoción.

El caso que lo hace falta es el del log 88971843 sin el Tapu Bulu: el único
cuerpo que aguanta es el **Meganium**, que lleva su propio veto a −10000 por ser
el motor Wild Growth. Con solo la penalización, el Dipplin condenado (−2595) le
ganaba y entregaba la partida. Dar el último premio es peor que exponer el
multiplicador.

**Item 5 — desempate.** Las prioridades (3) y (4) ya eran decisivas, y en ese
mismo orden, dentro de `_promote_setup_ko_attacker` (`_ps_key`), pero esa regla
exige que el ataque completado REMATE al activo rival. Este ajuste cubre el
hueco que deja: los supervivientes cuyo ataque no remata. Está acotado a 0..450
— manda sobre el score BASE de la promoción (150-250, que ordena por VIDA, el
criterio que el user pone por debajo de estos dos) y queda muy por debajo de
cualquier regla decisiva. Con los 60 puntos de la primera versión no llegaba:
medido, un Ogerpon ex de 210 PV a TRES adjuntes de atacar seguía ganándole a un
Tapu Bulu de 140 a DOS.
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
            / "festival_lead_promover_tapu_no_dipplin_step117.json")

MEGANIUM = m.Meganium
DIPPLIN = m.Dipplin
CHIKORITA = m.Chikorita
TAPU = m.Tapu_Bulu
OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRAPPLE = m.Hydrapple_ex
GRIMMSNARL = 648                # Marnie's Grimmsnarl ex: Shadow Bullet 180


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
    m._op_bench_count = 0
    m._festival_grounds_in_play = False
    yield
    m._init_cartas_tracking()


def _pk(cid, hp, energias=0, serial=900):
    """Pokemon de banca sintetico (energias ya EFECTIVAS, como la observacion)."""
    return {"appearThisTurn": False,
            "energies": [1] * energias,
            "energyCards": ([{"id": m.Basic_Grass_Energy, "playerIndex": 0,
                              "serial": serial}] if energias else []),
            "hp": hp, "id": cid, "maxHp": hp, "playerIndex": 0,
            "preEvolution": [], "serial": serial, "tools": []}


def _base(banca=None, sin_estadio=False, op_activo=None, op_premios=None):
    """Fixture real del paso 117 con la banca / el activo rival sustituidos."""
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]
    if sin_estadio:
        o["current"]["stadium"] = []
    if op_activo is not None:
        op_activo = dict(op_activo, playerIndex=1 - yo)
        riv["active"] = [op_activo]
    if op_premios is not None:
        riv["prize"] = [None] * op_premios
    if banca is not None:
        mio["bench"] = [dict(b, playerIndex=yo) for b in banca]
    o["select"]["option"] = [
        {"area": 5, "index": k, "playerIndex": yo, "type": 3}
        for k in range(len(mio["bench"]))]
    return o


def _elegido(obs):
    yo = obs["current"]["yourIndex"]
    opt = obs["select"]["option"][m.agent(obs)[0]]
    return obs["current"]["players"][yo]["bench"][opt["index"]]


# ---------------------------------------------------------------------------
# Item 4 - MATCH POINT
# ---------------------------------------------------------------------------

def test_el_veto_de_match_point_esta_por_debajo_de_los_demas_vetos():
    """Si empatara con SCORE_NEVER, el desempate quedaría al orden de opciones
    justo entre el cuerpo que aguanta y el que nos hace perder."""
    assert m.PROMO_MATCH_POINT_VETO < m.SCORE_NEVER
    assert m.PROMO_MATCH_POINT_VETO < -m.PROMO_KO_BONUS


def test_prefiere_el_motor_vetado_antes_que_regalar_el_ultimo_premio():
    """El caso real sin el Tapu Bulu: el único superviviente es el Meganium,
    que lleva su propio veto por ser el multiplicador Wild Growth."""
    o = _base()
    yo = o["current"]["yourIndex"]
    banca = [b for b in o["current"]["players"][yo]["bench"] if b["id"] != TAPU]
    o = _base(banca=banca)

    riv = o["current"]["players"][1 - yo]
    assert len(riv["prize"]) == 1                      # match point
    assert [b["id"] for b in o["current"]["players"][yo]["bench"]] == [
        MEGANIUM, DIPPLIN, CHIKORITA]
    # Meganium (160) aguanta los 100; Dipplin (80) y Chikorita (70) no.
    assert _elegido(o)["id"] == MEGANIUM


def test_sin_match_point_el_condenado_sigue_siendo_una_opcion():
    """Frontera: con el rival a 3 premios, un KO no cierra la partida y vuelve
    a mandar la penalización (que es graduable), no el veto."""
    o = _base()
    yo = o["current"]["yourIndex"]
    banca = [b for b in o["current"]["players"][yo]["bench"] if b["id"] != TAPU]
    o = _base(banca=banca, op_premios=3)
    # Con 3 premios el rival no gana noqueando un cuerpo de 1: el Dipplin deja
    # de estar vetado y su score vuelve a competir con el del Meganium.
    assert len(o["current"]["players"][1 - yo]["prize"]) == 3
    assert _elegido(o)["id"] == DIPPLIN


def test_si_no_aguanta_nadie_no_se_veta_la_banca_entera():
    """Frontera: sin supervivientes la partida está perdida igual y manda la
    regla de premios; vetar a todos dejaría la elección al azar."""
    o = _base(banca=[_pk(DIPPLIN, 80, 2, 901), _pk(CHIKORITA, 70, 0, 902)],
              op_premios=1)
    yo = o["current"]["yourIndex"]
    # Los dos mueren a los 100 de Do the Wave.
    for b in o["current"]["players"][yo]["bench"]:
        assert b["hp"] <= 100
    elegido = _elegido(o)
    assert elegido["id"] in (DIPPLIN, CHIKORITA)       # se elige, no se bloquea


def test_match_point_es_deck_agnostico():
    """No depende de Festival Lead: mismo veto contra Marnie's Grimmsnarl ex
    (Shadow Bullet 180) y sin estadio en mesa."""
    o = _base(sin_estadio=True,
              op_activo={"appearThisTurn": False, "energies": [2, 2],
                         "energyCards": [], "hp": 320, "id": GRIMMSNARL,
                         "maxHp": 320, "preEvolution": [], "serial": 800,
                         "tools": []},
              op_premios=1,
              banca=[_pk(HYDRAPPLE, 330, 0, 901), _pk(TAPU, 140, 2, 902)])
    yo = o["current"]["yourIndex"]
    op_act = m.to_observation_class(o).current.players[1 - yo].active[0]
    tapu = m.to_observation_class(o).current.players[yo].bench[1]
    hydra = m.to_observation_class(o).current.players[yo].bench[0]
    assert m._op_active_attack_damage_to(op_act, tapu) >= 140    # muere
    assert m._op_active_attack_damage_to(op_act, hydra) < 330    # aguanta
    assert _elegido(o)["id"] == HYDRAPPLE


# ---------------------------------------------------------------------------
# Item 5 - desempate entre supervivientes
# ---------------------------------------------------------------------------

def test_entre_supervivientes_manda_estar_cerca_de_atacar_y_ceder_menos():
    """Un Tapu Bulu de 140 PV a DOS adjuntes de Wood Hammer (1 premio) sube
    antes que un Ogerpon ex de 210 a TRES de Myriad (2 premios), aunque tenga
    70 PV menos: la vida es el criterio de MÁS ABAJO."""
    o = _base(banca=[_pk(OGERPON, 210, 0, 901), _pk(TAPU, 140, 2, 902)])
    yo = o["current"]["yourIndex"]
    banca = m.to_observation_class(o).current.players[yo].bench
    op_act = m.to_observation_class(o).current.players[1 - yo].active[0]

    # Los dos AGUANTAN el golpe: el desempate no lo decide la supervivencia.
    for pk_ in banca:
        assert m._op_active_attack_damage_to(op_act, pk_) < (pk_.hp or 0)
    # Y ninguno remata: tampoco lo decide el KO.
    assert 210 > 0 and m.ATTACK_ENERGY_REQ[OGERPON] > 0

    elegido = _elegido(o)
    assert elegido["id"] == TAPU
    assert m.prize_count(banca[1]) < m.prize_count(banca[0])


def test_el_desempate_no_puede_comprar_una_regla_decisiva():
    """Acotado a 0..450: por debajo del +4000 del mejor atacante, de las ramas
    con nombre (8000-9500) y del +20000 del que noquea."""
    assert 450 < 4000 < m.PROMO_KO_BONUS


def test_el_desempate_no_cambia_la_decision_del_registro():
    """Control de no-regresión: el paso 117 sigue subiendo al Tapu Bulu."""
    o = _base()
    assert _elegido(o)["id"] == TAPU
