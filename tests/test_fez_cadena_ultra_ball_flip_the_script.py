"""La cadena Ultra Ball -> Fezandipiti ex -> Flip the Script se COMPLETA.

Escenario (user, episodio 88710543 registro_006 turno 6 vs Mega Lucario,
GANADA -- pero por suerte):

    NOSOTROS                                 RIVAL
    activo  Hydrapple ex 330 2e              activo  Mega Lucario ex 340 2e
    banca   Meowth ex, Meganium, 2x          banca   2x Riolu, Lucario, Riolu
            Ogerpon ex
    premios restantes: 3 - 4    (nos noquearon el turno anterior: Flip the
                                 Script esta VIVA)

Secuencia registrada (pasos 86-104):

    Poke Pad -> Applin | Ultra Ball (descarta Meganium + Applin) -> **busca
    Fezandipiti ex** | **Unfair Stamp** (baraja la mano al mazo: el Fezandipiti
    recien cavado se va con ella) | Bug Catching Set | baja el Fezandipiti (que
    volvio por SUERTE entre las 5 cartas del Sello) | Teal Dance | Ripening
    Charge | Teal Dance | atacar.

Dos errores, los dos con la misma raiz "una jugada gratis que muere con el
turno":

1. PASO 91 -- el Unfair Stamp BARAJO al mazo el Fezandipiti ex que la Ultra
   Ball acababa de pagar con dos cartas (Meganium + Applin al descarte). Causa:
   un BLOQUEO CIRCULAR de tres reglas correctas por separado:
     * bajar el Fezandipiti se vetaba por el veto de ORDEN de Req H
       (`_lucario_riolu_gust`: "vs Mega Lucario con un Riolu gusteable, cede la
       jugada al Boss's"),
     * el Boss's se vetaba por `cede_a_unfair_stamp` ("primero el Sello, que
       baraja la mano"),
     * y el Sello se quedaba en 2000 por `mano_con_pokemon_o_evo` ("primero baja
       el Pokemon de la mano").
   Ganaba el Sello por descarte y se llevaba al mazo el Fezandipiti Y el propio
   Boss's al que Req H le cedia el turno.
   Arreglo: (a) el veto de Req H EXIME a Fezandipiti ex con la habilidad viva --
   es un Pokemon, no consume el Supporter del turno, asi que no compite con el
   Boss's; y (b) `_ub_fez_pending`, hermano de `_ub_meowth_pending`: si la Ultra
   Ball ELIGIO buscar Fezandipiti ex, el cuerpo BAJA aunque otro veto lo mate.

2. PASOS 95-102 -- Flip the Script se ofrecio en CUATRO menus y no se uso nunca:
   con 30000 perdia contra Teal Dance (31300) y Ripening Charge (31100) menu
   tras menu, y el turno se cerro atacando. El robo de 3 es GRATIS, es UNA VEZ
   POR TURNO y su condicion (que nos noquearan) muere con el turno, mientras que
   un adjunte que no remata se puede hacer despues sin perder nada. Ademas robar
   PRIMERO decide mejor los adjuntes (las 3 cartas pueden ser Plantas).
   Arreglo: `FEZ_DRAW_ABILITY_SCORE` = 31700 (sobre toda la familia de cargas no
   letales) + promocion al tier ENERGY para que ninguna carga la pise por ORDEN.

Lo que NO cambia: el orden Unfair Stamp / Lillie's -> habilidad (el Sello
barajaria las 3 cartas robadas), el freno de deck-out, las bandas LETALES de
Teal Dance / Ripening (41000+: la habilidad que habilita el KO de HOY sigue
primero) y el remate GANADOR (paso 102: si la partida se cierra este turno,
robar 3 no aporta nada).
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

FEZ = m.Fezandipiti_ex          # 140: Flip the Script (robar 3)
HYDRA = m.Hydrapple_ex          # 150: Ripening Charge
OGERPON = m.Teal_Mask_Ogerpon_ex  # 96: Teal Dance
MEOWTH = m.Meowth_ex
MEGANIUM = m.Meganium
CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
APPLIN = m.Applin
DIPPLIN = m.Dipplin
STAMP = m.Unfair_Stamp
LILLIE = m.Lillie_Determination
BOSS = m.Boss_Orders
DAWN = m.Dawn
GRASS = m.Basic_Grass_Energy

MEGA_LUCARIO = 678              # activo rival del registro (340 PV)
RIOLU = m.Riolu

_FIX = ROOT / "tests" / "fixtures"
_FIX_STEP91 = _FIX / "fez_ub_baja_el_cuerpo_antes_del_stamp_step91.json"
_FIX_STEP95 = _FIX / "fez_flip_the_script_antes_de_cargar_energia_step95.json"
_FIX_STEP102 = _FIX / "fez_remate_ganador_sobre_flip_the_script_step102.json"
_REGISTRO = ROOT / "registros" / "registro_006_pasos_086_hasta_104.json"


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
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _obs(fixture):
    with open(fixture, encoding="utf-8") as f:
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
    if tipo == int(m.OptionType.ATTACH):
        return ("ATTACH", jugador["hand"][o["index"]]["id"])
    if tipo == int(m.OptionType.ATTACK):
        return ("ATTACK", o.get("attackId"))
    if tipo == int(m.OptionType.RETREAT):
        return ("RETREAT", None)
    if tipo == int(m.OptionType.END):
        return ("END", None)
    return (tipo, None)


def _jugadas(obs):
    return [_jugada(obs, [i]) for i in range(len(obs["select"]["option"]))]


def _menus_del_registro():
    """Los menus de NUESTRO asiento (yourIndex 1) del registro, en orden."""
    with open(_REGISTRO, encoding="utf-8") as f:
        data = json.load(f)
    return [e["observation"] for paso in data["steps"] for e in paso
            if e["status"] in ("ACTIVE", "DONE")
            and e["observation"]["current"]["yourIndex"] == 1]


# ---------------------------------------------------------------------------
# 1. Paso 91: el cuerpo que pago la Ultra Ball baja ANTES del Unfair Stamp
# ---------------------------------------------------------------------------

def test_paso91_baja_el_fezandipiti_antes_del_unfair_stamp():
    obs = _obs(_FIX_STEP91)
    jugadas = _jugadas(obs)
    # El menu real ofrecia las dos jugadas en competencia.
    assert ("PLAY", FEZ) in jugadas, jugadas
    assert ("PLAY", STAMP) in jugadas, jugadas
    assert _jugada(obs, m.agent(obs)) == ("PLAY", FEZ)


def test_paso91_el_bloqueo_circular_existe_de_verdad():
    """Documenta el estado que lo hacia inevitable: Boss's en mano sin jugar
    (Req H activo), Unfair Stamp jugable (nos noquearon) y banca con hueco."""
    obs = _obs(_FIX_STEP91)
    st = m.to_observation_class(obs).current
    yo = st.players[st.yourIndex]
    mano = [c.id for c in yo.hand]
    assert mano.count(STAMP) == 1
    assert mano.count(BOSS) == 1
    assert mano.count(FEZ) == 1
    assert not st.supporterPlayed
    assert len(yo.bench) == 4                      # queda hueco para el Fez
    assert any(bp.id == RIOLU for bp in st.players[1 - st.yourIndex].bench)
    m.agent(obs)
    assert m.ko_last_turn is True                  # Flip the Script VIVA


@pytest.mark.skipif(
    not _REGISTRO.exists(),
    reason=("necesita la SECUENCIA de menus del registro (episodio 88710543), "
            "que es dato local transitorio: `utils/split_turns.py` lo "
            "reescribe con cada partida nueva. COBERTURA YA RESTITUIDA en "
            "tests/test_fez_pending_sintetico.py, que fabrica la secuencia con "
            "el StateBuilder (y por tanto es inmune a la rotacion). Este test "
            "se conserva por si el episodio vuelve a estar en disco."))
def test_turno_completo_la_ultra_ball_deja_el_fezandipiti_pendiente():
    """Punta a punta sobre el registro: la Ultra Ball elige Fezandipiti ex, eso
    fija `_ub_fez_pending`, y el menu siguiente lo BAJA (antes se jugaba el
    Sello y el cuerpo volvia al mazo)."""
    menus = _menus_del_registro()
    elecciones = []
    for obs in menus[:6]:
        elecciones.append((obs["select"]["context"], m.agent(obs)))
    # menu 4 = seleccion de la Ultra Ball (context TO_HAND): busca Fezandipiti.
    ub = menus[4]
    idx = elecciones[4][1][0]
    assert ub["select"]["effect"]["id"] == m.Ultra_Ball
    assert ub["select"]["deck"][ub["select"]["option"][idx]["index"]]["id"] == FEZ
    assert m._ub_fez_pending is True
    # menu 5 = menu principal siguiente: el cuerpo baja.
    assert _jugada(menus[5], elecciones[5][1]) == ("PLAY", FEZ)


# ---------------------------------------------------------------------------
# 2. Pasos 95-102: la habilidad se cobra antes de gastar la energia del turno
# ---------------------------------------------------------------------------

def test_paso95_flip_the_script_antes_de_teal_dance_y_ripening():
    obs = _obs(_FIX_STEP95)
    jugadas = _jugadas(obs)
    assert ("ABILITY", FEZ) in jugadas, jugadas
    assert ("ABILITY", OGERPON) in jugadas, jugadas     # Teal Dance
    assert ("ABILITY", HYDRA) in jugadas, jugadas       # Ripening Charge
    assert ("ATTACH", GRASS) in jugadas, jugadas
    assert _jugada(obs, m.agent(obs)) == ("ABILITY", FEZ)


def test_paso95_la_banda_esta_por_encima_de_las_cargas_no_letales():
    """El robo va primero por SCORE y por TIER: si se quedara en tier 0
    cualquier Teal Dance / Ripening promovida lo pisaria por ORDEN."""
    assert m.FEZ_DRAW_ABILITY_SCORE > m.RIPEN_HEAL_ABILITY_SCORE
    assert m.FEZ_DRAW_ABILITY_SCORE > 31600      # tope de las cargas de banca
    assert m.FEZ_DRAW_ABILITY_SCORE < 41000      # bandas LETALES intactas


def test_paso102_el_remate_ganador_sigue_por_encima_del_robo():
    """La UNICA excepcion: con la partida ganada este turno (3 premios y el
    Syrup Storm noquea al Mega Lucario ex) atacar va primero -- robar 3 no
    cambia nada."""
    obs = _obs(_FIX_STEP102)
    jugadas = _jugadas(obs)
    assert ("ABILITY", FEZ) in jugadas, jugadas
    assert _jugada(obs, m.agent(obs)) == ("ATTACK", 195)


# ---------------------------------------------------------------------------
# 3. Generalizacion sintetica
# ---------------------------------------------------------------------------

def _escenario_lucario(mano, con_ataque=True):
    """Tablero del paso 91 reconstruido con el StateBuilder, mano parametrica."""
    esc = (Escenario(turno=6, paso=91, tac=6)
           .mi_activo(pk(HYDRA, energias=[G, G], pre_evo=[APPLIN, DIPPLIN]))
           .mi_banca(MEOWTH, pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
                     pk(OGERPON, energias=[G]), OGERPON)
           .mi_mano(*mano)
           .op_activo(pk(MEGA_LUCARIO, hp=340, max_hp=340, energias=[C, C],
                         pre_evo=[RIOLU]))
           .op_banca(RIOLU, RIOLU)
           .op_zonas(mano=6, mazo=23, premios=4)
           .menu_mano(con_ataque=con_ataque))
    obs = esc.construir()
    # El paso 91 llega despues de que nos noquearan: replica el seguimiento.
    m.ko_last_turn = True
    m._ko_detected_this_turn = True
    m._prev_op_prize = 6
    return obs


def test_sintetico_req_h_ya_no_veta_el_fezandipiti_con_la_habilidad_viva():
    """Con Boss's en mano (Req H activo) y un Riolu en la banca rival, bajar el
    Fezandipiti ex ya NO se veta: no consume el Supporter, asi que el Boss's se
    juega igual despues."""
    obs = _escenario_lucario([FEZ, BOSS])
    assert ("PLAY", FEZ) in _jugadas(obs)
    assert _jugada(obs, m.agent(obs)) == ("PLAY", FEZ)


def test_sintetico_req_h_sigue_vetando_el_desarrollo_normal():
    """El veto de Req H no se ha desactivado: un cuerpo de desarrollo (Chikorita)
    sigue cediendo la jugada al Boss's."""
    obs = _escenario_lucario([CHIKORITA, BOSS])
    jugadas = _jugadas(obs)
    assert ("PLAY", CHIKORITA) in jugadas, jugadas
    assert _jugada(obs, m.agent(obs)) != ("PLAY", CHIKORITA)


