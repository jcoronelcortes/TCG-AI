"""Tests of the Grand Tree engine (ACE SPEC stadium id 1249).

Grand Tree lets EACH player, once per turn, search their deck for a
Stage 1 that evolves from one of their Basics and, if it evolved that way, also the
corresponding Stage 2. It is a SHARED stadium: if the rival plays it, we
use it too.

It covers the rules asked for by the user:
  * with the stadium on the table its ability is used (development priority);
  * with Meganium in play Hydrapple ex is completed, with Hydrapple ex in play
    Meganium is completed, and with BOTH in play a second Hydrapple ex is made;
  * if the root Basic is missing, it is searched for in the deck / recovered from the discard;
  * with Forest of Vitality in hand, FIRST the ability and THEN the
    stadium replacement.

And the restrictions of the card itself: nothing on our first turn, nothing
on a Basic put into play this same turn.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import (FOREST_OF_VITALITY, GRAND_TREE, G, Scenario,
                           pk)

APPLIN = m.Applin
DIPPLIN = m.Dipplin
HYDRAPPLE = m.Hydrapple_ex
CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
MEGANIUM = m.Meganium
OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu
ULTRA_BALL = m.Ultra_Ball
GRASS = m.Basic_Grass_Energy

KANGASKHAN = 756


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


# ---------------------------------------------------------------------------
# Tables derived from the deck (deck-agnostic)
# ---------------------------------------------------------------------------

def test_chains_derived_from_the_deck():
    """The chains are read from `evolvesFrom`, not from a hand-written list."""
    assert (APPLIN, DIPPLIN, HYDRAPPLE) in m._DECK_CHAINS
    assert (CHIKORITA, BAYLEEF, MEGANIUM) in m._DECK_CHAINS
    assert m._GT_BASICS_WITH_CHAIN == frozenset({APPLIN, CHIKORITA})


def test_body_value_prefers_hydrapple_over_meganium():
    """Hydrapple ex (330 HP + an ability) is the best body in the deck: it is the one
    that rules when diversification does not apply (both Stage 2s already in play)."""
    assert m._gt_body_value(HYDRAPPLE) > m._gt_body_value(MEGANIUM)


# ---------------------------------------------------------------------------
# Choosing the target: the user's priority rule
# ---------------------------------------------------------------------------

def _planes(active, bench, hand=(), deck=None, veta_ex=False,
            first_turn=False):
    """Runs `_gt_planes` on a minimal synthetic board."""
    esc = (Scenario(turn=8, step=40)
           .my_active(active)
           .my_bench(*bench)
           .my_hand(*hand)
           .stadium(GRAND_TREE, of_the_opponent=True)
           .op_active(pk(KANGASKHAN, hp=400))
           .op_zones(hand=5, deck=30, prizes=4))
    if deck is not None:
        esc = esc.deck(*deck).rest_to_discard()
    obs = esc.menu_grand_tree_options().build()
    m.agent(obs)  # syncs the module's card tracking
    state = obs["current"]["players"][0]
    from cg.api import to_observation_class
    my_state = to_observation_class(obs).current.players[0]
    field = {}
    for p in [state["active"][0]] + state["bench"]:
        if p is not None:
            field[p["id"]] = field.get(p["id"], 0) + 1
    return m._gt_planes(my_state, m.ACTIVE_CARDS_IN_DECK, field,
                        first_turn, vetoes_ex_stage=veta_ex)


def test_with_meganium_in_play_hydrapple_gets_completed():
    """The user's rule: having Meganium, the chain that gets built is
    Hydrapple ex's (diversify)."""
    planes = _planes(
        active=pk(OGERPON, energies=[G, G, G]),
        bench=[pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
               pk(APPLIN), pk(CHIKORITA)])
    assert planes
    assert planes[0].basic_id == APPLIN
    assert planes[0].stage2_id == HYDRAPPLE


def test_with_hydrapple_in_play_meganium_gets_completed():
    """The mirror rule: having Hydrapple ex, Meganium gets built."""
    planes = _planes(
        active=pk(OGERPON, energies=[G, G, G]),
        bench=[pk(HYDRAPPLE, pre_evo=[APPLIN, DIPPLIN]),
               pk(APPLIN), pk(CHIKORITA)])
    assert planes
    assert planes[0].basic_id == CHIKORITA
    assert planes[0].stage2_id == MEGANIUM


