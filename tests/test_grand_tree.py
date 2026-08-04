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
from state_builder import (FOREST_OF_VITALITY, GRAND_TREE, G, Escenario,
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

def test_cadenas_derivadas_del_mazo():
    """The chains are read from `evolvesFrom`, not from a hand-written list."""
    assert (APPLIN, DIPPLIN, HYDRAPPLE) in m._DECK_CHAINS
    assert (CHIKORITA, BAYLEEF, MEGANIUM) in m._DECK_CHAINS
    assert m._GT_BASICS_WITH_CHAIN == frozenset({APPLIN, CHIKORITA})


def test_valor_cuerpo_prefiere_hydrapple_sobre_meganium():
    """Hydrapple ex (330 HP + an ability) is the best body in the deck: it is the one
    that rules when diversification does not apply (both Stage 2s already in play)."""
    assert m._gt_body_value(HYDRAPPLE) > m._gt_body_value(MEGANIUM)


# ---------------------------------------------------------------------------
# Choosing the target: the user's priority rule
# ---------------------------------------------------------------------------

def _planes(active, banca, mano=(), mazo=None, veta_ex=False,
            primer_turno=False):
    """Runs `_gt_planes` on a minimal synthetic board."""
    esc = (Escenario(turn=8, paso=40)
           .mi_activo(active)
           .mi_banca(*banca)
           .mi_mano(*mano)
           .estadio(GRAND_TREE, del_rival=True)
           .op_activo(pk(KANGASKHAN, hp=400))
           .op_zonas(mano=5, mazo=30, prizes=4))
    if mazo is not None:
        esc = esc.mazo(*mazo).resto_al_descarte()
    obs = esc.menu_grand_tree().construir()
    m.agent(obs)  # syncs the module's card tracking
    estado = obs["current"]["players"][0]
    from cg.api import to_observation_class
    my_state = to_observation_class(obs).current.players[0]
    field = {}
    for p in [estado["active"][0]] + estado["bench"]:
        if p is not None:
            field[p["id"]] = field.get(p["id"], 0) + 1
    return m._gt_planes(my_state, m.ACTIVE_CARDS_IN_DECK, field,
                        primer_turno, vetoes_ex_stage=veta_ex)


def test_con_meganium_en_juego_se_completa_hydrapple():
    """The user's rule: having Meganium, the chain that gets built is
    Hydrapple ex's (diversify)."""
    planes = _planes(
        active=pk(OGERPON, energias=[G, G, G]),
        banca=[pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
               pk(APPLIN), pk(CHIKORITA)])
    assert planes
    assert planes[0].basic_id == APPLIN
    assert planes[0].stage2_id == HYDRAPPLE


def test_con_hydrapple_en_juego_se_completa_meganium():
    """The mirror rule: having Hydrapple ex, Meganium gets built."""
    planes = _planes(
        active=pk(OGERPON, energias=[G, G, G]),
        banca=[pk(HYDRAPPLE, pre_evo=[APPLIN, DIPPLIN]),
               pk(APPLIN), pk(CHIKORITA)])
    assert planes
    assert planes[0].basic_id == CHIKORITA
    assert planes[0].stage2_id == MEGANIUM


def test_con_ambos_en_juego_se_hace_un_segundo_hydrapple():
    """The user's rule: with Meganium AND Hydrapple ex on the table, the extra copy
    that matters is Hydrapple ex's (the strongest body)."""
    planes = _planes(
        active=pk(OGERPON, energias=[G, G, G]),
        banca=[pk(HYDRAPPLE, pre_evo=[APPLIN, DIPPLIN]),
               pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
               pk(APPLIN), pk(CHIKORITA)])
    assert planes
    assert planes[0].basic_id == APPLIN
    assert planes[0].stage2_id == HYDRAPPLE


def test_matchup_anti_ex_prefiere_la_linea_no_ex():
    """Against a rival that makes ex immune, the Stage 2 ex is discarded and the
    non-ex chain (Meganium) wins: building a 2-prize ex that cannot damage
    the wall is worse than not doing it."""
    planes = _planes(
        active=pk(OGERPON, energias=[G, G, G]),
        banca=[pk(APPLIN), pk(CHIKORITA)],
        veta_ex=True)
    assert planes
    assert planes[0].basic_id == CHIKORITA
    assert planes[0].stage2_id == MEGANIUM
    # Applin's chain still exists but stops at Stage 1.
    applin = [p for p in planes if p.basic_id == APPLIN]
    assert applin and applin[0].stage2_id == 0


def test_basico_que_salio_este_turno_no_es_objetivo():
    """The card forbids evolving a Basic put into play this turn."""
    planes = _planes(
        active=pk(OGERPON, energias=[G, G, G]),
        banca=[pk(APPLIN, aparecio=True), pk(CHIKORITA)])
    assert all(p.basic_id != APPLIN for p in planes)
    assert any(p.basic_id == CHIKORITA for p in planes)


def test_primer_turno_sin_planes():
    """The card forbids evolving Basics on our first turn."""
    planes = _planes(
        active=pk(OGERPON, energias=[G]),
        banca=[pk(APPLIN), pk(CHIKORITA)],
        primer_turno=True)
    assert planes == []


def test_prefiere_banca_con_el_activo_condenado():
    """With the active about to die, turning it into a body worth MORE prizes
    yields the turn to a bench Basic."""
    esc = (Escenario(turn=8, paso=40)
           .mi_activo(pk(APPLIN, hp=10))
           .mi_banca(pk(APPLIN))
           .estadio(GRAND_TREE, del_rival=True)
           .op_activo(pk(KANGASKHAN, hp=400))
           .op_zonas(mano=5, mazo=30, prizes=4))
    obs = esc.menu_grand_tree().construir()
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

def _obs_menu(mano=(), banca=None, con_forest=False, mazo=None, turn=8):
    banca = banca if banca is not None else [pk(APPLIN), pk(CHIKORITA)]
    esc = (Escenario(turn=turn, paso=40)
           .mi_activo(pk(OGERPON, energias=[G, G, G]))
           .mi_banca(*banca)
           .mi_mano(*mano)
           .estadio(GRAND_TREE, del_rival=True)
           .op_activo(pk(KANGASKHAN, hp=400))
           .op_zonas(mano=5, mazo=30, prizes=4))
    if mazo is not None:
        esc = esc.mazo(*mazo).resto_al_descarte()
    return esc.menu_grand_tree(con_forest=con_forest).construir()


def test_se_usa_la_habilidad_del_estadio_rival():
    """The stadium is shared: with the rival's Grand Tree on the table, the best
    play of the turn is its ability (a free chain)."""
    obs = _obs_menu()
    eleccion = m.agent(obs)
    assert obs["select"]["option"][eleccion[0]]["type"] == int(m.OptionType.ABILITY)


def test_la_habilidad_precede_al_reemplazo_por_forest():
    """The user's rule: with Forest of Vitality in hand, FIRST the Grand Tree
    ability and THEN the stadium replacement."""
    obs = _obs_menu(mano=[FOREST_OF_VITALITY], con_forest=True)
    eleccion = m.agent(obs)
    elegida = obs["select"]["option"][eleccion[0]]
    assert elegida["type"] == int(m.OptionType.ABILITY)


def test_sin_plan_ejecutable_el_forest_se_juega():
    """With no evolvable Basic (both came out this turn) the ability holds
    nothing back: the Forest replaces the rival stadium as usual."""
    obs = _obs_menu(mano=[FOREST_OF_VITALITY], con_forest=True,
                    banca=[pk(APPLIN, aparecio=True),
                           pk(CHIKORITA, aparecio=True)])
    eleccion = m.agent(obs)
    elegida = obs["select"]["option"][eleccion[0]]
    assert elegida["type"] == int(m.OptionType.PLAY)


def test_la_habilidad_precede_a_evolucionar_desde_la_mano():
    """Grand Tree does not spend a card from hand: it is cashed in before the manual
    evolution, which is still available afterwards."""
    esc = (Escenario(turn=8, paso=40)
           .mi_activo(pk(OGERPON, energias=[G, G, G]))
           .mi_banca(pk(APPLIN), pk(CHIKORITA))
           .mi_mano(BAYLEEF)
           .estadio(GRAND_TREE, del_rival=True)
           .op_activo(pk(KANGASKHAN, hp=400))
           .op_zonas(mano=5, mazo=30, prizes=4))
    obs = esc.menu_grand_tree(con_evolucion_mano=True).construir()
    eleccion = m.agent(obs)
    assert obs["select"]["option"][eleccion[0]]["type"] == int(m.OptionType.ABILITY)


# ---------------------------------------------------------------------------
# Sub-selections of the ability
# ---------------------------------------------------------------------------

def test_seleccion_del_pokemon_a_evolucionar_sigue_al_plan():
    """With Meganium in play, the sub-selection picks the Applin (Hydrapple ex's
    chain), not the Chikorita."""
    esc = (Escenario(turn=8, paso=41)
           .mi_activo(pk(OGERPON, energias=[G, G, G]))
           .mi_banca(pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
                     pk(APPLIN), pk(CHIKORITA))
           .estadio(GRAND_TREE, del_rival=True)
           .op_activo(pk(KANGASKHAN, hp=400))
           .op_zonas(mano=5, mazo=30, prizes=4))
    obs = esc.seleccion_grand_tree_en_juego().construir()
    eleccion = m.agent(obs)
    elegida = obs["select"]["option"][eleccion[0]]
    banca = obs["current"]["players"][0]["bench"]
    assert elegida["area"] == int(m.AreaType.BENCH)
    assert banca[elegida["index"]]["id"] == APPLIN


def test_seleccion_de_carta_del_mazo_sigue_al_plan():
    """Offered Dipplin and Bayleef, it brings the link of the plan (Dipplin)."""
    esc = (Escenario(turn=8, paso=41)
           .mi_activo(pk(OGERPON, energias=[G, G, G]))
           .mi_banca(pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
                     pk(APPLIN), pk(CHIKORITA))
           .estadio(GRAND_TREE, del_rival=True)
           .op_activo(pk(KANGASKHAN, hp=400))
           .op_zonas(mano=5, mazo=30, prizes=4)
           .mazo(DIPPLIN, BAYLEEF, HYDRAPPLE, GRASS)
           .resto_al_descarte())
    obs = esc.seleccion_grand_tree_mazo(DIPPLIN, BAYLEEF).construir()
    eleccion = m.agent(obs)
    elegida = obs["select"]["option"][eleccion[0]]
    assert obs["select"]["deck"][elegida["index"]]["id"] == DIPPLIN


def test_paso_2_trae_la_etapa_2_aunque_el_plan_ya_no_apunte_al_basico():
    """With step 1 resolved, the Basic is already a Stage 1 and `_gt_plan` stops
    pointing at it; the deck-agnostic criterion (an evolution whose pre-evolution is in
    play) still brings the Hydrapple ex."""
    esc = (Escenario(turn=8, paso=42)
           .mi_activo(pk(OGERPON, energias=[G, G, G]))
           .mi_banca(pk(DIPPLIN, pre_evo=[APPLIN]))
           .estadio(GRAND_TREE, del_rival=True)
           .op_activo(pk(KANGASKHAN, hp=400))
           .op_zonas(mano=5, mazo=30, prizes=4)
           .mazo(HYDRAPPLE, GRASS)
           .resto_al_descarte())
    obs = esc.seleccion_grand_tree_mazo(HYDRAPPLE).construir()
    eleccion = m.agent(obs)
    elegida = obs["select"]["option"][eleccion[0]]
    assert obs["select"]["deck"][elegida["index"]]["id"] == HYDRAPPLE


# ---------------------------------------------------------------------------
# Getting the root: a fetch in the deck / discard
# ---------------------------------------------------------------------------

def test_ultra_ball_busca_el_basico_raiz_si_no_hay_ninguno():
    """The user's rule: with no root Basic in play, the turn's search brings the
    one that opens the Grand Tree chain."""
    esc = (Escenario(turn=8, paso=30)
           .mi_activo(pk(OGERPON, energias=[G, G, G]))
           .mi_banca(pk(TAPU, energias=[G, G]))
           .mi_mano(GRASS, GRASS)
           .estadio(GRAND_TREE, del_rival=True)
           .op_activo(pk(KANGASKHAN, hp=400))
           .op_zonas(mano=5, mazo=30, prizes=4)
           .mazo(APPLIN, DIPPLIN, HYDRAPPLE, CHIKORITA, BAYLEEF, MEGANIUM,
                 GRASS, GRASS)
           .fetch_ultra_ball()
           .resto_al_descarte())
    obs = esc.construir()
    eleccion = m.agent(obs)
    elegida = obs["select"]["option"][eleccion[0]]
    assert obs["select"]["deck"][elegida["index"]]["id"] == APPLIN


def test_sin_grand_tree_el_bono_de_fetch_no_existe():
    """The whole engine is INERT without the stadium on the table: the same board without
    Grand Tree does not force the search for the root Basic."""
    def _fetch(estadio):
        esc = (Escenario(turn=8, paso=30)
               .mi_activo(pk(OGERPON, energias=[G, G, G]))
               .mi_banca(pk(TAPU, energias=[G, G]))
               .mi_mano(GRASS, GRASS)
               .op_activo(pk(KANGASKHAN, hp=400))
               .op_zonas(mano=5, mazo=30, prizes=4))
        if estadio is not None:
            esc = esc.estadio(estadio, del_rival=True)
        obs = (esc.mazo(APPLIN, DIPPLIN, HYDRAPPLE, CHIKORITA, BAYLEEF,
                        MEGANIUM, GRASS, GRASS)
               .fetch_ultra_ball()
               .resto_al_descarte()
               .construir())
        eleccion = m.agent(obs)
        elegida = obs["select"]["option"][eleccion[0]]
        return obs["select"]["deck"][elegida["index"]]["id"]

    con = _fetch(GRAND_TREE)
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._field_at_turn_start = {}
    sin = _fetch(None)
    # With the stadium the new rule rules; without it, the search goes back to what
    # the pre-existing rules decided (here, the refresh engine: Meowth ex
    # is not in the declared deck, so the usual Stage 2 wins).
    assert con == APPLIN
    assert sin != APPLIN


def test_con_raiz_en_juego_no_se_fuerza_la_busqueda():
    """With an Applin already on the bench the root exists: the bonus does not apply and
    the rest of the deck's priorities rule."""
    esc = (Escenario(turn=8, paso=30)
           .mi_activo(pk(OGERPON, energias=[G, G, G]))
           .mi_banca(pk(APPLIN, aparecio=True))
           .mi_mano(GRASS, GRASS)
           .estadio(GRAND_TREE, del_rival=True)
           .op_activo(pk(KANGASKHAN, hp=400))
           .op_zonas(mano=5, mazo=30, prizes=4)
           .mazo(APPLIN, DIPPLIN, HYDRAPPLE, CHIKORITA, BAYLEEF, MEGANIUM,
                 GRASS, GRASS)
           .fetch_ultra_ball()
           .resto_al_descarte())
    obs = esc.construir()
    m.agent(obs)  # it must not blow up; the choice is decided by the previous rules
    ranking = m._gt_wanted_basics(m.ACTIVE_CARDS_IN_DECK,
                                     {OGERPON: 1, APPLIN: 1})
    assert APPLIN in ranking and CHIKORITA in ranking