def _escenario_teal_lillie(mano):
    """Tablero con UN solo Ogerpon ex en juego: con Lillie's + Ogerpon ex +
    Planta en la mano se enciende `_fez_prefer_teal_lillie`, que veta bajar el
    Fezandipiti para preferir Teal + Teal Dance + Lillie's."""
    esc = (Escenario(turno=6, paso=91, tac=6)
           .mi_activo(pk(HYDRA, energias=[G, G], pre_evo=[APPLIN, DIPPLIN]))
           .mi_banca(MEOWTH, pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
                     pk(OGERPON, energias=[G]))
           .mi_mano(*mano)
           .op_activo(pk(MEGA_LUCARIO, hp=340, max_hp=340, energias=[C, C],
                         pre_evo=[RIOLU]))
           .op_banca(RIOLU, RIOLU)
           .op_zonas(mano=6, mazo=23, premios=4)
           .menu_mano(con_ataque=True))
    obs = esc.construir()
    m.ko_last_turn = True
    m._ko_detected_this_turn = True
    m._prev_op_prize = 6
    return obs


def test_sintetico_ub_fez_pending_completa_la_busqueda_pagada():
    """`_fez_prefer_teal_lillie` (Lillie's + Ogerpon ex + Planta en mano) veta
    bajar el Fezandipiti... salvo que la Ultra Ball lo acabe de pagar."""
    obs = _escenario_teal_lillie([FEZ, LILLIE, OGERPON, GRASS])
    assert ("PLAY", FEZ) in _jugadas(obs)
    assert _jugada(obs, m.agent(obs)) != ("PLAY", FEZ)

    obs = _escenario_teal_lillie([FEZ, LILLIE, OGERPON, GRASS])
    m._ub_fez_pending = True
    assert _jugada(obs, m.agent(obs)) == ("PLAY", FEZ)


def test_sintetico_pending_no_rompe_los_limites_fisicos():
    """El override no llena una banca ya completa (limite FISICO)."""
    esc = (Escenario(turno=6, paso=91, tac=6)
           .mi_activo(pk(HYDRA, energias=[G, G], pre_evo=[APPLIN, DIPPLIN]))
           .mi_banca(MEOWTH, pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
                     pk(OGERPON, energias=[G]), OGERPON, APPLIN)
           .mi_mano(FEZ, DAWN)
           .op_activo(pk(MEGA_LUCARIO, hp=340, max_hp=340, energias=[C, C],
                         pre_evo=[RIOLU]))
           .op_banca(RIOLU)
           .op_zonas(mano=6, mazo=23, premios=4)
           .menu_mano(con_ataque=True))
    obs = esc.construir()
    m.ko_last_turn = True
    m._ko_detected_this_turn = True
    m._prev_op_prize = 6
    m._ub_fez_pending = True
    assert len(obs["current"]["players"][0]["bench"]) == 5
    assert _jugada(obs, m.agent(obs)) != ("PLAY", FEZ)
