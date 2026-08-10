"""With the turn's Supporter already in hand, the Last-Ditch brings the refill.

Scenario (`records/registro_005_pasos_041_hasta_059.json`, episode 91176376,
turn 5 vs Alakazam -- LOST). The Meowth ex has just been benched and its
Last-Ditch Catch is choosing a Supporter out of the deck. In hand: a **Boss's
Orders**. The ctx of that very prompt prices the three cards on one scale:

    Boss's Orders (IN HAND) 970  >  Dawn 900  >  Lillie's Determination 800

The fetch took the **Dawn**. Only one Supporter is played per turn, and the
Boss's was above every candidate -- so the card just fetched could not be the
Supporter of this turn. The record played it out exactly so: three actions later
the Boss's gusted a Kadabra for the prize and the Dawn was still in hand when
the turn ended. A two-prize body on the bench bought a card that never moved.

WHY THE LADDER DID NOT SEE IT. Every branch of `_RULES_MEOWTH_FETCH` compares
the candidates against EACH OTHER; not one of them looks at what the hand
already holds. So the pick was made for a slot that was not on offer.

CARD RULE (user, august 2026), deck-agnostic: once the slot is taken, the fetch
is choosing for a LATER turn -- and that changes which card is best. Dawn only
sits above Lillie's here because of the SAME-TURN rush its premium is made of
(`_v_meowth_fetch_value` lets it keep its value while a Forest of Vitality is in
play, which is what lets a body played this turn evolve at once), and a rush
needs the slot the Boss's is taking. The refill does not: Lillie's draws eight
whenever it is played. So refills are exempt and the rest are capped.

WHAT IT DOES NOT TOUCH, and this is the delicate half: every branch that names a
REASON to bring a card returns ABOVE this rule -- the winning gust, the line cut,
the recovery that creates the KO, the Xerosic cap vs Alakazam. Those exist
precisely because the fetch scale and the play scale can rank two cards the
opposite way round (`xerosic_priority_over_boss` is that case, written down),
and a comparison made on the fetch scale must not talk over them. What is left
below is the tail, where no candidate has a reason -- which is where the Dawn
and the Lillie's of this record were.

See `the_slot_is_taken_so_bring_what_survives` in `ptcg/decision/meowth.py`, and
[[supporter-del-turno-ya-en-mano-no-meowth]] for the same question asked one step
earlier, about whether to bench the Meowth at all.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m  # noqa: E402

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_the_slot_is_taken_the_last_ditch_brings_the_refill_step52.json")

BOSS = m.Boss_Orders
DAWN = m.Dawn
LILLIE = m.Lillie_Determination
XEROSIC = m.Xerosic_Machinations
OGERPON = m.Teal_Mask_Ogerpon_ex


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    yield
    m._init_cards_tracking()


def _obs():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


def _fetched(obs):
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    choice = m.agent(copy.deepcopy(obs))
    deck = obs["select"]["deck"]
    return deck[obs["select"]["option"][choice[0]]["index"]]["id"]


def _offered(obs):
    deck = obs["select"]["deck"]
    return {deck[o["index"]]["id"] for o in obs["select"]["option"]}


# ---------------------------------------------------------------------------
# 1. The record
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_last_ditch_prompt_with_the_boss_in_hand():
    o = _obs()
    assert o["select"]["effect"]["id"] == m.Meowth_ex, (
        "el escenario es el prompt del Last-Ditch Catch")
    assert BOSS in [c["id"] for c in _mine(o)["hand"]], (
        "el Boss's Orders ya estaba en la mano: es quien se lleva el hueco")
    assert o["current"]["supporterPlayed"] is False
    assert {DAWN, LILLIE} <= _offered(o), (
        "el prompt ofrecia las dos: el menu mide la preferencia")


def test_the_fetch_brings_the_refill_and_not_the_rush():
    """The regression of the record: Dawn 900 beat Lillie's 800 while a Boss's
    at 970 was already holding the slot."""
    assert _fetched(_obs()) == LILLIE, (
        "con el hueco del turno tomado por el Boss's de la mano, el Last-Ditch "
        "trae el refresco (Lillie's), no la Dawn que necesitaba jugarse hoy")


def test_with_the_slot_free_the_dawn_wins_again():
    """The control that keeps the rule to what it says.

    The same board with the Boss's swapped for a Teal Mask Ogerpon ex -- same
    hand SIZE (so no other branch of the ladder moves) and no Supporter holding
    the slot. There the Dawn's rush premium is real again and it wins, exactly
    as before.
    """
    o = _obs()
    for c in _mine(o)["hand"]:
        if c["id"] == BOSS:
            c["id"] = OGERPON
    assert _fetched(o) == DAWN, (
        "con el hueco libre la Dawn vuelve a ganar: la regla habla del hueco, "
        "no de la carta")


# ---------------------------------------------------------------------------
# 2. The ladder, rule by rule
# ---------------------------------------------------------------------------

def _score(card_id, **kw):
    field = dict(sv=0, hand_counts={}, supp_values={}, hand_size=4,
                 strong_attacker=True, op_hand_count=4,
                 active_cant_attack=False, win_via_boss=False,
                 gust2_via_boss=False, deny_evo_via_boss=False,
                 devel_lillie=False, alakazam=False, first_turn=False,
                 lillie_alcanzable=True, gust_over_immune_active=False,
                 recovery_ko=False, hand_supp_val=0)
    field.update(kw)
    ctx = m._CtxMeowthFetch(
        card_id, field["sv"], field["hand_counts"], field["supp_values"],
        field["hand_size"], field["strong_attacker"], field["op_hand_count"],
        field["active_cant_attack"], field["win_via_boss"],
        field["gust2_via_boss"], field["deny_evo_via_boss"],
        field["devel_lillie"], field["alakazam"], field["first_turn"],
        field["lillie_alcanzable"], field["gust_over_immune_active"],
        field["recovery_ko"], field["hand_supp_val"])
    value, _ = m._resolve_rules(m._RULES_MEOWTH_FETCH, [], ctx, 50)
    return value


def test_a_candidate_that_loses_to_the_hand_is_capped():
    assert _score(DAWN, sv=900, hand_supp_val=970) == 40, (
        "por debajo del Supporter de la mano, el candidato no puede jugarse hoy")
    assert _score(DAWN, sv=900, hand_supp_val=900) == 40, (
        "el empate tambien: la carta de la mano ya ocupa el hueco")


def test_the_refill_is_exempt_and_a_better_candidate_is_not_capped():
    assert _score(LILLIE, sv=800, hand_supp_val=970) == 800, (
        "el refresco conserva su valor para el turno siguiente")
    assert _score(DAWN, sv=1100, hand_supp_val=970) == 1100, (
        "un candidato que SUPERA a la mano si puede llevarse el hueco")


def test_it_does_not_talk_over_the_reasons_above_it():
    """The specificity that matters: the two scales rank in reverse.

    `xerosic_priority_over_boss` (1310) exists because the PLAY scorer puts the
    cap above the gust (7000 vs 6800) while the fetch scale, which never prices
    Xerosic at all, would put it at zero. If this rule ran before it, a Boss's in
    hand would bury the very card the matchup is about.
    """
    assert _score(XEROSIC, sv=0, hand_supp_val=970, alakazam=True,
                  op_hand_count=9, hand_size=4) == 1310, (
        "el tope vs Alakazam sigue mandando sobre el Boss's de la mano")
    assert _score(m.Boss_Orders, sv=970, hand_supp_val=970,
                  win_via_boss=True, hand_counts={}) == 1300, (
        "y el gusteo que gana la partida tampoco cede")
