"""El KO ENTRE TURNOS no habilita Flip the Script: no se baja Fezandipiti ex.

Escenario (user, episodio 88914948 registro_008 paso 76 vs Marnie/Grimmsnarl,
PERDIDA):

    NOSOTROS (asiento 1)                     RIVAL (Marnie/Grimmsnarl)
    activo  Meowth ex 110/170                activo  Munkidori 90/110 2e
    banca   Meganium 130, Ogerpon ex 150,    banca   Munkidori 90, 2x Froslass,
            Ogerpon ex 150, Tapu Bulu 140            2x Marnie's Impidimp
    mano    Fezandipiti ex, Bayleef,
            Meganium, Unfair Stamp, Tapu Bulu
    premios 6 - 5   (el rival acaba de cobrar uno: perdimos el Dipplin)

Turno 8, con un hueco de banca libre: el agente bajaba Fezandipiti ex a cobrar
el robo de 3 de Flip the Script. La habilidad NO estaba disponible -- el turno
se cerro sin usarla y el cuerpo se quedo en la banca como un regalo de 2
premios en el ultimo hueco.

LA VENTANA, NO LA FUENTE DEL DANO
---------------------------------
Flip the Script (y el Unfair Stamp, que lleva impresa la MISMA clausula) pide
que un Pokemon nuestro quedara Fuera de Combate "durante el ULTIMO TURNO DE TU
RIVAL". Los logs del registro dicen donde murio el Dipplin:

    TURN_END(rival) -> 14 x HP_CHANGE(putDamageCounter, -10) -> Dipplin al
    descarte -> el rival cobra premio -> TURN_START(nuestro)

Es Freezing Shroud (Froslass: 1 contador a cada Pokemon CON HABILIDAD, y habia
DOS Froslass), un efecto que dispara ENTRE TURNOS. El KO no cae dentro del turno
del rival: cae en tierra de nadie. El motor lo confirma dos veces en el mismo
menu: no ofrece el Unfair Stamp que teniamos en mano ni, tras bajar el cuerpo,
la habilidad.

El corte NO es "ataque vs habilidad". El mismo episodio lo refuta: en el paso
105 Munkidori MOVIO 3 contadores con Adrena-Brain y mato a nuestro Ogerpon ex
DENTRO del turno del rival -- y el turno siguiente el motor SI ofrecio el Sello.
Una habilidad que noquea dentro del turno rival cuenta; un ataque que noqueara
entre turnos no contaria. Lo que decide es la VENTANA.

El detector viejo solo miraba el EFECTO del KO (el rival cobra premio ->
`op_prize` baja), que no dice CUANDO murio el cuerpo. `_rastrear_ventana_de_ko`
sigue los TURN_START / TURN_END de los logs y clasifica cada KO propio; el
resultado solo puede REBAJAR `ko_last_turn`, nunca subirlo, asi que sin
evidencia en los logs el comportamiento es el de antes.
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

FEZ = m.Fezandipiti_ex
STAMP = m.Unfair_Stamp

_FIX = ROOT / "tests" / "fixtures"
_FIX_ENTRE_TURNOS = _FIX / "marnie_ko_entre_turnos_no_baja_fez_step76.json"
_FIX_TURNO_RIVAL = _FIX / "marnie_ko_en_turno_rival_habilita_el_sello_step107.json"


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cartas_tracking()
    m._cartas_first_scan_done = False
    m._cartas_prizes_identified = False
    m._cartas_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    yield
    m._init_cartas_tracking()


def _cargar(fixture):
    """(observacion previa, observacion de la decision) del registro."""
    with open(fixture, encoding="utf-8") as f:
        datos = json.load(f)
    return datos["observacion_previa"], datos["observation"]


def _jugadas(obs):
    """(tipo, card_id) de cada opcion del menu."""
    yo = obs["current"]["yourIndex"]
    mano = obs["current"]["players"][yo]["hand"]
    salida = []
    for o in obs["select"]["option"]:
        if o["type"] == int(m.OptionType.PLAY):
            salida.append(("PLAY", mano[o["index"]]["id"]))
        elif o["type"] == int(m.OptionType.END):
            salida.append(("END", None))
        else:
            salida.append((o["type"], None))
    return salida


def _log(**campos):
    return SimpleNamespace(**campos)


# ---------------------------------------------------------------------------
# 1. El registro: KO entre turnos -> el cuerpo NO baja
# ---------------------------------------------------------------------------

def test_ko_entre_turnos_no_baja_fezandipiti():
    previa, decision = _cargar(_FIX_ENTRE_TURNOS)

    # El menu real ofrecia bajar el Fezandipiti ex.
    jugadas = _jugadas(decision)
    assert ("PLAY", FEZ) in jugadas, jugadas

    # ... y el propio motor decia que la clausula NO se cumplia: teniamos el
    # Unfair Stamp en mano y no aparece como jugable.
    yo = decision["current"]["yourIndex"]
    mano = [c["id"] for c in decision["current"]["players"][yo]["hand"]]
    assert STAMP in mano, mano
    assert ("PLAY", STAMP) not in jugadas, jugadas

    m.agent(previa)          # trae el TURN_END del rival
    eleccion = m.agent(decision)

    assert not m.ko_last_turn, (
        "el KO llego ENTRE TURNOS (Freezing Shroud): Flip the Script no se "
        "puede usar y `ko_last_turn` debe quedar en False")
    assert jugadas[eleccion[0]] != ("PLAY", FEZ), (
        f"con la habilidad muerta, bajar Fezandipiti ex regala 2 premios y el "
        f"ultimo hueco de banca a cambio de nada; jugo {jugadas[eleccion[0]]}")


def test_el_menu_del_motor_manda_sobre_la_inferencia_de_logs():
    """Sin los logs de la ventana, el Sello ausente del menu ya lo delata.

    Es el oraculo de respaldo: `ko_last_turn` llega a True por el premio que
    cobro el rival, pero el Unfair Stamp esta en la mano y el motor no lo
    ofrece -- luego la clausula no se cumple y la habilidad tampoco existe.
    """
    _, decision = _cargar(_FIX_ENTRE_TURNOS)
    m.agent(decision)          # SIN la observacion previa: no vimos el TURN_END
    assert m._ko_propio_fuera_del_turno_rival == -99
    assert not m.ko_last_turn


# ---------------------------------------------------------------------------
# 2. La otra cara: KO DENTRO del turno rival -> la clausula SI se cumple
# ---------------------------------------------------------------------------

def test_ko_por_habilidad_dentro_del_turno_rival_si_habilita():
    previa, decision = _cargar(_FIX_TURNO_RIVAL)

    # Adrena-Brain (Munkidori) movio 3 contadores y mato a nuestro Ogerpon ex
    # DENTRO del turno del rival: el motor ofrece el Sello el turno siguiente.
    jugadas = _jugadas(decision)
    assert ("PLAY", STAMP) in jugadas, jugadas

    m.agent(previa)
    m.agent(decision)

    assert m.ko_last_turn, (
        "un KO por HABILIDAD dentro del turno del rival cuenta igual que uno "
        "por ataque: la clausula habla de la ventana, no de la fuente del dano")


# ---------------------------------------------------------------------------
# 3. El clasificador, en seco
# ---------------------------------------------------------------------------

def _ko_propio(serial=1, area=m.AreaType.BENCH):
    return _log(type=m.LogType.MOVE_CARD, playerIndex=1, cardId=FEZ,
                serial=serial, fromArea=area, toArea=m.AreaType.DISCARD)


@pytest.mark.parametrize("logs, dentro, fuera", [
    # KO dentro del turno del rival.
    ([_log(type=m.LogType.TURN_START, playerIndex=0), _ko_propio()], 9, -99),
    # KO entre turnos (tras el TURN_END del rival).
    ([_log(type=m.LogType.TURN_START, playerIndex=0),
      _log(type=m.LogType.TURN_END, playerIndex=0), _ko_propio()], -99, 9),
    # Auto-KO en NUESTRO turno (retroceso): tampoco habilita nada.
    ([_log(type=m.LogType.TURN_START, playerIndex=1), _ko_propio()], -99, 9),
    # Sin marcador de turno no hay evidencia: no se clasifica.
    ([_ko_propio()], -99, -99),
])
def test_clasificador_de_ventana(logs, dentro, fuera):
    m._reset_ventana_de_ko()
    m._rastrear_ventana_de_ko(logs, my_index=1, turno=9)
    assert m._ko_propio_en_turno_rival == dentro
    assert m._ko_propio_fuera_del_turno_rival == fuera


def test_el_cuerpo_del_rival_y_las_energias_no_son_kos_nuestros():
    m._reset_ventana_de_ko()
    m._rastrear_ventana_de_ko([
        _log(type=m.LogType.TURN_START, playerIndex=0),
        # KO del RIVAL (playerIndex 0)
        _log(type=m.LogType.MOVE_CARD, playerIndex=0, cardId=FEZ, serial=5,
             fromArea=m.AreaType.ACTIVE, toArea=m.AreaType.DISCARD),
        # energia adjunta nuestra al descarte (acompana al KO, no es el cuerpo)
        _log(type=m.LogType.MOVE_CARD, playerIndex=1, cardId=m.Basic_Grass_Energy,
             serial=6, fromArea=m.AreaType.ENERGY, toArea=m.AreaType.DISCARD),
        # nuestra pre-evolucion al descarte (misma carta que ya contamos)
        _log(type=m.LogType.MOVE_CARD, playerIndex=1, cardId=m.Applin, serial=7,
             fromArea=m.AreaType.PRE_EVOLUTION, toArea=m.AreaType.DISCARD),
    ], my_index=1, turno=9)
    assert m._ko_propio_en_turno_rival == -99
    assert m._ko_propio_fuera_del_turno_rival == -99


def test_partida_nueva_borra_la_ventana():
    """El self-play encadena episodios en el mismo proceso."""
    m._rastrear_ventana_de_ko([
        _log(type=m.LogType.TURN_START, playerIndex=0),
        _log(type=m.LogType.TURN_END, playerIndex=0), _ko_propio()],
        my_index=1, turno=9)
    assert m._ko_propio_fuera_del_turno_rival == 9
    m._init_cartas_tracking()
    assert m._ko_propio_fuera_del_turno_rival == -99
    assert m._log_turno_en_curso == m._TURNO_LOG_DESCONOCIDO
