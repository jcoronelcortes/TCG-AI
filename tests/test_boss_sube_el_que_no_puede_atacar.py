"""Objetivo del gusteo SIN KO: lo que decide es el COSTE DEL ATAQUE, no la etapa.

Registro real del criterio que ya fabrica en sintético
`test_boss_objetivo_sin_ko_cuerpo_muerto.py`. Aquel test construye el escenario
con StateBuilder porque los registros locales apenas llegaban al prompt de
objetivo (contexto 3); éste ancla el **paso real** en el que el agente enviado
falló, para que la regla no pueda volver atrás sin que salte un test.

Escenario (`registros/registro_006_pasos_063_hasta_066.json`, paso 65, turno 6,
PERDIDA vs Dragapult -- episodio 89079426):

    NOSOTROS (6 premios)                    RIVAL (6 premios)
    activo Chikorita 60/70, 1 {G}           activo  Budew 30
    banca  Fezandipiti ex 210, 0 {G}        banca   Drakloak 90 **1 en.**
    mano   Ultra Ball (bloqueada), Meganium,        **Dragapult ex 320, 0 en.**
           Planta x2, Meowth ex                     Munkidori 110, 1 en.
                                                    **Drakloak 90, 0 en.** x2

Jugar el Boss's era correcto (nuestro activo no remata nada). El agente enviado
**subió el Dragapult ex**: es la pieza más gorda de la banca, pero su ataque
cuesta **1** energía, así que con el adjunte del turno siguiente ataca desde el
activo -- y encima el Boss's le había pagado la subida gratis. Le pusimos
delante, gratis, justo el cuerpo con el que quería atacar.

El objetivo correcto es un **Drakloak pelado**: su ataque cuesta **2**, así que
ni con el adjunte del turno puede pegar; su única salida es gastar la energía
del turno en pagar la retirada. Es un turno rival entero comprado.

Los tres números que deciden (regla del user) y que este paso separa:

    candidato        energías   coste ataque   coste retirada   ¿muerto?
    Drakloak            1            2              1              NO (2<=1+1)
    Dragapult ex        0            1              1              NO (1<=0+1)
    Munkidori           1            2              1              NO (2<=1+1)
    Drakloak            0            2              1              **SÍ** (2>0+1)

No basta con mirar energías adjuntas y coste de retirada: por esos dos números
el Dragapult ex y el Drakloak pelado **empatan** (ambos a 0 energías, ambos con
retirada 1). Lo único que los separa es cuántas energías necesitan para
**empezar a atacar**, que es lo que mide `_op_cuerpo_inofensivo` -- por COSTE
leído del dato de carta, nunca por daño impreso (Powerful Hand, Cruel Arrow y
los dos ataques de Gardevoir ex figuran con 0 y todos pegan de verdad).

La regla que lo aplica es `sin_ko_prefiere_cuerpo_muerto` (+1500, en los dos
modos del selector), documentada en `docs/main-08-agent-boss-orders.md`. Aquí se
fijan además los DOS lados del contraste, que es lo que de verdad protege contra
una regresión: el Drakloak pelado gana **y** el Dragapult ex queda por debajo.
"""

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
            / "dragapult_boss_sube_drakloak_pelado_step65.json")

DRAGAPULT = m.Dragapult_ex
DRAKLOAK = m.Drakloak
DREEPY = m.Dreepy
MUNKIDORI = m.Munkidori


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
    m._grass_attaches_this_turn = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _obs():
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _objetivo(obs, eleccion):
    """(id, energías) del Pokémon de banca rival que elige el gusteo."""
    o = obs["select"]["option"][eleccion[0]]
    assert o["type"] == int(m.OptionType.CARD) and o["area"] == 5
    pk = obs["current"]["players"][o["playerIndex"]]["bench"][o["index"]]
    return pk["id"], len(pk["energies"])


def _pk(card_id, energias):
    return SimpleNamespace(id=card_id, energies=[m.EnergyType.GRASS] * energias)


# ---------------------------------------------------------------------------
# 1. El paso real
# ---------------------------------------------------------------------------

def test_paso65_sube_un_drakloak_pelado_no_el_dragapult_ex():
    obs = _obs()
    assert _objetivo(obs, m.agent(obs)) == (DRAKLOAK, 0), (
        "sin KO se sube el cuerpo que NO puede pagar su ataque: el Drakloak "
        "pelado necesita 2 energías y solo puede retirarse; el Dragapult ex "
        "ataca con 1 y el Boss's le habría pagado la subida gratis")


def test_paso65_el_escenario_es_el_que_discrimina():
    """Sin estas tres condiciones el paso no probaría nada."""
    obs = _obs()
    banca = obs["current"]["players"][1]["bench"]
    # (a) el Dragapult ex está en la banca y es elegible;
    assert any(p["id"] == DRAGAPULT for p in banca)
    # (b) por energías + coste de retirada, Dragapult ex y Drakloak pelado
    #     EMPATAN: lo único que los separa es el coste del ataque;
    drag = next(p for p in banca if p["id"] == DRAGAPULT)
    drak = next(p for p in banca if p["id"] == DRAKLOAK and not p["energies"])
    assert len(drag["energies"]) == len(drak["energies"]) == 0
    assert m.RETREAT_COST[DRAGAPULT] == m.RETREAT_COST[DRAKLOAK]
    # (c) y no hay ningún KO disponible (si lo hubiera mandarían los tiers de
    #     KO, >= 3000, y este criterio no llegaría a decidir).
    assert m.plan.remain_hp in (-1, None) or m.plan.remain_hp > 0


