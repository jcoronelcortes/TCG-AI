"""Cornerstone Mask Ogerpon ex (117): the wall that reads our ABILITIES.

*Cornerstone Stance* prevents all damage from attacks done to it by our Pokemon
that have an Ability. Read against this deck's list that is not a partial veto,
it is almost a total one -- `OUR_ABILITY_IDS` holds Teal Mask Ogerpon ex,
Hydrapple ex, Meganium, Dipplin, Meowth ex and Fezandipiti ex, i.e. every body
we would normally attack with. What is left able to put damage on it is
Chikorita, Bayleef, Applin and **Tapu Bulu**, and only the last of those is an
attacker: Wood Hammer's 220 doubled by the wall's {G} weakness is 440 against
210 HP, a two-prize knockout the turn Tapu can pay for it.

Two consequences drive every case here:

  * the whole matchup is "get Tapu Bulu armed and in front", so every route
    that feeds it -- the turn's attachment, the searches, the recoveries --
    has to know it;
  * **Meganium is the price of that attack**, even though Meganium itself does
    zero to the wall. Wild Growth turns each Basic {G} into {G}{G}, so with it
    in play Wood Hammer costs TWO physical Grass instead of four. The line
    Chikorita -> Bayleef -> Meganium is a matchup priority for a body that can
    never attack into the matchup.

The frozen corpus does not exercise any of this (the flag fires in none of its
records), which is why these are synthetic boards built with the StateBuilder.
See [[estrategia-vs-cornerstone-ogerpon]].
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import G, Scenario, pk

CORNERSTONE = 117          # Cornerstone Mask Ogerpon ex
BEARTIC = 507
# A body that switches NO matchup flag on: the honest "no wall" control. Cubchoo
# does not serve here -- it raises `op_is_cubchoo_deck`, whose own branches make
# the same calls this file is measuring, so a control built on it would pass for
# the wrong reason.
NEUTRAL = 601              # Gigalith


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
    m.op_is_starmie_deck = False
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _chosen_option(obs, choice):
    return obs["select"]["option"][choice[0]]


def _attach_target_id(obs, choice):
    """Which body the chosen ATTACH option charges (None if it is not an ATTACH)."""
    opt = _chosen_option(obs, choice)
    if opt.get("type") != int(m.OptionType.ATTACH):
        return None
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    body = (me["active"][0] if opt.get("inPlayArea") == int(m.AreaType.ACTIVE)
            else me["bench"][opt["inPlayIndex"]])
    return body["id"]


def _played_card_id(obs, choice):
    """Which hand card the chosen PLAY option plays (None if it is not a PLAY)."""
    opt = _chosen_option(obs, choice)
    if opt.get("type") != int(m.OptionType.PLAY):
        return None
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    return me["hand"][opt["index"]]["id"]


def _evolution_played(obs, choice):
    """Which evolution card the chosen EVOLVE option puts down."""
    opt = _chosen_option(obs, choice)
    if opt.get("type") != int(m.OptionType.EVOLVE):
        return None
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    return me["hand"][opt["index"]]["id"]


# =====================================================================
# 1. THE OPENING TURN: the active Tapu Bulu is not denied the turn's Grass.
#
# The generic first-turn veto ("do not overcharge the opening attacker") was
# lifted for Tapu Bulu against Crustle years before this wall was modelled, and
# the exemption read `op_is_crustle_deck` only. Against Cornerstone the same
# sentence is true and the veto was still standing.
# =====================================================================

def _opening_board(op_active_id):
    """Our first turn, an active Tapu Bulu with nothing on it, one Grass in
    hand and a benched Applin that would happily eat it."""
    return (Scenario(turn=1, step=1, tac=1, first_player=0)
            .my_active(pk(m.Tapu_Bulu))
            .my_bench(pk(m.Applin))
            .my_hand(m.Basic_Grass_Energy)
            .op_active(pk(op_active_id, hp=210, max_hp=210))
            .op_zones(hand=4, deck=40, prizes=6)
            .menu_attach_energy()
            .build())


def test_opening_turn_the_grass_goes_to_the_tapu_in_front_of_cornerstone():
    obs = _opening_board(CORNERSTONE)
    assert _attach_target_id(obs, m.agent(obs)) == m.Tapu_Bulu, (
        "vs Cornerstone el Tapu Bulu activo es el UNICO cuerpo que hace dano "
        "al muro: el veto de primer turno no puede quitarle la energia del "
        "turno para dejarsela a un Applin de banca")


def test_opening_turn_without_the_wall_the_veto_still_stands():
    # The boundary the change must not cross: with no wall in front, the
    # first-turn veto keeps its original job and the opening Tapu is NOT the
    # destination of the turn's Grass.
    obs = _opening_board(NEUTRAL)
    assert _attach_target_id(obs, m.agent(obs)) != m.Tapu_Bulu, (
        "sin muro, el veto generico de 'no sobrecargar al atacante de arranque' "
        "sigue vigente")


# =====================================================================
# 2. THE LADDER TO THE DOUBLER: Chikorita -> Bayleef outranks Dipplin ->
#    Hydrapple ex against this wall.
#
# The top of the line (Meganium, 35500) was already a matchup priority; the
# RUNG that reaches it stayed at 32000, below the Hydrapple ex of the other
# line (33000). So the turn that held both evolutions assembled the 330 HP body
# that does ZERO to Cornerstone and deferred the one that halves Wood Hammer.
# =====================================================================

def _both_lines_board(op_active_id):
    """A Chikorita and a Dipplin on the bench, Bayleef and Hydrapple ex in
    hand: the menu offers exactly one evolution per line."""
    return (Scenario(turn=6, step=1, tac=1)
            .my_active(pk(m.Teal_Mask_Ogerpon_ex, energies=[G], fisicas=1))
            .my_bench(pk(m.Chikorita), pk(m.Dipplin, pre_evo=[m.Applin]))
            .my_hand(m.Bayleef, m.Hydrapple_ex)
            .op_active(pk(op_active_id, hp=210, max_hp=210))
            .op_zones(hand=4, deck=40, prizes=6)
            .menu_evolve()
            .build())


def test_vs_cornerstone_the_meganium_line_climbs_before_the_hydrapple_line():
    obs = _both_lines_board(CORNERSTONE)
    assert _evolution_played(obs, m.agent(obs)) == m.Bayleef, (
        "vs Cornerstone la linea del Meganium va PRIMERA: Hydrapple ex tiene "
        "habilidad y hace 0 al muro, mientras Wild Growth baja el Wood Hammer "
        "de 4 Plantas fisicas a 2")


def test_without_the_wall_the_hydrapple_line_keeps_its_place():
    obs = _both_lines_board(NEUTRAL)
    assert _evolution_played(obs, m.agent(obs)) == m.Hydrapple_ex, (
        "sin el muro anti-habilidad la linea de Hydrapple ex conserva su "
        "prioridad habitual")


# =====================================================================
# 3. THE RECOVERY: the Meganium line is not off-plan against this wall.
#
# The Cornerstone whitelist of the Night Stretcher selection kept only the two
# bodies that hit the wall THEMSELVES (Tapu Bulu, Pinsir) and dropped
# Chikorita, Bayleef and Meganium. Meganium is the card the matchup is built
# around, and Chikorita/Bayleef carry no Ability at all -- they are among the
# few bodies Cornerstone Stance does not switch off.
# =====================================================================

def _recovery_board(op_active_id):
    """The board that puts the two readings against each other. Our active Tapu
    Bulu holds TWO physical Grass and a Bayleef waits on the bench, so the
    Meganium in the discard is not a development piece -- it is this turn's
    attack: Wild Growth doubles those two into the four Wood Hammer costs. The
    Applin next to it in the discard is the body the old whitelist reached for
    instead, and it would arrive in hand as a Basic that does nothing this turn.

    It used to be the SECOND Tapu Bulu -- the whitelist's own first choice --
    but deck.csv now holds ONE, and that copy is the active this board needs.
    (Pinsir, the whitelist's other member, is not in the list at all, so against
    pure Cornerstone that whitelist reaches exactly one card: this active.)

    WEAKER THAN IT WAS, and it is written down rather than left to be
    discovered: with the second Tapu Bulu the competitor was the card the old
    whitelist PREFERRED. An Applin is not. Forcing
    `_ns_crustle_allowed_basics` back to `(Tapu_Bulu, Pinsir)` and
    `_ns_crustle_evos_permitidas` to `()` still recovers the Meganium on this
    board, so the Cornerstone case below no longer separates the whitelist from
    the generic scorer -- it now says the same thing as its own control. Making
    it sharp again needs a competitor the whitelist ranks above Meganium, and
    with a 1-of Tapu Bulu and no Pinsir the deck no longer holds one."""
    return (Scenario(turn=8, step=1, tac=1)
            .my_active(pk(m.Tapu_Bulu, energies=[G, G]))
            .my_bench(pk(m.Bayleef, pre_evo=[m.Chikorita]))
            # The hand is empty: the single Night Stretcher of deck.csv is the
            # one already IN EFFECT below, resolving its own selection.
            .my_hand()
            .my_discard(m.Meganium, m.Applin)
            .op_active(pk(op_active_id, hp=210, max_hp=210))
            .op_zones(hand=4, deck=40, prizes=4)
            .fetch_discard(m.Night_Stretcher)
            .build())


def _recovered_id(obs):
    opt = _chosen_option(obs, m.agent(obs))
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    return me["discard"][opt["index"]]["id"]


def test_vs_cornerstone_the_recovery_may_take_the_meganium():
    assert _recovered_id(_recovery_board(CORNERSTONE)) == m.Meganium, (
        "Meganium no ataca al muro, pero es lo que PAGA el ataque que si lo "
        "hace: recuperar la pieza que baja Wood Hammer de 4 Plantas a 2 es el "
        "plan del matchup, no una desviacion de el")


def test_without_the_wall_the_recovery_keeps_its_own_criterion():
    # The whitelist only exists for the two walls; off them the generic
    # recovery scorer decides, and it is not this change's business.
    # Off the two walls the whitelist does not exist at all, so this change is
    # inert here and the generic recovery scorer answers as it always did.
    assert _recovered_id(_recovery_board(NEUTRAL)) == m.Meganium


# =====================================================================
# 4. THE LAST GRASS: Teal Dance does not spend it on the body the wall has
#    already switched off.
#
# Teal Dance attaches FROM HAND, so with a single Grass left it is not free
# tempo: it is that card spent on an Ogerpon ex whose damage Cornerstone Stance
# cancels, while the one body that can remove the wall stays short of Wood
# Hammer. The reservation existed against Crustle and read only that flag.
# =====================================================================

def _last_grass_board(op_active_id, tapu_energy):
    """One Grass in hand, an active Ogerpon ex at one physical (below its cap of
    two, so the cap is NOT what decides here) and a benched Tapu Bulu carrying
    `tapu_energy` EFFECTIVE energy against Wood Hammer's four."""
    return (Scenario(turn=6, step=1, tac=1)
            .my_active(pk(m.Teal_Mask_Ogerpon_ex, energies=[G], fisicas=1))
            .my_bench(pk(m.Tapu_Bulu, energies=[G] * tapu_energy,
                         fisicas=tapu_energy))
            .my_hand(m.Basic_Grass_Energy)
            .op_active(pk(op_active_id, hp=210, max_hp=210))
            .op_zones(hand=4, deck=40, prizes=6)
            .menu_teal_dance_options()
            .build())


