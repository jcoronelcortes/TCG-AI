"""vs Crustle: el ESTADIO se baja ANTES de la Lillie's en nuestro primer turno.

Regla (user): saliendo SEGUNDOS contra el mazo de Crustle, con un estadio
(Forest of Vitality) y una Lillie's Determination en la misma mano, se juega
PRIMERO el estadio y DESPUES la Lillie's.

Por que el veto general no vale aqui. El agente veta cualquier estadio en
NUESTRO primer turno (`_our_first_turn_guard` en `agent()` + las reglas
`t1_saliendo_primeros` / `t1_segundos_sin_estadio_rival` de
`_REGLAS_FOREST_PLAY`): bajarlo tan pronto es regalarselo a un rival que lo
reemplace en su turno siguiente. Contra Crustle esa premisa no se cumple -- el
mazo no juega estadio, o lleva una o dos copias sueltas --, asi que el Forest se
queda en mesa.

Y el coste de conservarlo NO es cero: Lillie's Determination BARAJA LA MANO
ENTERA en el mazo. Guardar el estadio "para el proximo turno" teniendo la
Lillie's en la misma mano es PERDERLO. Las dos jugadas no compiten: caben en el
mismo turno si el estadio va primero, y el tier de orden `_TIER_STADIUM` (50) ya
lo antepone al Supporter (tier 0).

Alcance: SOLO vs Crustle y SOLO saliendo segundos (turno 2). Contra el resto de
matchups -- que si pueden reemplazar el estadio -- sigue mandando el veto.

El gate mira la LINEA Crustle en el tablero (`_op_juega_crustle`), no el flag
`op_is_crustle_deck`: ese flag significa "muro inmune a ex" y tambien se
enciende con Sylveon/Eevee, que comparten la inmunidad pero no la ausencia de
estadio -- que es lo unico que justifica adelantar el nuestro.

Cobertura:
  * caso positivo: vs Crustle, segundos, estadio + Lillie's -> se juega el Forest;
  * control de matchup: mismo tablero vs Dragapult -> el Forest sigue vetado;
  * control del flag: vs Eevee/Sylveon (`op_is_crustle_deck` tambien encendido)
    -> el Forest sigue vetado;
  * control de la mano: vs Crustle SIN Lillie's -> nada que proteger, sigue vetado;
  * control de orden: el Supporter ya jugado no resucita el estadio;
  * control de asiento: saliendo primeros el veto se mantiene.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import Escenario, pk

DWEBBLE = 344          # linea Crustle (enciende `op_is_crustle_deck`)
EEVEE = m.Eevee_TWM    # linea Sylveon: TAMBIEN enciende `op_is_crustle_deck`
DREEPY = m.Dreepy      # control: matchup que NO es Crustle


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


def _escenario(op_basico=DWEBBLE, con_lillie=True, partidario_jugado=False,
               primer_jugador=1):
    """Nuestro PRIMER turno saliendo segundos (turno 2) con el estadio y la
    Lillie's en la mano. `primer_jugador=1` = el rival salio primero."""
    mano = [m.Forest_of_Vitality, m.Basic_Grass_Energy, m.Ultra_Ball]
    if con_lillie:
        mano.append(m.Lillie_Determination)
    esc = (Escenario(turno=2, paso=7, tac=0,
                     primer_jugador=primer_jugador,
                     partidario_jugado=partidario_jugado)
           .mi_activo(pk(m.Tapu_Bulu))
           .mi_banca(pk(m.Applin))
           .mi_mano(*mano)
           .op_activo(pk(op_basico, hp=70, max_hp=70))
           .op_zonas(mano=5, mazo=50, premios=6)
           .menu_mano(con_adjunte=True))
    return esc.construir()


def _carta_jugada(obs, eleccion):
    assert eleccion, f"el agente termino el turno: {eleccion}"
    opt = obs["select"]["option"][eleccion[0]]
    if opt["type"] != int(m.OptionType.PLAY):
        return None
    return obs["current"]["players"][0]["hand"][opt["index"]]["id"]


def test_vs_crustle_segundos_baja_el_estadio_antes_de_la_lillie():
    obs = _escenario()
    eleccion = m.agent(obs)
    assert _carta_jugada(obs, eleccion) == m.Forest_of_Vitality, (
        "vs Crustle, saliendo segundos y con estadio + Lillie's en la mano, "
        "el Forest se baja PRIMERO: la Lillie's baraja la mano entera y el "
        "estadio conservado se perderia en el mazo. El mazo Crustle no lo "
        "reemplaza, que es lo unico que justifica el veto general")


def test_control_otro_matchup_conserva_el_veto_del_primer_turno():
    # Mismo tablero contra un mazo que SI puede reemplazar el estadio: la
    # excepcion es de matchup, no una relajacion general del veto.
    obs = _escenario(op_basico=DREEPY)
    eleccion = m.agent(obs)
    assert _carta_jugada(obs, eleccion) != m.Forest_of_Vitality, (
        "fuera del matchup Crustle el estadio sigue vetado en nuestro primer "
        "turno")


def test_control_sylveon_no_hereda_la_excepcion():
    # `op_is_crustle_deck` se enciende TAMBIEN con Eevee/Sylveon: comparten la
    # inmunidad a ex, que es lo que ese flag significa. Pero la excepcion no
    # nace de la inmunidad sino de que el mazo Crustle no juega estadio, asi
    # que el gate mira la LINEA en el tablero y Sylveon no la hereda.
    obs = _escenario(op_basico=EEVEE)
    eleccion = m.agent(obs)
    assert m.op_is_crustle_deck, (
        "premisa del control: Eevee enciende `op_is_crustle_deck`")
    assert _carta_jugada(obs, eleccion) != m.Forest_of_Vitality, (
        "vs Sylveon el estadio sigue vetado en nuestro primer turno: el flag "
        "de muro inmune a ex no dice nada sobre si el rival juega estadio")


def test_control_sin_lillie_en_mano_conserva_el_veto():
    # Sin Lillie's no hay barajeo que temer: el estadio no corre peligro en la
    # mano y no hay razon para adelantarlo.
    obs = _escenario(con_lillie=False)
    eleccion = m.agent(obs)
    assert _carta_jugada(obs, eleccion) != m.Forest_of_Vitality, (
        "la excepcion solo existe para salvar el estadio del barajeo de "
        "Lillie's: sin Lillie's en mano el veto del primer turno sigue")


def test_control_supporter_ya_jugado_no_resucita_el_estadio():
    # Con el Supporter del turno gastado, la Lillie's de la mano ya no se va a
    # jugar: el estadio no corre peligro y la excepcion no aplica.
    obs = _escenario(partidario_jugado=True)
    eleccion = m.agent(obs)
    assert _carta_jugada(obs, eleccion) != m.Forest_of_Vitality, (
        "con el Supporter ya jugado no hay barajeo pendiente: el estadio "
        "vuelve a esperar")


def test_control_saliendo_primeros_conserva_el_veto():
    # La regla del user acota la excepcion a salir SEGUNDOS. Saliendo primeros
    # (turno 1) el rival aun no ha jugado y el veto general se mantiene.
    obs = _escenario(primer_jugador=0)
    obs["current"]["turn"] = 1
    eleccion = m.agent(obs)
    assert _carta_jugada(obs, eleccion) != m.Forest_of_Vitality, (
        "saliendo primeros el estadio sigue vetado en el turno 1")
