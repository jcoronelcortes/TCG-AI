"""The search paid its cost with the only fuel the free ability had.

Scenario (`records/registro_004_pasos_038_hasta_059.json`, step 39, turn 4,
WON vs Marnie's Grimmsnarl ex -- episode 92486283):

    US (6 prizes)                       RIVAL (5 prizes)
    active Teal Mask Ogerpon ex         active Marnie's Grimmsnarl ex
           210/210, ONE Grass                  320/320, 2 energies
           (Myriad Leaf Shower needs    bench  Morgrem, 2x Munkidori,
            three)                             2x Marnie's Impidimp
    bench  Bayleef 80/110  (1 of 5)     stadium Spikemuth Gym
    hand   Lana's Aid, ONE Basic Grass, Meganium, Boss's Orders, ULTRA BALL

The menu, and what the agent made of it:

    [1] Grass -> active        score    -1   tier  0   (yields to the dance)
    [2] Grass -> Bayleef       score  7000   tier  0
    [4] ULTRA BALL             score 31450   tier 10   <-- played
    [5] TEAL DANCE (active)    score  7500   tier  0

The Ultra Ball was the right card: `_ub_engine_refresh_pivot` with the bench at
one body and an active that cannot take 320 HP off. It paid its cost with
Boss's Orders and THE GRASS -- and that Grass was the only fuel Teal Dance had,
so the free attachment and the free draw died with it. Three actions later a
Bug Catching Set happened to dig two more Grass out of the top seven and the
dance was made after all; on the same board without that Bug Catching Set the
turn ends with the attacker one energy further from its attack.

WHY NOTHING SAW IT. Nothing was wrong with either number. The Ultra Ball is at
31450 because the engine pivot really is on this board, and Teal Dance is at
7500 because of the reserve band ("the active needs the Grass and there is only
one"). They do not even meet: the pivot promotes the Ultra Ball to
`_TIER_ENERGY` and a degraded ability stays in tier 0, so the TIER decided and
no score comparison ever happened.

THE FIX IS THE SENTENCE THE FILE ALREADY WRITES ONE BLOCK ABOVE. "The hand
reset goes last" lifts every ability that pays with a card from hand above the
refill that would shuffle that card away. An Ultra Ball is the same destroyer
with a smaller mouth: it takes two cards it CHOOSES, and a spare Basic Energy
is exactly what a discard scorer reads as surplus. So a play whose cost is
discarding from hand (`HAND_DISCARD_COST_PLAY_IDS`, read off the printed text:
Ultra Ball, Secret Box, Morty's Conviction, Iris's Fighting Spirit, Canari)
yields to any ability that pays with a card from hand AND GIVES ONE BACK
(`HAND_NEUTRAL_ABILITY_IDS`: Teal Dance, N's Zoroark ex's Trade, Lunatone's
Moonlight Dance).

AND THE ORDER THE OTHER WAY ROUND COSTS NOTHING, which is why the rule is a
rule. Teal Dance takes one card and draws one: the hand is the same size after
it, so the Ultra Ball is just as legal, decided with one card MORE of
information and one more candidate to pay its cost with -- and the card the
ability spends lands on the attacker instead of in the discard pile. The draw
can even be the card the search was digging for.

WHAT DOES NOT CHANGE, and it is the other half of the rule: Ripening Charge
attaches and HEALS, it hands nothing back, so playing it first shrinks the hand
-- and an Ultra Ball left with fewer than two cards to discard dies in hand,
which is the exact failure `_ub_engine_refresh_pivot` was written for
(registro_008 step 58). There the order is a genuine trade-off and stays
decided the way it was measured.

Golden corpus: six flips, all of the same shape (PLAY Ultra Ball -> ABILITY
Teal Mask Ogerpon ex) across five different opposing decks and both seats.
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
from ptcg.cards.tables import (HAND_COST_ABILITY_IDS, HAND_DISCARD_COST_PLAY_IDS,
                               HAND_NEUTRAL_ABILITY_IDS, HAND_RESET_PLAY_IDS)

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_the_dance_goes_before_the_ultra_ball_step39.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRAPPLE = m.Hydrapple_ex
GRASS = m.Basic_Grass_Energy
ULTRA_BALL = m.Ultra_Ball
BOSS = m.Boss_Orders
GRIMMSNARL = m.Grimmsnarl_ex
SECRET_BOX = 1092
ZOROARK = 293


@pytest.fixture(autouse=True)
def reset_main_state():
    import tests.golden_corpus as gc
    gc.reset_agent(m)
    yield
    gc.reset_agent(m)


def _sequence():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["sequence"])


def _replay_to_the_last_menu():
    """Every observation of the fixture; the last one is the menu under test."""
    seq = _sequence()
    for item in seq[:-1]:
        m.agent(item["observation"])
    return seq[-1]["observation"]


def _mine(obs):
    return obs["current"]["players"][obs["current"]["yourIndex"]]


def _theirs(obs):
    return obs["current"]["players"][1 - obs["current"]["yourIndex"]]


def _option(obs, kind, **fields):
    return next(i for i, o in enumerate(obs["select"]["option"])
                if o.get("type") == int(kind)
                and all(o.get(k) == v for k, v in fields.items()))


# ---------------------------------------------------------------------------
# 1. The two sets, read off the printed text
# ---------------------------------------------------------------------------

def test_the_ultra_ball_is_a_play_that_pays_from_the_hand():
    # "you can use this card only if you discard 2 other cards from your hand"
    assert ULTRA_BALL in HAND_DISCARD_COST_PLAY_IDS
    assert SECRET_BOX in HAND_DISCARD_COST_PLAY_IDS
    # It is NOT a hand reset: the block above this one never saw it.
    assert ULTRA_BALL not in HAND_RESET_PLAY_IDS
    # A Pokemon's ability text belongs to the other set, never to this one.
    assert all(int(m.card_table[cid].cardType) != int(m.CardType.POKEMON)
               for cid in HAND_DISCARD_COST_PLAY_IDS)


def test_only_the_abilities_that_give_the_card_back_are_reordered():
    # Teal Dance: "attach a Basic {G} Energy card from your hand to this
    # Pokemon. If you attached Energy ... draw a card." One out, one in.
    assert OGERPON in HAND_NEUTRAL_ABILITY_IDS
    assert ZOROARK in HAND_NEUTRAL_ABILITY_IDS
    # Ripening Charge attaches and HEALS. It pays from the hand, so it is in
    # the parent set -- and it shrinks the hand, so it is not in this one.
    assert HYDRAPPLE in HAND_COST_ABILITY_IDS
    assert HYDRAPPLE not in HAND_NEUTRAL_ABILITY_IDS
    assert HAND_NEUTRAL_ABILITY_IDS <= HAND_COST_ABILITY_IDS


# ---------------------------------------------------------------------------
# 2. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_ultra_ball_about_to_eat_the_only_grass():
    obs = _replay_to_the_last_menu()
    mine, theirs = _mine(obs), _theirs(obs)

    active = mine["active"][0]
    assert active["id"] == OGERPON and len(active["energyCards"]) == 1
    # Myriad Leaf Shower needs three: the dance does NOT make it attack today,
    # so nothing in the lethal bands is deciding this.
    assert m.ATTACK_ENERGY_REQ[OGERPON] == 3

    hand = [c["id"] for c in mine["hand"]]
    assert hand.count(GRASS) == 1, "one Grass: it is fuel OR fodder, not both"
    assert ULTRA_BALL in hand and BOSS in hand
    # The cost is two cards and the hand has five: the Ultra Ball is playable
    # before the dance and just as playable after it.
    assert len(hand) == 5

    assert theirs["active"][0]["id"] == GRIMMSNARL
    assert theirs["active"][0]["hp"] == 320

    # Both plays are really on the menu.
    assert _option(obs, m.OptionType.ABILITY, area=int(m.AreaType.ACTIVE)) >= 0
    assert any(o.get("type") == int(m.OptionType.PLAY)
               and hand[o["index"]] == ULTRA_BALL
               for o in obs["select"]["option"])


# ---------------------------------------------------------------------------
# 3. The decision
# ---------------------------------------------------------------------------

def test_the_dance_is_played_before_the_ultra_ball():
    obs = _replay_to_the_last_menu()
    choice = m.agent(obs)
    picked = obs["select"]["option"][choice[0]]
    assert (picked.get("type") == int(m.OptionType.ABILITY)
            and picked.get("area") == int(m.AreaType.ACTIVE)), (
        "the free attach-and-draw goes before the search that pays from hand; "
        f"got {choice} -> {picked}")


def _scored(obs):
    """`(scores, tiers)` of the menu `obs`, as `finalizar` ranked it."""
    box = {}
    import ptcg.turn.finalize as fin
    fin.TIER_CENSUS_SINK = (
        lambda ctx, sel, sc, tiers, o, mi: box.update(sc=list(sc), tier=list(tiers)))
    try:
        m.agent(obs)
    finally:
        fin.TIER_CENSUS_SINK = None
    return box["sc"], box["tier"]


def test_the_promotion_is_an_insertion_in_front_of_the_search():
    """One point above the spender, and nothing at all without one.

    The rule does not BOOST the ability -- it parks it immediately in front of
    the play whose cost could eat its fuel. So the number it ends up with is
    the spender's plus one, and with the spender out of the hand the ability is
    back on the band its own scorer gave it."""
    obs = _replay_to_the_last_menu()
    mine = _mine(obs)
    dance = _option(obs, m.OptionType.ABILITY, area=int(m.AreaType.ACTIVE))
    ub = next(i for i, o in enumerate(obs["select"]["option"])
              if o.get("type") == int(m.OptionType.PLAY)
              and mine["hand"][o["index"]]["id"] == ULTRA_BALL)

    scores, tiers = _scored(obs)
    assert scores[dance] == scores[ub] + 1 and tiers[dance] == tiers[ub], (
        "the ability is inserted one point above the spender, in its tier; got "
        f"{scores[dance]}/{tiers[dance]} against {scores[ub]}/{tiers[ub]}")
    inserted = scores[dance]

    without = _replay_to_the_last_menu()
    hand_ub = next(i for i, c in enumerate(_mine(without)["hand"])
                   if c["id"] == ULTRA_BALL)
    without["select"]["option"] = [
        o for o in without["select"]["option"]
        if not (o.get("type") == int(m.OptionType.PLAY)
                and o.get("index") == hand_ub)]
    alone, _ = _scored(without)
    dance_alone = _option(without, m.OptionType.ABILITY, area=int(m.AreaType.ACTIVE))
    assert alone[dance_alone] != inserted, (
        "with no discard-priced play on the menu nothing is inserted; the "
        f"ability kept {inserted}")


def test_the_ripening_charge_does_not_take_the_order_from_the_search():
    """The other half: an ability that does NOT give the card back.

    Same board with the active turned into a Hydrapple ex -- Ripening Charge
    pays a card from hand and hands nothing back, so playing it first would
    leave the Ultra Ball one card short of its own cost. That order is a
    trade-off, and this rule does not touch trade-offs."""
    obs = _replay_to_the_last_menu()
    mine = _mine(obs)
    active = mine["active"][0]
    active["id"] = HYDRAPPLE
    active["hp"] = active["maxHp"] = 330

    scores = {}
    import ptcg.turn.finalize as fin
    fin.TIER_CENSUS_SINK = (
        lambda ctx, sel, sc, tiers, o, mi: scores.update(sc=list(sc), tier=list(tiers)))
    try:
        m.agent(obs)
    finally:
        fin.TIER_CENSUS_SINK = None

    ability = _option(obs, m.OptionType.ABILITY, area=int(m.AreaType.ACTIVE))
    ub = next(i for i, o in enumerate(obs["select"]["option"])
              if o.get("type") == int(m.OptionType.PLAY)
              and mine["hand"][o["index"]]["id"] == ULTRA_BALL)
    assert ((scores["tier"][ability], scores["sc"][ability])
            < (scores["tier"][ub], scores["sc"][ub])), (
        "Ripening Charge shrinks the hand: it does not get the insertion")
