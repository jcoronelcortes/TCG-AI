"""vs Crustle: the STADIUM is played BEFORE the Lillie's on our first turn.

Rule (user): going SECOND against the Crustle deck, with a stadium
(Forest of Vitality) and a Lillie's Determination in the same hand, the
stadium is played FIRST and the Lillie's AFTERWARDS.

Why the general veto does not hold here. The agent vetoes any stadium on
OUR first turn (`_our_first_turn_guard` in `agent()` + the rules
`t1_saliendo_primeros` / `t1_segundos_sin_estadio_rival` of
`_REGLAS_FOREST_PLAY`): playing it that early is giving it to a rival who
replaces it on their next turn. Against Crustle that premise does not hold -- the
deck does not play a stadium, or carries one or two loose copies --, so the Forest
stays on the table.

And the cost of keeping it is NOT zero: Lillie's Determination SHUFFLES THE WHOLE
HAND into the deck. Keeping the stadium "for next turn" while holding the
Lillie's in the same hand is LOSING it. The two plays do not compete: they fit in the
same turn if the stadium goes first, and the order tier `_TIER_STADIUM` (50) already
puts it ahead of the Supporter (tier 0).

Scope: ONLY vs Crustle and ONLY going second (turn 2). Against the other
matchups -- which can replace the stadium -- the veto still rules.

The gate looks at the Crustle LINE on the board (`_op_juega_crustle`), not at the flag
`op_is_crustle_deck`: that flag means "a wall immune to ex" and also
switches on with Sylveon/Eevee, which share the immunity but not the absence of a
stadium -- which is the only thing that justifies playing ours early.

Coverage:
  * the positive case: vs Crustle, going second, a stadium + Lillie's -> the Forest is played;
  * a matchup control: the same board vs Dragapult -> the Forest is still vetoed;
  * a flag control: vs Eevee/Sylveon (`op_is_crustle_deck` also switched on)
    -> the Forest is still vetoed;
  * a hand control: vs Crustle WITHOUT Lillie's -> nothing to protect, still vetoed;
  * an order control: an already-played Supporter does not resurrect the stadium;
  * a seat control: going first the veto holds.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import Escenario, pk

DWEBBLE = 344          # the Crustle line (switches on `op_is_crustle_deck`)
EEVEE = m.Eevee_TWM    # the Sylveon line: it ALSO switches on `op_is_crustle_deck`
DREEPY = m.Dreepy      # control: a matchup that is NOT Crustle


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
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
    m._init_cards_tracking()


def _escenario(op_basico=DWEBBLE, con_lillie=True, partidario_jugado=False,
               primer_jugador=1):
    """Our FIRST turn going second (turn 2) with the stadium and the
    Lillie's in hand. `primer_jugador=1` = the rival went first."""
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
           .op_zonas(mano=5, mazo=50, prizes=6)
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
    # The same board against a deck that CAN replace the stadium: the
    # exception belongs to the matchup, it is not a general relaxation of the veto.
    obs = _escenario(op_basico=DREEPY)
    eleccion = m.agent(obs)
    assert _carta_jugada(obs, eleccion) != m.Forest_of_Vitality, (
        "fuera del matchup Crustle el estadio sigue vetado en nuestro primer "
        "turno")


def test_control_sylveon_no_hereda_la_excepcion():
    # `op_is_crustle_deck` ALSO switches on with Eevee/Sylveon: they share the
    # immunity to ex, which is what that flag means. But the exception is not
    # born of the immunity but of the fact that the Crustle deck plays no stadium, so
    # the gate looks at the LINE on the board and Sylveon does not inherit it.
    obs = _escenario(op_basico=EEVEE)
    eleccion = m.agent(obs)
    assert m.op_is_crustle_deck, (
        "premisa del control: Eevee enciende `op_is_crustle_deck`")
    assert _carta_jugada(obs, eleccion) != m.Forest_of_Vitality, (
        "vs Sylveon el estadio sigue vetado en nuestro primer turno: el flag "
        "de muro inmune a ex no dice nada sobre si el rival juega estadio")


def test_control_sin_lillie_en_mano_conserva_el_veto():
    # With no Lillie's there is no shuffle to fear: the stadium is in no danger in
    # hand and there is no reason to play it early.
    obs = _escenario(con_lillie=False)
    eleccion = m.agent(obs)
    assert _carta_jugada(obs, eleccion) != m.Forest_of_Vitality, (
        "la excepcion solo existe para salvar el estadio del barajeo de "
        "Lillie's: sin Lillie's en mano el veto del primer turno sigue")


def test_control_supporter_ya_jugado_no_resucita_el_estadio():
    # With the turn's Supporter spent, the Lillie's in hand is no longer going to be
    # played: the stadium is in no danger and the exception does not apply.
    obs = _escenario(partidario_jugado=True)
    eleccion = m.agent(obs)
    assert _carta_jugada(obs, eleccion) != m.Forest_of_Vitality, (
        "con el Supporter ya jugado no hay barajeo pendiente: el estadio "
        "vuelve a esperar")


def test_control_saliendo_primeros_conserva_el_veto():
    # The user's rule bounds the exception to going SECOND. Going first
    # (turn 1) the rival has not played yet and the general veto holds.
    obs = _escenario(primer_jugador=0)
    obs["current"]["turn"] = 1
    eleccion = m.agent(obs)
    assert _carta_jugada(obs, eleccion) != m.Forest_of_Vitality, (
        "saliendo primeros el estadio sigue vetado en el turno 1")