def test_with_both_in_play_a_second_hydrapple_is_built():
    """The user's rule: with Meganium AND Hydrapple ex on the table, the extra copy
    that matters is Hydrapple ex's (the strongest body)."""
    planes = _planes(
        active=pk(OGERPON, energies=[G, G, G]),
        bench=[pk(HYDRAPPLE, pre_evo=[APPLIN, DIPPLIN]),
               pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
               pk(APPLIN), pk(CHIKORITA)])
    assert planes
    assert planes[0].basic_id == APPLIN
    assert planes[0].stage2_id == HYDRAPPLE


def test_an_anti_ex_matchup_prefers_the_non_ex_line():
    """Against a rival that makes ex immune, the Stage 2 ex is discarded and the
    non-ex chain (Meganium) wins: building a 2-prize ex that cannot damage
    the wall is worse than not doing it."""
    planes = _planes(
        active=pk(OGERPON, energies=[G, G, G]),
        bench=[pk(APPLIN), pk(CHIKORITA)],
        veta_ex=True)
    assert planes
    assert planes[0].basic_id == CHIKORITA
    assert planes[0].stage2_id == MEGANIUM
    # Applin's chain still exists but stops at Stage 1.
    applin = [p for p in planes if p.basic_id == APPLIN]
    assert applin and applin[0].stage2_id == 0


def test_a_basic_played_this_turn_is_not_a_target():
    """The card forbids evolving a Basic put into play this turn."""
    planes = _planes(
        active=pk(OGERPON, energies=[G, G, G]),
        bench=[pk(APPLIN, aparecio=True), pk(CHIKORITA)])
    assert all(p.basic_id != APPLIN for p in planes)
    assert any(p.basic_id == CHIKORITA for p in planes)


def test_the_first_turn_has_no_plans():
    """The card forbids evolving Basics on our first turn."""
    planes = _planes(
        active=pk(OGERPON, energies=[G]),
        bench=[pk(APPLIN), pk(CHIKORITA)],
        first_turn=True)
    assert planes == []


def test_it_prefers_the_bench_when_the_active_is_doomed():
    """With the active about to die, turning it into a body worth MORE prizes
    yields the turn to a bench Basic."""
    esc = (Scenario(turn=8, step=40)
           .my_active(pk(APPLIN, hp=10))
           .my_bench(pk(APPLIN))
           .stadium(GRAND_TREE, of_the_opponent=True)
           .op_active(pk(KANGASKHAN, hp=400))
           .op_zones(hand=5, deck=30, prizes=4))
    obs = esc.menu_grand_tree_options().build()
    m.agent(obs)
    from cg.api import to_observation_class
    my_state = to_observation_class(obs).current.players[0]
    field = {APPLIN: 2}
    planes = m._gt_planes(my_state, m.ACTIVE_CARDS_IN_DECK, field, False,
                          doomed_active=True)
    assert planes
    assert planes[0].area == m.AreaType.BENCH


# ---------------------------------------------------------------------------
# The ability is USED (main menu)
# ---------------------------------------------------------------------------

def _obs_menu(hand=(), bench=None, with_forest=False, deck=None, turn=8):
    bench = bench if bench is not None else [pk(APPLIN), pk(CHIKORITA)]
    esc = (Scenario(turn=turn, step=40)
           .my_active(pk(OGERPON, energies=[G, G, G]))
           .my_bench(*bench)
           .my_hand(*hand)
           .stadium(GRAND_TREE, of_the_opponent=True)
           .op_active(pk(KANGASKHAN, hp=400))
           .op_zones(hand=5, deck=30, prizes=4))
    if deck is not None:
        esc = esc.deck(*deck).rest_to_discard()
    return esc.menu_grand_tree_options(with_forest=with_forest).build()


def test_the_opponent_stadium_ability_is_used():
    """The stadium is shared: with the rival's Grand Tree on the table, the best
    play of the turn is its ability (a free chain)."""
    obs = _obs_menu()
    choice = m.agent(obs)
    assert obs["select"]["option"][choice[0]]["type"] == int(m.OptionType.ABILITY)


