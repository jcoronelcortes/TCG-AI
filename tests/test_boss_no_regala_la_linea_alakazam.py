"""Boss's Orders: no regalar el activo cuando el gusteo no consigue nada.

Escenario (`registros/registro_002_pasos_015_hasta_022.json`, paso 20, turno 2,
PERDIDA vs Alakazam -- episodio 88906640):

    NOSOTROS (6 premios)                     RIVAL (6 premios)
    activo  Teal Mask Ogerpon ex 1/3         activo  Fezandipiti ex 210 PV,
    banca   Teal Mask Ogerpon ex 2/3                 **0 energias**
    mano    Lana's Aid, Boss's Orders,       banca   Abra x4, Dunsparce
            Hydrapple ex, Unfair Stamp,      mano    ...con el Kadabra dentro
            Tapu Bulu

Ningun cuerpo nuestro puede atacar (Myriad Leaf Shower cuesta 3). El menu solo
ofrecia cuatro cosas: Boss's Orders, bajar Tapu Bulu (vetado: sin Meganium en
juego), retirar y terminar el turno. El agente jugo **Boss's Orders** y subio un
**Abra**. El rival evoluciono ese mismo Abra a Kadabra y empezo a atacar con el
cuerpo que le habiamos puesto delante.

Dos errores independientes en la misma jugada:

1. **El gusteo no conseguia nada.** Boss's Orders es, para el rival, una
   RETIRADA GRATIS. Solo compensa regalarsela por cobrar un premio que de frente
   no cobramos, o por quitar de enmedio al cuerpo que nos va a golpear. Aqui no
   habia KO posible y su activo no podia atacar en su turno: *Cruel Arrow* cuesta
   3 energias y el Fezandipiti ex estaba pelado (con un adjunte llega a 1).
   -> `gusteo_sin_proposito`, deck-agnostico.

2. **En ESTE matchup subir la linea es hacerles el trabajo.** Abra -> Kadabra ->
   Alakazam es la unica linea atacante del mazo. El unico gusteo sin KO que
   rinde es el inverso -- su Kadabra/Alakazam ya esta de activo CON energia y lo
   mandamos a la banca a cambio de un cuerpo que no ataca (`relevo`).
   -> `no_regalar_linea_alakazam`.

La valoracion de la que salia el gusteo era la rama `elif op_is_alakazam_deck`
de `evaluate_supporters`: puntuaba 700 "subir la mayor evolucion de la linea que
haya en banca" sin exigir KO (Abra de banca > Fezandipiti de activo, que no esta
en la linea). Los 700 pasaban por el tope de turno 2 (200) y llegaban a la regla
de reserva `valor_del_supporter`: 2400 + 200*1.4 = 2680, por encima del END.

Corpus dorado: un unico flip, el de este paso (1/93 decisiones).
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

_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_boss_regala_abra_step20.json"

OGERPON = m.Teal_Mask_Ogerpon_ex
FEZ = m.Fezandipiti_ex
ABRA = m.Abra
KADABRA = m.Kadabra
ALAKAZAM = m.Alakazam_ex
DUNSPARCE = 305


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


def _pk(card_id, energias=0):
    return SimpleNamespace(id=card_id, energies=[1] * energias)


def _op(activo, banca):
    return SimpleNamespace(active=[activo] if activo else [], bench=list(banca))


# ---------------------------------------------------------------------------
# 1. El escenario: sin el, el test no mide nada
# ---------------------------------------------------------------------------

def test_el_fixture_es_el_turno_2_sin_atacante():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]

    assert o["current"]["turn"] == 2 and not o["current"]["supporterPlayed"]

    # Nosotros: dos Ogerpon ex, ninguno a las 3 energias de Myriad Leaf Shower.
    assert mio["active"][0]["id"] == OGERPON
    assert len(mio["active"][0]["energies"]) < m.ATTACK_ENERGY_REQ[OGERPON]
    assert [b["id"] for b in mio["bench"] if b] == [OGERPON]
    assert len(mio["bench"][0]["energies"]) < m.ATTACK_ENERGY_REQ[OGERPON]

    # El rival: Fezandipiti ex PELADO de activo -- Cruel Arrow cuesta 3, asi que
    # ni adjuntando una energia puede atacar en su turno.
    assert riv["active"][0]["id"] == FEZ
    assert riv["active"][0]["energies"] == []
    assert m._coste_de_ataque_min(FEZ) == 3

    # ...y su banca es solo la linea Alakazam (+ un Dunsparce, objetivo PROHIBIDO).
    assert sorted(b["id"] for b in riv["bench"] if b) == [DUNSPARCE] + [ABRA] * 4

    # El Boss's estaba en la mano y el menu lo ofrecia (opcion 0).
    assert any(c["id"] == m.Boss_Orders for c in mio["hand"])
    assert o["select"]["option"][0] == {"index": 1, "type": 7}


def test_no_se_juega_el_boss_que_regala_el_abra():
    o = _obs()
    fin = next(i for i, opt in enumerate(o["select"]["option"])
               if opt.get("type") == 14)
    assert m.agent(o) == [fin], (
        "sin KO y con el activo rival incapaz de atacar, el Boss's se guarda: "
        "subir un Abra le entrega la pre-evolucion de su unico atacante")


# ---------------------------------------------------------------------------
# 2. Los dos predicados, en aislamiento
# ---------------------------------------------------------------------------

def test_activo_inofensivo_mide_el_coste_del_ataque():
    # Fezandipiti ex: Cruel Arrow cuesta 3. Pelado no llega ni con un adjunte;
    # con 2 encima si -> deja de ser inofensivo.
    assert m._op_activo_inofensivo(_op(_pk(FEZ, 0), []))
    assert not m._op_activo_inofensivo(_op(_pk(FEZ, 2), []))
    # Powerful Hand cuesta UNA energia: el Alakazam nunca es inofensivo.
    assert not m._op_activo_inofensivo(_op(_pk(ALAKAZAM, 0), []))
    # Carta desconocida: no se veta por sospecha.
    assert not m._op_activo_inofensivo(_op(_pk(-12345, 0), []))
    assert not m._op_activo_inofensivo(_op(None, []))


def test_relevo_solo_cambia_un_atacante_por_un_no_atacante():
    # Caso bueno: su Alakazam ENERGIZADO baja a la banca y sube un Abra pelado.
    assert m._alakazam_relevo_de_atacante(_op(_pk(ALAKAZAM, 1), [_pk(ABRA)]))
    assert m._alakazam_relevo_de_atacante(_op(_pk(KADABRA, 1), [_pk(FEZ)]))
    # Sin energia encima no hay nada que dejar parado en la banca.
    assert not m._alakazam_relevo_de_atacante(_op(_pk(ALAKAZAM, 0), [_pk(ABRA)]))
    # Cambiar un atacante por otro no releva nada.
    assert not m._alakazam_relevo_de_atacante(
        _op(_pk(ALAKAZAM, 1), [_pk(KADABRA), _pk(ALAKAZAM)]))
    # Dunsparce nunca cuenta: es objetivo PROHIBIDO de gusteo.
    assert not m._alakazam_relevo_de_atacante(_op(_pk(ALAKAZAM, 1), [_pk(DUNSPARCE)]))
    # El caso del registro: su activo esta FUERA de la linea -> no hay relevo,
    # solo el regalo.
    assert not m._alakazam_relevo_de_atacante(_op(_pk(FEZ, 0), [_pk(ABRA)] * 4))


# ---------------------------------------------------------------------------
# 3. Las reglas de `_REGLAS_BOSS_PLAY`
# ---------------------------------------------------------------------------

def _boss_ctx(**over):
    from test_main import _make_boss_ctx
    return _make_boss_ctx(**over)


def test_veto_alakazam_y_veto_generico_sobre_la_regla_de_reserva():
    regalo = _boss_ctx(op_is_alakazam_deck=True,
                       op_state=_op(_pk(FEZ, 0), [_pk(ABRA)] * 4))
    assert m._score_boss_orders_play(regalo) == m.SCORE_VETO

    # Sin el matchup Alakazam el veto que queda es el deck-agnostico: el mismo
    # activo pelado que no puede atacar.
    generico = _boss_ctx(op_state=_op(_pk(FEZ, 0), [_pk(m.Dreepy)]))
    assert m._score_boss_orders_play(generico) == m.SCORE_VETO


def test_el_relevo_del_atacante_no_esta_vetado():
    ctx = _boss_ctx(op_is_alakazam_deck=True,
                    op_state=_op(_pk(ALAKAZAM, 1), [_pk(ABRA)]))
    assert m._score_boss_orders_play(ctx) > 0


def test_un_activo_que_si_ataca_no_dispara_el_veto_generico():
    ctx = _boss_ctx(op_state=_op(_pk(FEZ, 3), [_pk(m.Dreepy)]))
    assert m._score_boss_orders_play(ctx) > 0


def test_los_motivos_con_premio_mandan_sobre_ambos_vetos():
    """Ningun veto puede tapar un remate ni un corte de linea CON KO."""
    tablero = dict(op_is_alakazam_deck=True,
                   op_state=_op(_pk(FEZ, 0), [_pk(ABRA)] * 4))
    assert (m._score_boss_orders_play(_boss_ctx(win_via_boss_gust=True, **tablero))
            == m.BOSS_SCORE_WIN_NOW)
    assert (m._score_boss_orders_play(_boss_ctx(gust_2prize_via_boss=True, **tablero))
            == m.BOSS_SCORE_GUST_2PRIZE)
    assert (m._score_boss_orders_play(_boss_ctx(boss_deny_alakazam_line=True, **tablero))
            == m.BOSS_SCORE_PRIZE_RANK_BASE)
    assert m._score_boss_orders_play(
        _boss_ctx(boss_prize_rank=3, **tablero)) >= m.BOSS_SCORE_PRIZE_RANK_BASE
    # El gusteo DEFENSIVO (nos rematan el proximo turno) tambien sobrevive.
    assert m._score_boss_orders_play(
        _boss_ctx(boss_defensive_gust=True, **tablero)) > 0


def test_una_preevo_de_amenaza_de_activo_no_dispara_el_veto_generico():
    """Un Riolu no ataca hoy, pero evoluciona a Mega Lucario ex y ataca con el
    cuerpo NUEVO: su coste de ataque actual no dice nada."""
    ctx = _boss_ctx(op_state=_op(_pk(m.Riolu, 0), [_pk(m.Mega_Lucario_ex)]))
    assert m._score_boss_orders_play(ctx) > 0


# ---------------------------------------------------------------------------
# 4. El OBJETIVO del gusteo: sin KO no se promueve otro atacante de la linea
# ---------------------------------------------------------------------------

def _gust_ctx(card_id, can_ko=False, energia=0):
    return m._CtxGustObjetivo(
        card_id=card_id, energia=energia,
        rc0=m.RETREAT_COST.get(card_id, 0), rc1=m.RETREAT_COST.get(card_id, 1),
        stall_diff=m.RETREAT_COST.get(card_id, 0) - energia,
        is_ex=False, is_exmega=False, is_megaex=False, prizes=1, wins_now=False,
        is_stage1=(card_id == KADABRA), is_stage2=(card_id == ALAKAZAM),
        tiene_tool=False, can_ko=can_ko, tier_ko=5 if can_ko else 0,
        plan_target_match=False, regust_energized=False,
        linea_rank=0, linea_can_ko=False, op_alakazam=True,
        op_latias=False, op_linea_dragapult=False, op_linea_typhlosion=False)


def _estorbo(ctx):
    score, _ = m._resolver_reglas(m._REGLAS_GUST_ESTORBO,
                                 m._AJUSTES_GUST_ESTORBO, ctx, defecto=-200)
    return score


def test_sin_ko_no_se_sube_kadabra_ni_alakazam():
    assert _estorbo(_gust_ctx(KADABRA)) == m.SCORE_FORBID
    assert _estorbo(_gust_ctx(ALAKAZAM)) == m.SCORE_FORBID
    # El Abra pelado sigue siendo un relevo valido (regla del user).
    assert _estorbo(_gust_ctx(ABRA)) > 0


def test_con_ko_se_levanta_la_prohibicion():
    """Gustear para NOQUEARLOS si corta la linea: ahi los tres son objetivos
    validos y el orden historico (Kadabra >= Abra >= Alakazam) se conserva."""
    kad = _estorbo(_gust_ctx(KADABRA, can_ko=True))
    abra = _estorbo(_gust_ctx(ABRA, can_ko=True))
    alk = _estorbo(_gust_ctx(ALAKAZAM, can_ko=True))
    assert min(kad, abra, alk) > 0
    assert kad >= abra >= alk