def test_vs_cornerstone_the_last_grass_goes_to_the_tapu_it_completes():
    # Tapu at three of the four Wood Hammer wants: this Grass IS the attack.
    obs = _last_grass_board(CORNERSTONE, 3)
    assert _attach_target_id(obs, m.agent(obs)) == m.Tapu_Bulu, (
        "con una sola Planta en mano y el Tapu a un adjunte de su coste, "
        "bailar la carga sobre el Ogerpon ex —anulado por Cornerstone "
        "Stance— tira el ataque del turno")


def test_a_tapu_the_grass_cannot_finish_does_not_take_the_dance_away():
    # THE MEASURED BOUNDARY (n=4000): reserving on "Tapu is short" rather than
    # on "this card makes Tapu ready" scored -0.9 on its own. From two of four
    # the attachment finishes nothing and the refused dance costs a whole card
    # -- the draw that finds the next Grass. Here the dance keeps its priority.
    obs = _last_grass_board(CORNERSTONE, 2)
    assert _chosen_option(obs, m.agent(obs))["type"] == int(m.OptionType.ABILITY), (
        "si la Planta no lleva al Tapu a su coste, negarle el baile paga una "
        "carta por un cuerpo que sigue sin poder atacar")


def test_without_the_wall_teal_dance_still_takes_the_last_grass():
    # The boundary: off the wall the dance also DRAWS a card, and the Ogerpon
    # is a real attacker. Nothing about that changes.
    obs = _last_grass_board(NEUTRAL, 3)
    assert _chosen_option(obs, m.agent(obs))["type"] == int(m.OptionType.ABILITY), (
        "sin muro, Teal Dance conserva su prioridad: adjunta y roba")
