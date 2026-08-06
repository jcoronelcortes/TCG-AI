"""The one-prize wall of our first turn: put it down, pay for it, put it in front.

Scenario (`records/registro_002_pasos_010_hasta_019.json`, step 14, turn 2,
LOST vs Marnie -- episode 90088064):

    US (6 prizes)                        RIVAL (Marnie)
    active  Chikorita 70, 0 energies      active  Marnie's Impidimp 70 (1 {D})
    bench   Meowth ex 170                 bench   --
    hand    Meganium, Meowth ex, Ultra Ball, Forest, **Tapu Bulu**,
            **Lillie's Determination**

The agent played the Lillie's, which SHUFFLES THE WHOLE HAND INTO THE DECK.
The Tapu Bulu went with it. Of everything in that hand it was the one card
drawing more cards cannot replace: a BASIC worth ONE prize with 140 HP, the
body this deck wants in front while the bench is being built -- the opponent
needs more than one attack to remove it, and when it finally falls it pays a
single prize.

THE RULE (user, ago 2026), in three parts and deck-agnostic. `is_one_prize_wall`
(ptcg/calc/card.py) reads the three properties off the card -- basic, one
prize, hard to remove and a real attacker -- so a deck with a different body in
that role inherits the rule without a line of code:

  * the wall goes DOWN before the refill can shuffle it away
    (`_ft_wall_in_hand`, an envelope over the PLAY branch: what it has to beat
    is spread all over the per-card ladder, from the first-turn matchup vetoes
    to the "wait until the items are played" cap);
  * this turn's energy goes to the ACTIVE up to its retreat cost
    (`_ft_wall_charge_active`), which is the only thing that makes the engine
    OFFER the retreat;
  * if by the end of the turn we cannot attack, the active retreats and the
    wall takes the front (`_ft_wall_pivot`), and the promotion one observation
    later brings up the wall and not the biggest body.

WHAT THE PIVOT ASKS FOR, and why it is narrower than "we cannot attack" (user's
decision after seeing the alternatives): the retreat DESTROYS the energy that
pays it, so the swap has to answer a threat. Their projection -- the attack of
the active they have AND the one it becomes in one step -- has to take our body
in front down and NOT take the wall down. With that condition the two rules
already measured on this same board stay intact: turn 1 going first nothing
they assemble with a single energy reaches a tough opener (no sacrifice of
early development), and an opposing active with no energy on it does not make
us spend ours.
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
from state_builder import Scenario, pk

_FIXTURE = ROOT / "tests" / "fixtures" / "marnie_t2_wall_before_the_refill_step14.json"

G = int(m.EnergyType.GRASS)
W = int(m.EnergyType.WATER)

TAPU = m.Tapu_Bulu
CHEWTLE = m.Chewtle          # 60 damage with two energies: it knocks out a
                             # damaged body and does NOT knock out the wall


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


def _obs_fixture():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _chosen(obs):
    """(OptionType, the id of the card it points at) of the agent's decision."""
    opt = obs["select"]["option"][m.agent(copy.deepcopy(obs))[0]]
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    card_id = None
    if opt["type"] == int(m.OptionType.PLAY):
        card_id = mine["hand"][opt["index"]]["id"]
    elif opt["type"] == int(m.OptionType.CARD):
        card_id = mine["bench"][opt["index"]]["id"]
    return int(opt["type"]), card_id


# ---------------------------------------------------------------------------
# 0. The predicate: which bodies the rule is about
# ---------------------------------------------------------------------------

def test_the_predicate_reads_the_card_and_not_a_list_of_ids():
    # In this deck exactly one body plays the part. The three properties are
    # what excludes the rest: prizes (the ex), HP (the fragile openers) and
    # stage (the ones that need a line assembled first).
    assert m.is_one_prize_wall(TAPU)
    assert not m.is_one_prize_wall(m.Teal_Mask_Ogerpon_ex)   # 2 prizes
    assert not m.is_one_prize_wall(m.Meowth_ex)              # 2 prizes
    assert not m.is_one_prize_wall(m.Chikorita)              # 70 HP
    assert not m.is_one_prize_wall(m.Applin)                 # 60 HP
    assert not m.is_one_prize_wall(m.Meganium)               # not a basic
    assert not m.is_one_prize_wall(m.Ultra_Ball)             # not a Pokemon


