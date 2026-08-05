"""vs Crustle: the STADIUM is played BEFORE the Lillie's on our first turn.

Rule (user): going SECOND against the Crustle deck, with a stadium
(Forest of Vitality) and a Lillie's Determination in the same hand, the
stadium is played FIRST and the Lillie's AFTERWARDS.

Why the general veto does not hold here. The agent vetoes any stadium on
OUR first turn (`_our_first_turn_guard` in `agent()` + the rules
`t1_going_first` / `t1_second_no_opponent_stadium` of
`_RULES_FOREST_PLAY`): playing it that early is giving it to a rival who
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
from state_builder import Scenario, pk

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


def _scenario(op_basico=DWEBBLE, with_lillie=True, supporter_played=False,
               first_player=1):
    """Our FIRST turn going second (turn 2) with the stadium and the
    Lillie's in hand. `primer_jugador=1` = the rival went first."""
    hand = [m.Forest_of_Vitality, m.Basic_Grass_Energy, m.Ultra_Ball]
    if with_lillie:
        hand.append(m.Lillie_Determination)
    esc = (Scenario(turn=2, step=7, tac=0,
                     first_player=first_player,
                     supporter_played=supporter_played)
           .my_active(pk(m.Tapu_Bulu))
           .my_bench(pk(m.Applin))
           .my_hand(*hand)
           .op_active(pk(op_basico, hp=70, max_hp=70))
           .op_zonas(hand=5, deck=50, prizes=6)
           .menu_hand(with_attachment=True))
    return esc.build()


def _played_card(obs, choice):
    assert choice, f"el agente termino el turno: {choice}"
    opt = obs["select"]["option"][choice[0]]
    if opt["type"] != int(m.OptionType.PLAY):
        return None
    return obs["current"]["players"][0]["hand"][opt["index"]]["id"]


def test_vs_crustle_going_second_the_stadium_goes_before_the_lillie():
    obs = _scenario()
    choice = m.agent(obs)
    assert _played_card(obs, choice) == m.Forest_of_Vitality, (
        "vs Crustle, saliendo segundos y con estadio + Lillie's en la mano, "
        "el Forest se baja PRIMERO: la Lillie's baraja la mano entera y el "
        "estadio conservado se perderia en el mazo. El mazo Crustle no lo "
        "reemplaza, que es lo unico que justifica el veto general")


def test_control_another_matchup_keeps_the_first_turn_veto():
    # The same board against a deck that CAN replace the stadium: the
    # exception belongs to the matchup, it is not a general relaxation of the veto.
    obs = _scenario(op_basico=DREEPY)
    choice = m.agent(obs)
    assert _played_card(obs, choice) != m.Forest_of_Vitality, (
        "fuera del matchup Crustle el estadio sigue vetado en nuestro primer "
        "turno")


def test_control_sylveon_does_not_inherit_the_exception():
    # `op_is_crustle_deck` ALSO switches on with Eevee/Sylveon: they share the
    # immunity to ex, which is what that flag means. But the exception is not
    # born of the immunity but of the fact that the Crustle deck plays no stadium, so
    # the gate looks at the LINE on the board and Sylveon does not inherit it.
    obs = _scenario(op_basico=EEVEE)
    choice = m.agent(obs)
    assert m.op_is_crustle_deck, (
        "premisa del control: Eevee enciende `op_is_crustle_deck`")
    assert _played_card(obs, choice) != m.Forest_of_Vitality, (
        "vs Sylveon el estadio sigue vetado en nuestro primer turno: el flag "
        "de muro inmune a ex no dice nada sobre si el rival juega estadio")


def test_control_with_no_lillie_in_hand_the_veto_holds():
    # With no Lillie's there is no shuffle to fear: the stadium is in no danger in
    # hand and there is no reason to play it early.
    obs = _scenario(with_lillie=False)
    choice = m.agent(obs)
    assert _played_card(obs, choice) != m.Forest_of_Vitality, (
        "la excepcion solo existe para salvar el estadio del barajeo de "
        "Lillie's: sin Lillie's en mano el veto del primer turno sigue")


def test_control_a_played_supporter_does_not_revive_the_stadium():
    # With the turn's Supporter spent, the Lillie's in hand is no longer going to be
    # played: the stadium is in no danger and the exception does not apply.
    obs = _scenario(supporter_played=True)
    choice = m.agent(obs)
    assert _played_card(obs, choice) != m.Forest_of_Vitality, (
        "con el Supporter ya jugado no hay barajeo pendiente: el estadio "
        "vuelve a esperar")


def test_control_going_first_the_veto_holds():
    # The user's rule bounds the exception to going SECOND. Going first
    # (turn 1) the rival has not played yet and the general veto holds.
    obs = _scenario(first_player=0)
    obs["current"]["turn"] = 1
    choice = m.agent(obs)
    assert _played_card(obs, choice) != m.Forest_of_Vitality, (
        "saliendo primeros el estadio sigue vetado en el turno 1")
