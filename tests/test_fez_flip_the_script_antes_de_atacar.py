"""Flip the Script no se pierde al cerrar el turno atacando.

Escenario (user, episodio 88710037 registro_006 paso 78 vs Archaludon ex,
PERDIDA):

    NOSOTROS                                RIVAL
    activo  Teal Mask Ogerpon ex 210 3e     activo  Archaludon ex 400 3e
    banca   Bayleef, Meowth ex, 2x Applin,  banca   Duraludon 10, Duraludon 130,
            Fezandipiti ex (bajado en el           Fezandipiti ex
            paso 77 con la Ultra Ball)
    mano    Lillie's Determination, Boss's Orders, Bayleef
    premios restantes: 6 - 4     (nos noquearon el Ogerpon ex el turno anterior)

El menu del paso 78 ofrecia CUATRO jugadas: jugar Lillie's, jugar Boss's, la
habilidad **Flip the Script** del Fezandipiti ex recien bajado (robar 3) y
atacar. El agente ATACO, cerrando el turno y tirando el robo. La perdida es
seca e irrecuperable: la habilidad es UNA VEZ POR TURNO y su condicion de
activacion -- que nos noquearan un Pokemon en el turno anterior -- se va con el
turno. Bajar el Fezandipiti ex con una Ultra Ball (dos cartas de coste) para no
cobrar su habilidad deja el turno en numeros rojos.

Causa: un BLOQUEO CIRCULAR entre tres reglas correctas por separado.

  * la habilidad se veta por ORDEN, "primero Lillie's Determination y DESPUES la
    habilidad" (`_lillie_blocks_fez_ability`), para que Lillie's no baraje de
    vuelta las 3 cartas robadas;
  * Lillie's se veta a si misma por ceder a un Boss's ejecutable
    (`cede_a_boss_ejecutable`, -1);
  * y Boss's se degrada a 20 por ceder a Lillie's sin atacante de banca
    (`sin_atacante_banca_cede_a_lillie`).

Ninguna de las tres se juega, el ataque (1100) gana el menu y la habilidad muere.

Arreglo (agnostico del mazo rival: solo mira nuestra mano y el menu). Los vetos
de ORDEN sobre habilidades se registran como DIFERIBLES en
`_ability_order_veto` y el bloque "REVOCAR VETOS DE ORDEN" los levanta cuando el
"primero X" no va a ocurrir:

  (a) ningun bloqueador esta ofrecido y jugable (score > 0) en este menu -- sin X
      jugable no hay "despues de X". Es el caso del paso 78;
  (b) el bloqueador vive pero PIERDE contra atacar/pasar y no queda ninguna otra
      jugada viva -- el turno se cierra en esta misma accion.

Con el bloqueador jugable y mas jugadas vivas el veto se mantiene: se juega
primero el bloqueador y, al salir de la mano, el veto se apaga solo.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import C, G, Escenario, pk

OGERPON = m.Teal_Mask_Ogerpon_ex    # 96: activo del paso 78
FEZ = m.Fezandipiti_ex              # 140: Flip the Script (robar 3)
MEOWTH = m.Meowth_ex
BAYLEEF = m.Bayleef
APPLIN = m.Applin
LILLIE = m.Lillie_Determination     # bloqueador (Supporter)
STAMP = m.Unfair_Stamp              # bloqueador (Item)
BOSS = m.Boss_Orders
TAPU = m.Tapu_Bulu

ARCHALUDON = 190                    # activo rival del registro (400 PV)
DURALUDON = 169

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "fez_flip_the_script_antes_de_atacar_step78.json")


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


def _obs_fixture():
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _jugada(obs, eleccion):
    """('PLAY'|'ABILITY', card_id) / ('ATTACK', attackId) / ('END', None)."""
    o = obs["select"]["option"][eleccion[0]]
    tipo = o["type"]
    yo = obs["current"]["yourIndex"]
    jugador = obs["current"]["players"][yo]
    if tipo == int(m.OptionType.PLAY):
        return ("PLAY", jugador["hand"][o["index"]]["id"])
    if tipo == int(m.OptionType.ABILITY):
        zona = (jugador["active"] if o["area"] == int(m.AreaType.ACTIVE)
                else jugador["bench"])
        return ("ABILITY", zona[o["index"]]["id"])
    if tipo == int(m.OptionType.ATTACK):
        return ("ATTACK", o.get("attackId"))
    if tipo == int(m.OptionType.RETREAT):
        return ("RETREAT", None)
    if tipo == int(m.OptionType.END):
        return ("END", None)
    return (tipo, None)


def _jugadas(obs):
    return [_jugada(obs, [i])
            for i in range(len(obs["select"]["option"]))]


# ---------------------------------------------------------------------------
# El paso 78 real
# ---------------------------------------------------------------------------

def test_paso78_usa_flip_the_script_en_vez_de_atacar():
    obs = _obs_fixture()
    # El fixture debe ofrecer las TRES jugadas para que el test discrimine.
    jugadas = _jugadas(obs)
    assert ("ABILITY", FEZ) in jugadas, jugadas
    assert ("ATTACK", 120) in jugadas, jugadas
    assert ("PLAY", LILLIE) in jugadas, jugadas

    assert _jugada(obs, m.agent(obs)) == ("ABILITY", FEZ)


def test_paso78_el_bloqueo_circular_existe_de_verdad():
    """Documenta el estado que hacia inevitable el error: el bloqueador de la
    habilidad (Lillie's) esta en la mano y ofrecido, pero NO es jugable."""
    obs = _obs_fixture()
    st = m.to_observation_class(obs).current
    mano = [c.id for c in st.players[0].hand]
    assert mano.count(LILLIE) == 1
    assert mano.count(BOSS) == 1
    assert not st.supporterPlayed          # => _lillie_blocks_fez_ability activo
    assert st.players[0].deckCount > 4     # => el freno de deck-out NO aplica

    # Lillie's cede a Boss's y Boss's cede a Lillie's: ninguno se juega.
    eleccion = m.agent(obs)
    assert _jugada(obs, eleccion)[0] != "PLAY"


def test_paso78_la_ventana_exacta_del_bloqueo_circular():
    """Fija la ventana del ctx en la que las dos reglas se ceden el turno, para
    que un cambio futuro en `cede_a_boss_ejecutable` / `_boss_cede_dig` no la
    mueva sin darse cuenta: sin atacante de banca listo, pre-evo AMENAZA
    gusteable y activo condenado SOLO segun `attack_table`.

    Cerrar la asimetria (que `cede_a_boss_ejecutable` mire tambien
    `active_doomed_real`, como hace `_boss_cede_dig`) se MIDIO y salio a -0.39
    puntos con n=7000 por rama en 4 matchups; ver el comentario de la regla en
    main.py. Aqui el turno lo rescata el veto de ORDEN diferible: sin bloqueador
    jugable, Flip the Script cobra el robo de 3."""
    obs = _obs_fixture()
    visto = {}
    orig = m._score_boss_orders_play

    def espia(ctx):
        visto["ctx"] = ctx
        return orig(ctx)

    m._score_boss_orders_play = espia
    try:
        m.agent(obs)
    finally:
        m._score_boss_orders_play = orig

    ctx = visto["ctx"]
    assert ctx.has_ready_bench_attacker is False
    assert ctx.boss_ko_threat_preevo is True
    assert ctx.active_ko_likely is False     # el heuristico CIEGO
    assert ctx.active_doomed_real is True    # el remate REAL de attack_table
    # La asimetria en vivo: Lillie's se veta, Boss's se degrada a la banda de
    # cesion. Ninguna de las dos se juega.
    assert m._score_lillie_determination_play(ctx) == m.SCORE_VETO
    assert m._score_boss_orders_play(ctx) == m.BOSS_SCORE_EMPTY_GUST


def test_paso78_la_habilidad_se_usa_antes_de_cualquier_cierre_de_turno():
    """Recorte del menu a habilidad + ataque + pasar: nunca se cierra el turno
    con Flip the Script disponible."""
    obs = _obs_fixture()
    opciones = obs["select"]["option"]
    idx = [i for i, o in enumerate(opciones)
           if o["type"] in (int(m.OptionType.ABILITY),
                            int(m.OptionType.ATTACK),
                            int(m.OptionType.END))]
    obs["select"]["option"] = [opciones[i] for i in idx]
    assert _jugada(obs, m.agent(obs)) == ("ABILITY", FEZ)


# ---------------------------------------------------------------------------
# Generalizacion sintetica: el ORDEN pedido sigue vivo
# ---------------------------------------------------------------------------

def _escenario(mano, con_ataque=True):
    """Tablero del paso 78 reconstruido con el StateBuilder, mano parametrica.

    Se anade a mano la opcion ABILITY del Fezandipiti ex de banca (slot 4), que
    `menu_mano` no emite, justo antes de los cierres de turno.
    """
    esc = (Escenario(turno=6, paso=78, tac=7)
           .mi_activo(pk(OGERPON, energias=[G, G, G]))
           .mi_banca(pk(BAYLEEF, pre_evo=[m.Chikorita]), MEOWTH, APPLIN,
                     APPLIN, pk(FEZ, aparecio=True))
           .mi_mano(*mano)
           .mi_descarte(m.Ultra_Ball, m.Ultra_Ball, m.Lanas_Aid,
                        m.Basic_Grass_Energy, m.Basic_Grass_Energy,
                        m.Basic_Grass_Energy, OGERPON)
           .op_activo(pk(ARCHALUDON, hp=400, max_hp=400, energias=[C, C, C],
                         pre_evo=[DURALUDON]))
           .op_banca(pk(DURALUDON, hp=130, max_hp=130, energias=[C, C, C]))
           .op_zonas(mano=9, mazo=23, premios=4)
           .menu_mano(con_ataque=con_ataque))
    obs = esc.construir()
    opciones = obs["select"]["option"]
    n_play = sum(1 for o in opciones if o["type"] == int(m.OptionType.PLAY))
    opciones.insert(n_play, {"type": int(m.OptionType.ABILITY),
                             "area": int(m.AreaType.BENCH), "index": 4})
    return obs


def _con_ko_previo(obs):
    """El paso 78 llega despues de que nos noquearan: replica el estado de
    seguimiento que deja `ko_last_turn` encendido."""
    m.ko_last_turn = True
    m._ko_detected_this_turn = True
    m._prev_op_prize = 6
    return obs


def test_sintetico_sin_bloqueador_usa_la_habilidad():
    """Caso (a) en su forma mas simple: sin Lillie's ni Stamp en la mano la
    habilidad se cobra antes de atacar."""
    obs = _con_ko_previo(_escenario([BOSS]))
    assert ("ABILITY", FEZ) in _jugadas(obs)
    assert _jugada(obs, m.agent(obs)) == ("ABILITY", FEZ)


def test_sintetico_unfair_stamp_jugable_manda_primero():
    """El orden pedido NO se rompe: con Unfair Stamp jugable y otra jugada viva
    (Boss's) el Stamp va primero y la habilidad espera al menu siguiente -- si
    no, el Stamp barajaria de vuelta las 3 cartas robadas."""
    obs = _con_ko_previo(_escenario([STAMP, BOSS]))
    jugadas = _jugadas(obs)
    assert ("PLAY", STAMP) in jugadas, jugadas
    assert ("ABILITY", FEZ) in jugadas, jugadas
    assert _jugada(obs, m.agent(obs)) == ("PLAY", STAMP)


def test_sintetico_lillie_jugable_manda_primero():
    """Mismo orden con el otro bloqueador: Lillie's Determination antes que la
    habilidad cuando Lillie's SI es jugable."""
    obs = _con_ko_previo(_escenario([LILLIE]))
    jugadas = _jugadas(obs)
    assert ("PLAY", LILLIE) in jugadas, jugadas
    assert _jugada(obs, m.agent(obs)) == ("PLAY", LILLIE)


def test_sintetico_deck_out_sigue_vetando_la_habilidad():
    """El freno de deck-out es un veto de VALOR, no de ORDEN: la revocacion no
    lo levanta ni con la mano sin bloqueadores."""
    esc = (Escenario(turno=6, paso=78, tac=7)
           .mi_activo(pk(OGERPON, energias=[G, G, G]))
           .mi_banca(pk(FEZ, aparecio=True))
           .mi_mano(BOSS)
           .mazo(TAPU, MEOWTH, APPLIN)          # deckCount = 3 (<= 4)
           .resto_al_descarte()
           .op_activo(pk(ARCHALUDON, hp=400, max_hp=400, energias=[C, C, C],
                         pre_evo=[DURALUDON]))
           .op_zonas(mano=5, mazo=20, premios=4)
           .menu_mano(con_ataque=True))
    obs = esc.construir()
    opciones = obs["select"]["option"]
    n_play = sum(1 for o in opciones if o["type"] == int(m.OptionType.PLAY))
    opciones.insert(n_play, {"type": int(m.OptionType.ABILITY),
                             "area": int(m.AreaType.BENCH), "index": 0})
    _con_ko_previo(obs)
    assert obs["current"]["players"][0]["deckCount"] <= 4
    assert ("ABILITY", FEZ) in _jugadas(obs)
    assert _jugada(obs, m.agent(obs)) != ("ABILITY", FEZ)
