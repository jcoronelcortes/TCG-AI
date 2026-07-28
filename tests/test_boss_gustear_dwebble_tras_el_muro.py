"""Con el muro de Crustle delante, el Dwebble de banca SI se gustea.

Escenario (user, episodio 88620891 paso 78 vs Crustle, PERDIDA): Hydrapple ex
ACTIVO con 12 unidades de Planta en el campo -- Syrup Storm pega 390 -- pero el
activo rival es un Crustle, cuya habilidad *Mysterious Rock Inn* anula TODO el
dano de nuestros Pokemon ex. Atacar de frente hace 0. En la banca rival esperan
DOS Dwebble no-ex (70 y 90 PV), y en la mano tenemos Boss's Orders. La jugada
correcta es de tres pasos:

    Boss's Orders -> gustear un Dwebble -> Syrup Storm -> KO (1 premio)

El agente jugaba Xerosic's Machinations y cerraba el turno sin premios, con
Boss's atrapado en la mano (solo cabe un Supporter por turno).

Causa: DOS reglas acopladas del log 86339758, que asumen que vs Crustle un
Dwebble nunca merece el gusteo (es forraje del muro: evoluciona a Crustle):

1. `_AJUSTES_GUST_ESTORBO / forbid_dwebble_vs_crustle` -> SCORE_FORBID sobre el
   Dwebble como OBJETIVO del gusteo.
2. En `evaluate_supporters`, el corte `_cru_has_nondwebble_bench` ponia
   `values[Boss_Orders] = 0` si en la banca rival solo habia Dwebble -- para no
   jugar la carta persiguiendo un KO que (1) despues vetaba.

El corte (2) pisaba silenciosamente a `crustle_gust_worth_it`, la rama que YA
detectaba justo este caso y subia Boss's a `BOSS_PRIORITY_CRUSTLE_GUST` (990).

La exencion es deck-agnostica en su nucleo: `muro_bloquea_activo` mide que
nuestro ACTIVO hace 0 dano efectivo al activo rival via `_our_effective_damage`
(vale para Mysterious Rock Inn, Cornerstone Stance, Sylveon...), no una lista de
ids. Solo la exencion del veto sigue acotada a `op_is_crustle_deck`, que es
donde vive el veto.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import G, Escenario, pk

HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
MEGANIUM = m.Meganium
MEOWTH = m.Meowth_ex
BOSS = m.Boss_Orders
XEROSIC = m.Xerosic_Machinations
ULTRA_BALL = m.Ultra_Ball

CRUSTLE = m.Crustle_Grass      # 345: Mysterious Rock Inn (anula el dano de ex)
DWEBBLE = m.Dwebble_Grass      # 344: 70 PV, no-ex -> 1 premio
KANGASKHAN = m.Mega_Kangaskhan_ex


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
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _escenario(op_activo=None, op_banca=None, mano=(BOSS, XEROSIC, ULTRA_BALL)):
    """El tablero del paso 78: Hydrapple ex activo con Planta de sobra
    (Syrup Storm 390) y la banca rival solo con Dwebble."""
    op_activo = op_activo if op_activo is not None else pk(CRUSTLE)
    op_banca = op_banca if op_banca is not None else [pk(DWEBBLE), pk(DWEBBLE)]
    return (Escenario(turno=8, paso=78, energia_jugada=True)
            .mi_activo(pk(HYDRAPPLE, hp=210, energias=[G, G], fisicas=1))
            .mi_banca(pk(MEGANIUM),
                      pk(OGERPON, energias=[G] * 4, fisicas=2),
                      pk(OGERPON, energias=[G] * 6, fisicas=3),
                      pk(MEOWTH))
            .mi_mano(*mano)
            .op_activo(op_activo)
            .op_banca(*op_banca)
            .op_zonas(mano=8, mazo=30, premios=6))


def _jugada(obs, eleccion, mano):
    o = obs["select"]["option"][eleccion[0]]
    if o["type"] == int(m.OptionType.PLAY):
        return ("PLAY", mano[o["index"]])
    if o["type"] == int(m.OptionType.ATTACK):
        return ("ATTACK", None)
    if o["type"] == int(m.OptionType.END):
        return ("END", None)
    return (o["type"], None)


# ---------------------------------------------------------------------------
# El fallo del registro: jugar Boss's y gustear al Dwebble
# ---------------------------------------------------------------------------

def test_con_el_muro_delante_se_juega_boss_orders():
    """El caso exacto del paso 78: Boss's estaba VETADO (valor 0) y ganaba
    Xerosic. Con el activo anulado por el muro, el gusteo es el unico premio."""
    mano = [BOSS, XEROSIC, ULTRA_BALL]
    obs = _escenario(mano=mano).menu_mano().construir()
    assert _jugada(obs, m.agent(obs), mano) == ("PLAY", BOSS)


def test_el_objetivo_del_gusteo_es_el_dwebble_y_no_el_segundo_muro():
    """La otra mitad de la cadena: sin esto jugariamos Boss's y luego el
    selector vetaria al Dwebble (el fallo que motivo el log 86339758).

    La banca lleva un Dwebble noqueable Y un segundo Crustle, al que tampoco
    danamos: es el par que DISCRIMINA. Con los dos Dwebble del registro ambos
    caian en SCORE_FORBID y el argmax elegia el indice 0 de todas formas, asi
    que la asercion pasaba tambien sin la correccion."""
    obs = (_escenario(op_banca=[pk(DWEBBLE), pk(CRUSTLE)])
           .menu_gusteo().construir())
    idx = obs["select"]["option"][m.agent(obs)[0]]["index"]
    assert obs["current"]["players"][1]["bench"][idx]["id"] == DWEBBLE


def test_el_dwebble_gusteado_muere_al_syrup_storm():
    """El gusteo solo vale si el KO es real: 30 + 30x12 = 390 sobre 70 PV."""
    obs = _escenario().menu_gusteo().construir()
    st = m.to_observation_class(obs).current
    mio, riv = st.players[0], st.players[1]
    m.meganium_in_play = True
    objetivo = riv.bench[0]
    dmg = m.calc_syrup_storm_damage(mio, True)
    assert m._our_effective_damage(mio.active[0], objetivo, dmg, True, False) \
        >= (objetivo.hp or 0)


# ---------------------------------------------------------------------------
# Fronteras: la exencion NO desarma el veto original del log 86339758
# ---------------------------------------------------------------------------

def test_sin_muro_el_dwebble_sigue_vetado_como_objetivo():
    """Frontera: si el activo rival NO nos anula (aqui un Mega Kangaskhan ex al
    que SI pegamos), el Dwebble vuelve a ser forraje y no se gustea."""
    obs = (_escenario(op_activo=pk(KANGASKHAN, hp=300),
                      op_banca=[pk(DWEBBLE), pk(CRUSTLE)])
           .menu_gusteo().construir())
    idx = obs["select"]["option"][m.agent(obs)[0]]["index"]
    assert obs["current"]["players"][1]["bench"][idx]["id"] != DWEBBLE


def test_con_muro_pero_sin_KO_el_dwebble_sigue_vetado():
    """Frontera: la exencion exige un KO REAL. Con el activo propio sin energia
    suficiente para atacar, el Dwebble no es un premio y el veto se mantiene."""
    obs = (Escenario(turno=8, paso=78, energia_jugada=True)
           .mi_activo(pk(HYDRAPPLE, hp=210))          # 0 energias: no ataca
           .mi_banca(pk(MEOWTH))
           .mi_mano(BOSS, ULTRA_BALL)
           .op_activo(pk(CRUSTLE))
           .op_banca(pk(DWEBBLE), pk(CRUSTLE))
           .op_zonas(mano=8, mazo=30, premios=6)
           .menu_gusteo().construir())
    idx = obs["select"]["option"][m.agent(obs)[0]]["index"]
    assert obs["current"]["players"][1]["bench"][idx]["id"] != DWEBBLE