def test_the_ability_comes_before_replacing_with_forest():
    """The user's rule: with Forest of Vitality in hand, FIRST the Grand Tree
    ability and THEN the stadium replacement."""
    obs = _obs_menu(hand=[FOREST_OF_VITALITY], with_forest=True)
    choice = m.agent(obs)
    elegida = obs["select"]["option"][choice[0]]
    assert elegida["type"] == int(m.OptionType.ABILITY)


def test_with_no_executable_plan_the_forest_is_played():
    """With no evolvable Basic (both came out this turn) the ability holds
    nothing back: the Forest replaces the rival stadium as usual."""
    obs = _obs_menu(hand=[FOREST_OF_VITALITY], with_forest=True,
                    bench=[pk(APPLIN, aparecio=True),
                           pk(CHIKORITA, aparecio=True)])
    choice = m.agent(obs)
    elegida = obs["select"]["option"][choice[0]]
    assert elegida["type"] == int(m.OptionType.PLAY)


def test_the_ability_comes_before_evolving_from_hand():
    """Grand Tree does not spend a card from hand: it is cashed in before the manual
    evolution, which is still available afterwards."""
    esc = (Scenario(turn=8, step=40)
           .my_active(pk(OGERPON, energies=[G, G, G]))
           .my_bench(pk(APPLIN), pk(CHIKORITA))
           .my_hand(BAYLEEF)
           .stadium(GRAND_TREE, of_the_opponent=True)
           .op_active(pk(KANGASKHAN, hp=400))
           .op_zones(hand=5, deck=30, prizes=4))
    obs = esc.menu_grand_tree_options(with_evolution_in_hand=True).build()
    choice = m.agent(obs)
    assert obs["select"]["option"][choice[0]]["type"] == int(m.OptionType.ABILITY)


# ---------------------------------------------------------------------------
# Sub-selections of the ability
# ---------------------------------------------------------------------------

def test_choosing_the_pokemon_to_evolve_follows_the_plan():
    """With Meganium in play, the sub-selection picks the Applin (Hydrapple ex's
    chain), not the Chikorita."""
    esc = (Scenario(turn=8, step=41)
           .my_active(pk(OGERPON, energies=[G, G, G]))
           .my_bench(pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
                     pk(APPLIN), pk(CHIKORITA))
           .stadium(GRAND_TREE, of_the_opponent=True)
           .op_active(pk(KANGASKHAN, hp=400))
           .op_zones(hand=5, deck=30, prizes=4))
    obs = esc.grand_tree_selection_in_play().build()
    choice = m.agent(obs)
    elegida = obs["select"]["option"][choice[0]]
    bench = obs["current"]["players"][0]["bench"]
    assert elegida["area"] == int(m.AreaType.BENCH)
    assert bench[elegida["index"]]["id"] == APPLIN


def test_choosing_the_card_from_the_deck_follows_the_plan():
    """Offered Dipplin and Bayleef, it brings the link of the plan (Dipplin)."""
    esc = (Scenario(turn=8, step=41)
           .my_active(pk(OGERPON, energies=[G, G, G]))
           .my_bench(pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
                     pk(APPLIN), pk(CHIKORITA))
           .stadium(GRAND_TREE, of_the_opponent=True)
           .op_active(pk(KANGASKHAN, hp=400))
           .op_zones(hand=5, deck=30, prizes=4)
           .deck(DIPPLIN, BAYLEEF, HYDRAPPLE, GRASS)
           .rest_to_discard())
    obs = esc.grand_tree_selection_deck(DIPPLIN, BAYLEEF).build()
    choice = m.agent(obs)
    elegida = obs["select"]["option"][choice[0]]
    assert obs["select"]["deck"][elegida["index"]]["id"] == DIPPLIN


def test_step_2_brings_the_stage_2_even_if_the_plan_no_longer_points_at_the_basic():
    """With step 1 resolved, the Basic is already a Stage 1 and `_gt_plan` stops
    pointing at it; the deck-agnostic criterion (an evolution whose pre-evolution is in
    play) still brings the Hydrapple ex."""
    esc = (Scenario(turn=8, step=42)
           .my_active(pk(OGERPON, energies=[G, G, G]))
           .my_bench(pk(DIPPLIN, pre_evo=[APPLIN]))
           .stadium(GRAND_TREE, of_the_opponent=True)
           .op_active(pk(KANGASKHAN, hp=400))
           .op_zones(hand=5, deck=30, prizes=4)
           .deck(HYDRAPPLE, GRASS)
           .rest_to_discard())
    obs = esc.grand_tree_selection_deck(HYDRAPPLE).build()
    choice = m.agent(obs)
    elegida = obs["select"]["option"][choice[0]]
    assert obs["select"]["deck"][elegida["index"]]["id"] == HYDRAPPLE