# ---------------------------------------------------------------------------
# 1. The record: the wall goes down BEFORE the hand refill
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_turn_2_that_was_lost():
    o = _obs_fixture()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]

    assert cur["turn"] == 2 and cur["firstPlayer"] != cur["yourIndex"]
    assert not cur["supporterPlayed"]
    assert mine["active"][0]["id"] == m.Chikorita
    hand = [c["id"] for c in mine["hand"]]
    assert TAPU in hand and m.Lillie_Determination in hand
    offered = {mine["hand"][opt["index"]]["id"]
               for opt in o["select"]["option"] if opt["type"] == 7}
    assert {TAPU, m.Lillie_Determination} <= offered, (
        "el menu ofrecia AMBAS: la decision es de orden, no de legalidad")


def test_the_wall_goes_down_instead_of_the_refill():
    kind, card_id = _chosen(_obs_fixture())
    assert (kind, card_id) == (int(m.OptionType.PLAY), TAPU), (
        "en nuestro primer turno el muro de 1 premio se baja ANTES del "
        "refresco: la Lillie's baraja la mano entera y se lo lleva al mazo")


def test_the_refill_is_not_lost_only_postponed():
    # The point is the ORDER, not vetoing the Supporter: with the wall already
    # on the bench, the Lillie's is still the play of that same turn.
    o = _obs_fixture()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    tapu_i = next(i for i, c in enumerate(mine["hand"]) if c["id"] == TAPU)
    mine["bench"] = list(mine["bench"]) + [{
        "id": TAPU, "serial": mine["hand"][tapu_i]["serial"], "playerIndex": 0,
        "hp": 140, "maxHp": 140, "appearThisTurn": True, "energies": [],
        "energyCards": [], "tools": [], "preEvolution": []}]
    mine["hand"] = [c for i, c in enumerate(mine["hand"]) if i != tapu_i]
    mine["handCount"] = len(mine["hand"])
    o["select"]["option"] = [
        opt for opt in o["select"]["option"]
        if not (opt["type"] == 7 and opt["index"] == tapu_i)]
    for opt in o["select"]["option"]:
        if opt["type"] == 7 and opt["index"] > tapu_i:
            opt["index"] -= 1

    kind, card_id = _chosen(o)
    assert (kind, card_id) == (int(m.OptionType.PLAY), m.Lillie_Determination), (
        "con el muro ya en banca el refresco vuelve a ser la jugada del turno")


def test_control_outside_our_first_turn_the_ladder_decides():
    # The rule is about the first turn: it is there that the hand still holds
    # the wall and the refill is about to shuffle it. Later the per-card ladder
    # (crowding, matchup, items pending) owns the decision again.
    o = _obs_fixture()
    o["current"]["turn"] = 6
    kind, card_id = _chosen(o)
    assert card_id != TAPU, (
        "fuera del primer turno el muro no tiene banda propia: decide la "
        "escalera de siempre")


def test_control_a_copy_already_in_play_does_not_claim_the_band():
    # One wall in front is enough; a second copy is development like any other
    # and the crowding vetoes own it.
    o = _obs_fixture()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    mine["bench"] = list(mine["bench"]) + [{
        "id": TAPU, "serial": 900, "playerIndex": 0, "hp": 140, "maxHp": 140,
        "appearThisTurn": False, "energies": [], "energyCards": [],
        "tools": [], "preEvolution": []}]
    kind, card_id = _chosen(o)
    assert card_id != TAPU, (
        "con una copia ya en juego la segunda no reclama la banda del muro")


# ---------------------------------------------------------------------------
# 2. The pivot: charge, retreat, promote
# ---------------------------------------------------------------------------

