"""La energia del DESCARTE que paga la retirada del activo y libera el remate.

Escenario (user, registro_021 turno 21, log 88359220): el ACTIVO no puede
atacar y ni siquiera puede RETIRARSE (0 energias, coste 1), pero en la banca
espera un atacante YA LISTO que noquea al activo rival. La unica Planta esta en
el DESCARTE y tenemos una Night Stretcher en la mano. La jugada correcta es la
cadena de cinco pasos:

    Night Stretcher -> Planta a la mano -> adjuntar al ACTIVO -> RETIRAR ->
    promover al rematador -> KO

El agente cerraba el turno (END). Causa: `_ns_e_activo_paga_retirada` -- el
detector deck-agnostico de esa linea -- solo estaba cableado al corte de BANCA
LLENA (`_ns_banca_llena_guardar`), nunca a `_ESC_NS_RECUPERACION`, que es la
lista que produce el SCORE. Con la banca no llena el ARGMAX daba 0 y el scorer
de la Night Stretcher devolvia SCORE_VETO.

Los tests son deck-agnosticos a proposito: el caso que fallaba usa un rematador
de banca SIN habilidad de carga (Tapu Bulu), porque con un Teal Mask Ogerpon ex
en juego la Night Stretcher se jugaba igual por CASUALIDAD, via el escenario
`energia_activo_sin_teal` -- que no tiene nada que ver con la retirada.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import G, Escenario, pk

FEZANDIPITI = m.Fezandipiti_ex     # activo bloqueado: 0 energias, coste 1
TAPU = m.Tapu_Bulu                 # rematador de banca SIN habilidad de carga
OGERPON = m.Teal_Mask_Ogerpon_ex
MEOWTH = m.Meowth_ex
NIGHT_STRETCHER = m.Night_Stretcher
ULTRA_BALL = m.Ultra_Ball
GRASS = m.Basic_Grass_Energy

COMFEY = 164                       # 70 PV: Wood Hammer (220) lo noquea


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


def _escenario(mano, banca=None, energia_activo=0, descarte=(GRASS, GRASS),
               energia_jugada=False, retirado=False, op_hp=70):
    banca = banca if banca is not None else [pk(TAPU, energias=[G, G, G, G]),
                                             pk(MEOWTH)]
    return (Escenario(turno=12, paso=40, energia_jugada=energia_jugada,
                      retirado=retirado)
            .mi_activo(pk(FEZANDIPITI, energias=[G] * energia_activo))
            .mi_banca(*banca)
            .mi_mano(*mano)
            .mi_descarte(*descarte)
            .op_activo(pk(COMFEY, hp=op_hp))
            .op_zonas(mano=5, mazo=20, premios=3))


def _elegida(obs, eleccion, mano):
    o = obs["select"]["option"][eleccion[0]]
    if o["type"] == int(m.OptionType.PLAY):
        return ("PLAY", mano[o["index"]])
    if o["type"] == int(m.OptionType.END):
        return ("END", None)
    if o["type"] == int(m.OptionType.RETREAT):
        return ("RETREAT", None)
    if o["type"] == int(m.OptionType.ATTACH):
        return ("ATTACH", o["inPlayArea"])
    return (o["type"], None)


# ---------------------------------------------------------------------------
# Paso 1: jugar la carta que trae la energia
# ---------------------------------------------------------------------------

def test_night_stretcher_se_juega_para_pagar_la_retirada():
    """El caso del registro: sin Planta en mano y con el remate en la mesa, la
    Night Stretcher se juega en vez de terminar el turno."""
    mano = [NIGHT_STRETCHER, ULTRA_BALL]
    obs = _escenario(mano).menu_mano().construir()
    assert _elegida(obs, m.agent(obs), mano) == ("PLAY", NIGHT_STRETCHER)


def test_deck_agnostico_el_rematador_no_necesita_habilidad_de_carga():
    """Con un Teal Mask Ogerpon ex de banca la jugada ya salia bien por
    casualidad (escenario `energia_activo_sin_teal`). La regla debe valer
    igual con un rematador cualquiera -- aqui, ambos."""
    for banca in ([pk(TAPU, energias=[G, G, G, G]), pk(MEOWTH)],
                  [pk(OGERPON, energias=[G, G, G]), pk(MEOWTH)]):
        m._init_cartas_tracking()
        m._cartas_first_scan_done = False
        m._field_at_turn_start = {}
        mano = [NIGHT_STRETCHER, ULTRA_BALL]
        obs = _escenario(mano, banca=banca).menu_mano().construir()
        assert _elegida(obs, m.agent(obs), mano) == ("PLAY", NIGHT_STRETCHER)


def test_sin_energia_en_el_descarte_no_se_gasta_la_night_stretcher():
    """Frontera: si en el descarte no queda ninguna Planta, la cadena no existe
    y la Night Stretcher no debe jugarse por esta regla."""
    mano = [NIGHT_STRETCHER, ULTRA_BALL]
    obs = _escenario(mano, descarte=(ULTRA_BALL, ULTRA_BALL)).menu_mano().construir()
    assert _elegida(obs, m.agent(obs), mano) != ("PLAY", NIGHT_STRETCHER)


def test_con_planta_ya_en_mano_la_cadena_no_necesita_la_night_stretcher():
    """Frontera: con la Planta ya en la mano el eslabon inicial sobra; manda el
    adjunte al ACTIVO (`_attach_enable_retreat_ko`, 41000)."""
    mano = [NIGHT_STRETCHER, GRASS]
    obs = _escenario(mano).menu_mano(con_adjunte=True).construir()
    tipo, destino = _elegida(obs, m.agent(obs), mano)
    assert tipo == "ATTACH" and destino == int(m.AreaType.ACTIVE)


# ---------------------------------------------------------------------------
# Pasos 2-5: la cadena completa
# ---------------------------------------------------------------------------

def test_la_night_stretcher_recupera_la_energia_y_no_un_pokemon():
    obs = (_escenario([ULTRA_BALL], descarte=(GRASS, GRASS, ULTRA_BALL))
           .fetch_descarte(NIGHT_STRETCHER).construir())
    eleccion = m.agent(obs)
    idx = obs["select"]["option"][eleccion[0]]["index"]
    assert obs["current"]["players"][0]["discard"][idx]["id"] == GRASS


def test_la_planta_recuperada_va_al_activo_no_a_la_banca():
    mano = [GRASS, ULTRA_BALL]
    obs = _escenario(mano).menu_mano(con_adjunte=True).construir()
    tipo, destino = _elegida(obs, m.agent(obs), mano)
    assert tipo == "ATTACH" and destino == int(m.AreaType.ACTIVE)


def test_con_la_energia_puesta_se_retira():
    mano = [ULTRA_BALL]
    obs = (_escenario(mano, energia_activo=1, energia_jugada=True)
           .menu_mano(con_retirada=True).construir())
    assert _elegida(obs, m.agent(obs), mano) == ("RETREAT", None)


# ---------------------------------------------------------------------------
# Umbral de energia util sobre el ACTIVO (`_ns_umbral_energia_util`)
# ---------------------------------------------------------------------------

def _umbral_viejo(cid, e):
    """Copia LITERAL de la cadena de `if act.id == ...` que habia antes de
    extraer el umbral a tablas. Es el oraculo de la equivalencia."""
    eff = e * m._grass_mult()
    if cid == m.Hydrapple_ex:
        return eff < 2 and e < 2
    if cid == m.Dipplin:
        return e < 1
    if cid == m.Teal_Mask_Ogerpon_ex:
        return eff < 3 and e < 3
    if cid == m.Tapu_Bulu:
        return eff < 4 and e < 4
    if cid == m.Pinsir:
        return eff < 2 and e < 2
    if cid in (m.Chikorita, m.Bayleef, m.Meganium):
        return e < m.RETREAT_COST.get(cid, 1)
    return False


def _umbral_nuevo(cid, e):
    umbral = m._ns_umbral_energia_util(cid)
    if umbral is None:
        return False
    return (e * m._grass_mult()) < umbral and e < umbral


@pytest.mark.parametrize("card_id", sorted(m._DECK_POKEMON_IDS))
def test_umbral_equivale_al_original_para_todo_el_mazo(card_id):
    """El refactor a tablas + fallback NO cambia ni una decision del mazo
    actual: se compara contra el oraculo para 0..10 energias."""
    for e in range(11):
        assert _umbral_nuevo(card_id, e) == _umbral_viejo(card_id, e), (
            f"flip en {card_id} con {e} energias")


def test_cuerpos_del_mazo_excluidos_siguen_excluidos():
    """Meowth ex y Fezandipiti ex TIENEN ataque, pero la configuracion curada
    los deja fuera a proposito (cuerpos de utilidad). El fallback por dato de
    carta no debe resucitarlos."""
    for cid in (m.Meowth_ex, m.Fezandipiti_ex):
        assert m._coste_de_ataque_min(cid) is not None   # si tienen ataque...
        assert m._ns_umbral_energia_util(cid) is None    # ...pero no cuentan


def test_cuerpo_fuera_del_mazo_usa_el_dato_de_carta():
    """La rama deck-agnostica: un cuerpo que la configuracion no conoce deja de
    devolver False a ciegas y razona con el coste real de su ataque."""
    crustle = 345
    assert crustle not in m._DECK_POKEMON_IDS
    assert m._ns_umbral_energia_util(crustle) == m._coste_de_ataque_min(crustle)
    assert m._ns_umbral_energia_util(crustle) > 0


def test_coste_de_ataque_min_desconocido_es_none():
    """Sin dato de carta no se inventa un umbral."""
    assert m._coste_de_ataque_min(-12345) is None
    assert m._ns_umbral_energia_util(-12345) is None


def test_tras_retirar_se_promueve_al_rematador():
    obs = (_escenario([ULTRA_BALL], energia_activo=1, energia_jugada=True,
                      retirado=True)
           .promocion_desde_banca().construir())
    eleccion = m.agent(obs)
    idx = obs["select"]["option"][eleccion[0]]["index"]
    assert obs["current"]["players"][0]["bench"][idx]["id"] == TAPU