# ---------------------------------------------------------------------------
# Getting the root: a fetch in the deck / discard
# ---------------------------------------------------------------------------

def test_the_ultra_ball_searches_the_root_basic_if_there_is_none():
    """The user's rule: with no root Basic in play, the turn's search brings the
    one that opens the Grand Tree chain."""
    esc = (Scenario(turn=8, step=30)
           .my_active(pk(OGERPON, energies=[G, G, G]))
           .my_bench(pk(TAPU, energies=[G, G]))
           .my_hand(GRASS, GRASS)
           .stadium(GRAND_TREE, of_the_opponent=True)
           .op_active(pk(KANGASKHAN, hp=400))
           .op_zones(hand=5, deck=30, prizes=4)
           .deck(APPLIN, DIPPLIN, HYDRAPPLE, CHIKORITA, BAYLEEF, MEGANIUM,
                 GRASS, GRASS)
           .fetch_ultra_ball()
           .rest_to_discard())
    obs = esc.build()
    choice = m.agent(obs)
    elegida = obs["select"]["option"][choice[0]]
    assert obs["select"]["deck"][elegida["index"]]["id"] == APPLIN


def test_without_grand_tree_the_fetch_bonus_does_not_exist():
    """The whole engine is INERT without the stadium on the table: the same board without
    Grand Tree does not force the search for the root Basic."""
    def _fetch(stadium):
        esc = (Scenario(turn=8, step=30)
               .my_active(pk(OGERPON, energies=[G, G, G]))
               .my_bench(pk(TAPU, energies=[G, G]))
               .my_hand(GRASS, GRASS)
               .op_active(pk(KANGASKHAN, hp=400))
               .op_zones(hand=5, deck=30, prizes=4))
        if stadium is not None:
            esc = esc.stadium(stadium, of_the_opponent=True)
        obs = (esc.deck(APPLIN, DIPPLIN, HYDRAPPLE, CHIKORITA, BAYLEEF,
                        MEGANIUM, GRASS, GRASS)
               .fetch_ultra_ball()
               .rest_to_discard()
               .build())
        choice = m.agent(obs)
        elegida = obs["select"]["option"][choice[0]]
        return obs["select"]["deck"][elegida["index"]]["id"]

    with_gt = _fetch(GRAND_TREE)
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._field_at_turn_start = {}
    without_gt = _fetch(None)
    # With the stadium the new rule rules; without it, the search goes back to what
    # the pre-existing rules decided (here, the refresh engine: Meowth ex
    # is not in the declared deck, so the usual Stage 2 wins).
    assert with_gt == APPLIN
    assert without_gt != APPLIN


def test_with_the_root_in_play_the_search_is_not_forced():
    """With an Applin already on the bench the root exists: the bonus does not apply and
    the rest of the deck's priorities rule."""
    esc = (Scenario(turn=8, step=30)
           .my_active(pk(OGERPON, energies=[G, G, G]))
           .my_bench(pk(APPLIN, aparecio=True))
           .my_hand(GRASS, GRASS)
           .stadium(GRAND_TREE, of_the_opponent=True)
           .op_active(pk(KANGASKHAN, hp=400))
           .op_zones(hand=5, deck=30, prizes=4)
           .deck(APPLIN, DIPPLIN, HYDRAPPLE, CHIKORITA, BAYLEEF, MEGANIUM,
                 GRASS, GRASS)
           .fetch_ultra_ball()
           .rest_to_discard())
    obs = esc.build()
    m.agent(obs)  # it must not blow up; the choice is decided by the previous rules
    ranking = m._gt_wanted_basics(m.ACTIVE_CARDS_IN_DECK,
                                     {OGERPON: 1, APPLIN: 1})
    assert APPLIN in ranking and CHIKORITA in ranking