def _pivot(active=None, bench=None, op=None, hand=(m.Night_Stretcher,),
           energy_played=True, turn=2, first_player=1):
    """Our first turn with a body in front that their active knocks out and a
    wall on the bench that it does not."""
    return (Scenario(turn=turn, step=20, tac=3, first_player=first_player,
                     energy_played=energy_played, supporter_played=True)
            .my_active(active or pk(m.Meowth_ex, hp=50, energies=[G], fisicas=1))
            .my_bench(*(bench or (pk(TAPU), pk(m.Applin))))
            .my_hand(*hand)
            .op_active(op or pk(CHEWTLE, energies=[W, W], fisicas=2))
            .op_zones(hand=4, deck=40, prizes=6))


def test_the_energy_goes_to_the_active_to_pay_the_retreat():
    o = (_pivot(active=pk(m.Meowth_ex, hp=50), energy_played=False,
                hand=(m.Basic_Grass_Energy,))
         .menu_hand(with_attachment=True).build())
    opt = o["select"]["option"][m.agent(o)[0]]
    assert opt["type"] == int(m.OptionType.ATTACH), (
        f"el adjunte es la jugada del turno, no {opt}")
    assert opt["inPlayArea"] == int(m.AreaType.ACTIVE), (
        "la Planta va al ACTIVO: es lo unico que hace que el motor OFREZCA la "
        "retirada hacia el muro")


def test_with_no_attack_the_active_retreats():
    o = _pivot().menu_hand(with_retreat=True).build()
    assert _chosen(o)[0] == int(m.OptionType.RETREAT), (
        "sin ataque disponible y con el cuerpo de delante condenado, se "
        "retira para poner el muro de 1 premio")


def test_the_promotion_brings_up_the_wall():
    # The bench holds the wall AND a charged 2-prize ex: the generic ranking
    # (prizes x 1000 + HP) brings up the ex, which is precisely the body the
    # pivot exists to hide.
    o = (_pivot(bench=(pk(TAPU), pk(m.Teal_Mask_Ogerpon_ex, energies=[G, G],
                                    fisicas=2)))
         .promote_after_retreat().build())
    kind, card_id = _chosen(o)
    assert (kind, card_id) == (int(m.OptionType.CARD), TAPU), (
        "tras la retirada sube el muro de 1 premio, no el cuerpo mas grande")


def test_control_attacking_comes_first():
    # A turn with an attack in it is not a turn without a plan: we attack and
    # the wall waits on the bench. `can_attack` is what the flag reads.
    o = _pivot(active=pk(m.Teal_Mask_Ogerpon_ex, hp=60, energies=[G, G, G],
                         fisicas=3)).menu_hand(with_retreat=True,
                                               with_attack=True).build()
    assert _chosen(o)[0] == int(m.OptionType.ATTACK), (
        "atacar con el activo sigue siendo lo primero")


def test_control_a_wall_they_one_shot_is_not_a_wall():
    # The premise of the whole idea is that the body in front ENDURES. Damaged
    # to 50 HP the Tapu falls to the same hit as the active, so it buys no
    # turns: the flag switches off and the promotion goes back to being
    # answered by the logic that owns it.
    #
    # It is the promotion and not the retreat that is measured here: on a board
    # with a doomed 2-prize ex in front, other pivots -- older and measured --
    # also want to retreat, and a test that asked for "it does not retreat"
    # would be pinning THEM. The threat side of the flag is pinned from the
    # other end by two tests that were already there:
    # `test_boss_does_not_give_away_the_alakazam_line` (their active carries no
    # energy: the turn closes in END) and
    # `test_abomasnow_first_turn_going_first_it_does_not_sacrifice`.
    o = (_pivot(bench=(pk(TAPU, hp=50),
                       pk(m.Teal_Mask_Ogerpon_ex, energies=[G, G], fisicas=2)))
         .promote_after_retreat().build())
    assert _chosen(o)[1] != TAPU, (
        "un muro que el rival noquea de un golpe no compra turnos: la "
        "promocion vuelve a la logica de siempre")