# ---------------------------------------------------------------------------
# 2. El criterio, aislado: energías + coste de ataque
# ---------------------------------------------------------------------------

def test_cuerpo_inofensivo_mide_el_coste_del_ataque_no_la_etapa():
    # Dragapult ex: ataque de 1 -> pelado YA ataca el turno que viene.
    assert m._op_cuerpo_inofensivo(_pk(DRAGAPULT, 0)) is False
    # Drakloak: ataque de 2 -> pelado NO ataca ni con el adjunte del turno.
    assert m._op_cuerpo_inofensivo(_pk(DRAKLOAK, 0)) is True
    # ...pero con una energía encima ya no está muerto.
    assert m._op_cuerpo_inofensivo(_pk(DRAKLOAK, 1)) is False
    # Dreepy es Básico y "más pequeño" que el Drakloak, pero su ataque cuesta
    # 1: la ETAPA no es el criterio.
    assert m._op_cuerpo_inofensivo(_pk(DREEPY, 0)) is False
    # Munkidori con su energía llega justo a los 2 que necesita.
    assert m._op_cuerpo_inofensivo(_pk(MUNKIDORI, 1)) is False
    assert m._op_cuerpo_inofensivo(_pk(MUNKIDORI, 0)) is True


def test_budew_nunca_es_cuerpo_muerto_su_ataque_cuesta_cero():
    """Itchy Pollen cuesta 0: pelado y todo, ataca. Es además el que ya veta
    `retirada_gratis` en modo estorbo (coste de retirada 0)."""
    assert m._op_cuerpo_inofensivo(_pk(m.Budew, 0)) is False


# ---------------------------------------------------------------------------
# 3. El eje graduado: `_op_cuerpo_inofensivo` es un UMBRAL de algo medible
# ---------------------------------------------------------------------------
# El booleano no es un dato primitivo: es `_op_deficit_de_ataque >= 2`. Tenerlo
# separado es lo que dejó ver que el horizonte es de UNA energía, y es el dato
# sobre el que se probó (y se descartó por inerte) el desempate graduado dentro
# de la banda -- ver la nota "MEDIDO Y REVERTIDO" junto a `_v_gust_traba_neta`.

def test_deficit_de_ataque_es_el_umbral_graduado_de_cuerpo_inofensivo():
    assert m._op_deficit_de_ataque(_pk(DRAGAPULT, 0)) == 1     # ataca con 1
    assert m._op_deficit_de_ataque(_pk(DRAKLOAK, 0)) == 2      # muerto justo
    assert m._op_deficit_de_ataque(_pk(DRAKLOAK, 1)) == 1
    assert m._op_deficit_de_ataque(_pk(DRAKLOAK, 5)) == 0      # nunca negativo
    assert m._op_deficit_de_ataque(_pk(m.Dusknoir, 0)) == 3    # muerto de sobra
    # El umbral y el eje graduado no pueden derivar: uno es función del otro.
    for cid in (DREEPY, DRAKLOAK, DRAGAPULT, MUNKIDORI, m.Dusknoir):
        for en in range(4):
            pk = _pk(cid, en)
            assert (m._op_cuerpo_inofensivo(pk)
                    is (m._op_deficit_de_ataque(pk) >= 2))


def test_deficit_desconocido_no_inventa_nada():
    """Sin ataques legibles no se concluye ni muerto ni atascado."""
    assert m._op_deficit_de_ataque(None) is None
    assert m._op_deficit_de_ataque(_pk(m.Basic_Grass_Energy, 0)) is None
    assert m._op_cuerpo_inofensivo(_pk(m.Basic_Grass_Energy, 0)) is False


def test_los_muros_pasan_por_muertos_y_por_eso_existe_gust_trampa_ids():
    """Crustle, Sylveon, Cornerstone e Iron Thorns ex tienen ataques de coste 3:
    pelados dan déficit 3 y el criterio los llamaría "muertos". Son justo los
    cuerpos que NO queremos delante, y por eso `GUST_TRAMPA_IDS` los excluye de
    `sin_ko_prefiere_cuerpo_muerto`. Fija la premisa de esa lista."""
    for trampa in sorted(m.GUST_TRAMPA_IDS):
        pk = _pk(trampa, 0)
        assert m._op_deficit_de_ataque(pk) >= 2
        assert m._op_cuerpo_inofensivo(pk) is True


def test_el_paso_65_lo_decide_el_umbral_no_un_desempate_graduado():
    """En este paso TODOS los cuerpos muertos tienen déficit 2 (el mínimo), así
    que la corrección se apoya solo en el umbral. Es lo que hizo inerte el
    desempate graduado que se probó y se revirtió."""
    obs = _obs()
    muertos = [_pk(p["id"], len(p["energies"]))
               for p in obs["current"]["players"][1]["bench"]]
    muertos = [pk for pk in muertos if m._op_cuerpo_inofensivo(pk)]
    assert muertos, "el paso tiene que tener algún cuerpo muerto"
    assert {m._op_deficit_de_ataque(pk) for pk in muertos} == {2}
