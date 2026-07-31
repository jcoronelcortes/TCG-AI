"""Cruel Arrow: el mejor objetivo NO siempre es el activo rival.

Escenario (user, episodio 88714320 registro_004 paso 54 vs Alakazam, turno 4):

    NOSOTROS                                  RIVAL
    activo  Fezandipiti ex 210, 4 efectivas   activo  Alakazam 140/140
    banca   Meowth ex, 3x Ogerpon ex (2e),    banca   Kadabra 80, Kadabra 80,
            Meganium (recien evolucionado)            Abra 50, Dunsparce 70
    mano    Dipplin, Night Stretcher, Grass, Unfair Stamp, Ultra Ball, Tapu Bulu
    energyAttached: SI     Teal Dance de los TRES Ogerpon: YA usada

El menu ofrecia PLAY / ATTACK(183 = Cruel Arrow) / RETREAT / END. El agente
RETIRO al Fezandipiti ex -- descartando su energia -- para promover un Ogerpon
que ni siquiera podia atacar, y cerro el turno sin hacer nada.

Cruel Arrow hace 100 FIJOS a UNO CUALQUIERA de los Pokemon del rival, activo o
banca ("no apliques Debilidad y Resistencia a los Pokemon en Banca"). No llegaba
al Alakazam de 140 PV, pero NOQUEABA a un Kadabra de 80 en la banca: un premio
gratis, sin coste de retirada y sin exponer otro cuerpo.

Dos causas, las dos arregladas:

  1. TODO el planificador media el ataque del ACTIVO contra el ACTIVO rival.
     `_active_can_ko_now` (scorer de retirada) y `_active_already_kos` daban
     False, el turno parecia esteril y los pivotes de retirada ganaban el menu.
     Arreglo: `_snipe_best_target` evalua a TODOS los Pokemon rivales y sus tres
     consumidores nuevos -- `_active_snipe_ko_now` (el activo SI puede noquear,
     luego no se retira), `_snipe_attack_wins_now` (el snipe tambien cierra la
     partida) y la banda 8500+ del ATTACK -- lo propagan. Es la MISMA funcion de
     ranking (`_snipe_target_score`) que usa el menu de DAMAGE al elegir el
     objetivo real, asi que las dos escalas no pueden divergir.

  2. Quien gano el menu fue `_ogerpon_lethal_promote` (8900): "retirar y subir
     un Ogerpon que con Teal Dance llega a 3 energias y remata". Pero la Planta
     era INALCANZABLE -- el adjunte manual ya estaba gastado y los tres Ogerpon
     habian usado su Teal Dance ese turno --, asi que el remate no existia. El
     detector ahora exige `_grass_attach_route_open`.

Cuando el pivote de banca SI es real, la regla no lo pisa a ciegas: el snipe
solo cede ante un KO de MAS premios (aqui Alakazam es no-ex, 1 premio = el
Kadabra, asi que atacar gana).
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

FEZ = m.Fezandipiti_ex          # 140: activo, Cruel Arrow (100 a cualquiera)
OGERPON = m.Teal_Mask_Ogerpon_ex
ALAKAZAM = 743                  # activo rival, 140 PV, NO-ex (1 premio)
KADABRA = 742                   # banca rival, 80 PV  <- el objetivo correcto
ABRA = 741                      # banca rival, 50 PV
DUNSPARCE = 305                 # banca rival, 70 PV
CRUEL_ARROW = 183

_FIX_MAIN = ROOT / "tests" / "fixtures" / "fez_cruel_arrow_remata_banca_step54.json"
_FIX_DMG = ROOT / "tests" / "fixtures" / "fez_cruel_arrow_objetivo_banca_step54.json"


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


def _obs(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _jugada(obs, eleccion):
    o = obs["select"]["option"][eleccion[0]]
    tipo = o["type"]
    if tipo == int(m.OptionType.ATTACK):
        return ("ATTACK", o.get("attackId"))
    if tipo == int(m.OptionType.RETREAT):
        return ("RETREAT", None)
    if tipo == int(m.OptionType.END):
        return ("END", None)
    if tipo == int(m.OptionType.PLAY):
        yo = obs["current"]["yourIndex"]
        return ("PLAY", obs["current"]["players"][yo]["hand"][o["index"]]["id"])
    return (tipo, None)


def _pk_elegido(obs, eleccion):
    """Pokemon rival senalado por la opcion `eleccion` del menu de DAMAGE."""
    o = obs["select"]["option"][eleccion[0]]
    rival = obs["current"]["players"][o["playerIndex"]]
    zona = rival["active"] if o["area"] == int(m.AreaType.ACTIVE) else rival["bench"]
    return zona[o["index"]]


# ---------------------------------------------------------------------------
# El paso 54 real
# ---------------------------------------------------------------------------

def _menu_paso54():
    """La observacion del paso 54 (turno 4, accion 23) con el ESTADO DE TURNO
    ya avanzado.

    Antes esto se obtenia reproduciendo el turno entero desde el registro; los
    registros son datos locales transitorios (salida de `utils/split_turns.py`)
    y el test se rompia en cuanto el usuario cargaba una partida nueva. Lo unico
    que aportaba el replay era el acumulador `_grass_attaches_this_turn`, que se
    monta desde los logs ATTACH paso a paso y es lo que sabe si queda alguna via
    de carga viva. Aqui se inyecta explicitamente -- y ademas queda a la vista
    cual es el dato que hace el escenario: **4 Plantas ya puestas este turno**
    (1 adjunte manual + las 3 Teal Dance de los tres Ogerpon), o sea ninguna
    ruta abierta. `pre_turn` se fija al turno en curso para que `agent()` no
    tome esta observacion por el inicio de un turno nuevo y reinicie el
    contador.
    """
    obs = _obs(_FIX_MAIN)
    m.pre_turn = obs["current"]["turn"]
    m._grass_attaches_this_turn = 4
    return obs


def test_paso54_ataca_con_cruel_arrow_en_vez_de_retirarse():
    obs = _menu_paso54()
    # El menu debe ofrecer las dos jugadas para que el test discrimine.
    jugadas = [_jugada(obs, [i]) for i in range(len(obs["select"]["option"]))]
    assert ("ATTACK", CRUEL_ARROW) in jugadas, jugadas
    assert ("RETREAT", None) in jugadas, jugadas

    assert _jugada(obs, m.agent(obs)) == ("ATTACK", CRUEL_ARROW)


def test_paso54_el_remate_del_ogerpon_era_imposible():
    """La retirada gano el menu por un KO que NO existia: quedaba una Planta en
    la mano, pero ninguna via para ponerla en el campo."""
    obs = _menu_paso54()
    st = m.to_observation_class(obs).current
    yo = st.players[1]

    assert st.energyAttached is True                  # adjunte manual gastado
    assert m._grass_attaches_this_turn == 4           # 1 manual + 3 Teal Dance
    assert sum(1 for p in yo.bench if p is not None
               and p.id == OGERPON) == 3              # las 3 Teal Dance usadas
    assert m._grass_attach_route_open(st, {OGERPON: 3}) is False
    assert any(c.id == m.Basic_Grass_Energy for c in yo.hand)


def test_paso54_cruel_arrow_no_llega_al_activo_pero_si_a_la_banca():
    """El estado que hacia inevitable el error: medido contra el ACTIVO rival el
    turno es esteril, medido contra TODO el campo rival hay un premio."""
    obs = _menu_paso54()
    st = m.to_observation_class(obs).current
    activo = st.players[1].active[0]
    rival = st.players[0]

    assert activo.id == FEZ
    assert len(activo.energies) >= 3                  # Cruel Arrow disponible
    assert rival.active[0].id == ALAKAZAM
    assert rival.active[0].hp == 140                  # 100 NO lo noquea
    assert any(p is not None and p.id == KADABRA and p.hp == 80
               for p in rival.bench)                  # 100 SI lo noquea

    objetivo, dano, es_ko = m._snipe_best_target(activo, rival, len(activo.energies),
                                                 m.meganium_in_play, False)
    assert (objetivo.id, dano, es_ko) == (KADABRA, 100, True)


# ---------------------------------------------------------------------------
# El menu de DAMAGE: a quien apunta la flecha
# ---------------------------------------------------------------------------

def test_cruel_arrow_apunta_al_kadabra_no_al_activo():
    obs = _obs(_FIX_DMG)
    elegido = _pk_elegido(obs, m.agent(obs))
    assert (elegido["id"], elegido["hp"]) == (KADABRA, 80)


def test_cruel_arrow_prefiere_el_kadabra_sobre_abra_y_dunsparce():
    """Entre los tres cuerpos que mueren, el mas desarrollado (Fase 1, 80 PV)."""
    obs = _obs(_FIX_DMG)
    rival = obs["current"]["players"][0]
    hp = {p["id"]: p["hp"] for p in rival["bench"]}
    assert hp[ABRA] == 50 and hp[DUNSPARCE] == 70 and hp[KADABRA] == 80

    from main import _snipe_target_score as sc
    st = m.to_observation_class(obs).current.players[0]
    por_id = {p.id: p for p in st.bench if p is not None}
    assert sc(100, por_id[KADABRA]) > sc(100, por_id[DUNSPARCE])
    assert sc(100, por_id[DUNSPARCE]) > sc(100, por_id[ABRA])
    # El activo, que sobrevive, queda por debajo de cualquier KO.
    assert sc(100, st.active[0]) < sc(100, por_id[ABRA])


# ---------------------------------------------------------------------------
# El evaluador del snipe, aislado
# ---------------------------------------------------------------------------

def test_snipe_sin_energia_no_propone_nada():
    obs = _obs(_FIX_DMG)
    st = m.to_observation_class(obs).current
    activo = st.players[1].active[0]
    activo.energies = activo.energies[:2]             # Cruel Arrow cuesta 3
    assert m._snipe_best_target(activo, st.players[0], 2,
                                False, False) == (None, 0, False)


def test_snipe_solo_para_atacantes_que_eligen_objetivo():
    """Un Ogerpon ex no snipea: su Myriad Leaf Shower golpea solo al activo."""
    obs = _obs(_FIX_DMG)
    st = m.to_observation_class(obs).current
    ogerpon = next(p for p in st.players[1].bench if p is not None and p.id == OGERPON)
    assert m._snipe_best_target(ogerpon, st.players[0], 6,
                                False, False) == (None, 0, False)


def test_snipe_respeta_la_inmunidad_a_ex():
    """Fezandipiti ex es ex: contra un muro que inmuniza a nuestros ex el snipe
    hace 0 y no propone ningun KO (el chip sigue eligiendo el menos malo)."""
    obs = _obs(_FIX_DMG)
    st = m.to_observation_class(obs).current
    activo = st.players[1].active[0]
    rival = st.players[0]
    inmune = next(iter(m.EX_IMMUNE_IDS))
    for p in [rival.active[0]] + [b for b in rival.bench if b is not None]:
        p.id = inmune
    objetivo, dano, es_ko = m._snipe_best_target(activo, rival,
                                                 len(activo.energies),
                                                 m.meganium_in_play, False)
    assert dano == 0 and es_ko is False


# ---------------------------------------------------------------------------
# El fixture de una sola llamada (mismo veredicto sin replay)
# ---------------------------------------------------------------------------

def test_fixture_paso54_ataca():
    obs = _obs(_FIX_MAIN)
    assert _jugada(obs, m.agent(obs)) == ("ATTACK", CRUEL_ARROW)


def test_fixture_paso54_no_se_retira_aunque_el_ogerpon_pareciera_letal():
    """Aunque la via de la Planta estuviera abierta, el pivote del Ogerpon no
    puede pisar al snipe: Alakazam es NO-ex, o sea el MISMO premio que el
    Kadabra, y atacar no paga coste de retirada ni expone otro cuerpo."""
    obs = copy.deepcopy(_obs(_FIX_MAIN))
    obs["current"]["energyAttached"] = False          # adjunte manual libre
    assert _jugada(obs, m.agent(obs)) == ("ATTACK", CRUEL_ARROW)


def test_el_snipe_cede_ante_un_ko_de_mas_premios_sin_cerrar_el_turno():
    """El snipe manda sobre las jugadas de relleno, no sobre un KO mayor.

    Con un ex de 2 premios delante (Archaludon ex, 300 PV: Cruel Arrow no llega)
    y un Ogerpon de banca cuyo Myriad SI lo remata, retirar cobra el doble. Lo
    que NO puede pasar nunca es que el veto del snipe sobre la retirada y el
    veto del plan sobre el ataque se cancelen mutuamente y el turno se cierre en
    blanco -- de ahi la guarda `plan.attacker <= 0` de `_active_snipe_ko_now`.
    """
    obs = copy.deepcopy(_obs(_FIX_MAIN))
    rival = obs["current"]["players"][0]["active"][0]
    archaludon = m.card_table[190]
    assert archaludon.ex and archaludon.hp == 300
    rival["id"] = 190
    rival["hp"] = rival["maxHp"] = archaludon.hp
    # Un Ogerpon de banca con energia de sobra para rematar al muro.
    obs["current"]["players"][1]["bench"][1]["energies"] = [1] * 12

    jugada = _jugada(obs, m.agent(obs))
    assert jugada != ("END", None), jugada
    assert jugada == ("RETREAT", None), jugada
