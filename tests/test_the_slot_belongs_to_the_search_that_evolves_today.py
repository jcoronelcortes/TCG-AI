"""The turn's Supporter goes to the search that BUILDS the body, not to the cap.

Scenario (user, `records/registro_003` step 26, turn 3 vs Marnie -- WON, but
this turn was thrown away):

    US                                          THEM
    active  Dipplin (evolved THIS turn, 1 Grass) active  Munkidori 110
    bench   Meganium 160 (Wild Growth)           bench   3 bodies, no energy
            Teal Mask Ogerpon ex 210 (2 Grass)   hand    **8 cards**
    stadium **Forest of Vitality** (ours)
    hand    **Dawn**, Ultra Ball,
            **Xerosic's Machinations**, Chikorita
    supporterPlayed: NO -- one Supporter, two candidates.

**Forest of Vitality is what makes the turn**: "each player's {G} Pokemon can
evolve into {G} Pokemon during the turn they play those Pokemon". The Dipplin
that came down this step may still become a Stage 2 before the turn ends -- the
whole Chikorita -> Bayleef -> Meganium chain had just been assembled the same
way, on steps 23 and 24.

    Dawn        "Search your deck for a Basic Pokemon, a Stage 1 Pokemon, and a
                 Stage 2 Pokemon, reveal them, and put them into your hand."
    Xerosic's   "Your opponent discards cards from their hand until they have 3
                 cards in their hand."

The agent played **Xerosic** (five of their cards to the discard), retreated the
Dipplin -- burning the Grass it had just attached -- and attacked with the
Ogerpon ex it had to pull out of the bench, where its Tera was making it
untouchable. Dawn instead buys **Hydrapple ex** out of the deck (its own fetch
table already prices exactly this piece at `immediate_evo`, the top rung of
`_RULES_DAWN_HYDRAPPLE`), puts it on the Dipplin under Forest, and attacks with
a 330 HP body that is still in the front spot next turn.

WHY IT LOST BY ONE POINT, and why the number is not the defect. The two scorers
were reading DIFFERENT boards:

  * `generic_very_big_hand` is a FLAT `XEROSIC_SCORE_GENERIC` (3380) that reads
    ONE fact -- how many cards THEY hold -- and never asks what our own board
    would do with the slot;
  * Dawn's play value is a four-rung ladder over two booleans about our board
    (`meganium_in_play`, `has_hydrapple`) that never asks what its own fetch
    would BUY: with Meganium down and no Hydrapple it answered 700, i.e.
    `SCORE_SUPPORTER_VALUE_BASE + int(700 * 1.4)` = 3379.

Fix (`_xr_the_slot_belongs_to_the_search`, deck-agnostic): the cap yields to
`XEROSIC_SCORE_LAST_RESORT` when a live Pokemon-search Supporter in hand buys an
evolution that a body in play can WEAR THIS TURN. Disruption that only touches
their hand cannot outbid a search that converts into a body the same turn,
against any deck: the cap takes no prize, builds nothing, and KEEPS (their hand
is big again next turn), while the evolution window closes when the stadium is
replaced.

The law already existed for the ITEM search -- `_ub_evolve_now_search` says the
same thing for Ultra Ball -- and had never been written for the SUPPORTER
search, which is the one that actually competes for a slot.

SCOPE. It sits immediately above `generic_very_big_hand` and BELOW every
`_xr_gate_alakazam` branch: against the deck the card is in the list for,
capping Powerful Hand is the board play and keeps its priority.
"""

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import main as m
from main_support import _make_boss_ctx, reset_main_state  # noqa: F401 (fixture)
from rule_trace import assert_reason, resolve

from ptcg.cards.groups import EVO_LINES, POKEMON_SEARCH_SUPPORTER_IDS
from ptcg.decision.disruption import (_RULES_XEROSIC_PLAY,
                                      _the_search_buys_an_evolution_today,
                                      _xr_the_slot_belongs_to_the_search)
from ptcg.state.zones import ZONE_DECK

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_t3_the_slot_belongs_to_the_search_step26.json")

DAWN = m.Dawn
XEROSIC = m.Xerosic_Machinations
ULTRA_BALL = m.Ultra_Ball
CHIKORITA = m.Chikorita
DIPPLIN = m.Dipplin
HYDRAPPLE = m.Hydrapple_ex
MEGANIUM = m.Meganium
OGERPON = m.Teal_Mask_Ogerpon_ex
FOREST = m.Forest_of_Vitality


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _idx_play(obs, card_id):
    """Index of the 'PLAY <card_id>' option in the menu, or -1."""
    cur = obs["current"]
    hand = cur["players"][cur["yourIndex"]]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(m.OptionType.PLAY) and hand[o["index"]]["id"] == card_id:
            return i
    return -1


# ---------------------------------------------------------------------------
# 1. The record: first the board, then the decision
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_turn_the_forest_opens():
    o = _obs()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert cur["supporterPlayed"] is False, "el Supporter del turno sigue libre"
    assert [c["id"] for c in cur["stadium"]] == [FOREST], (
        "Forest of Vitality en mesa: el Dipplin bajado este turno AUN evoluciona")
    assert [c["id"] for c in mine["active"]] == [DIPPLIN]
    assert mine["active"][0]["appearThisTurn"] is True, (
        "el Dipplin evoluciono ESTE turno -- sin Forest no podria evolucionar otra vez")
    assert sorted(c["id"] for c in mine["bench"]) == sorted([MEGANIUM, OGERPON])
    assert [c["id"] for c in mine["hand"]] == [DAWN, ULTRA_BALL, XEROSIC, CHIKORITA]
    assert theirs["handCount"] == 8, (
        "mano rival de 8: por encima de XEROSIC_BIG_HAND, la banda que "
        "encendia generic_very_big_hand")
    assert all(c["id"] != HYDRAPPLE for c in mine["hand"]), (
        "el Hydrapple ex NO esta en mano: es justo la mitad que compra la busqueda")


def test_the_menu_offers_both_supporters():
    o = _obs()
    assert _idx_play(o, DAWN) >= 0 and _idx_play(o, XEROSIC) >= 0, (
        "el paso ofrecia las dos: el menu es el que mide la prioridad")


def test_the_turn_buys_the_stage_two_instead_of_capping_their_hand():
    """The regression of the record: the cap took the slot by one point."""
    o = _obs()
    assert m.agent(copy.deepcopy(o)) == [_idx_play(o, DAWN)], (
        "el Supporter del turno es la busqueda que pone el cuerpo, no el cap")


# ---------------------------------------------------------------------------
# 2. The rule that decides, by NAME
# ---------------------------------------------------------------------------

def _ctx_of_the_record(**overrides):
    """The step-26 board as a DecisionContext, minus whatever a test moves."""
    base = dict(
        hand_counts={DAWN: 1, ULTRA_BALL: 1, XEROSIC: 1, CHIKORITA: 1},
        field_counts={DIPPLIN: 1, MEGANIUM: 1, OGERPON: 1},
        field_at_turn_start={OGERPON: 1},
        supp_values={DAWN: 700},
        cards_in_deck={HYDRAPPLE: {ZONE_DECK: 2}},
        forest_in_play=True,
        meganium_in_play=True,
        op_hand_count=8,
    )
    base.update(overrides)
    return _make_boss_ctx(**base)


def test_the_rule_that_decides_is_the_yield_and_not_the_generic_cap():
    score, why = resolve(_RULES_XEROSIC_PLAY, [], _ctx_of_the_record(), default=0)
    assert_reason(why, "yields_to_the_search_that_evolves_today")
    assert score == m.XEROSIC_SCORE_LAST_RESORT, (
        "cede a la banda de 'solo si no puntua nada mas', no a un veto: si la "
        "busqueda cayese, el Supporter se gasta igual en vez de perderse")


def test_without_the_search_in_hand_the_cap_keeps_its_generic_score():
    """The guard: with no Dawn there is nothing better to do with the slot."""
    ctx = _ctx_of_the_record(hand_counts={XEROSIC: 1, ULTRA_BALL: 1},
                             supp_values={})
    score, why = resolve(_RULES_XEROSIC_PLAY, [], ctx, default=0)
    assert_reason(why, "generic_very_big_hand")
    assert score == m.XEROSIC_SCORE_GENERIC


def test_the_alakazam_cap_is_above_the_yield_and_keeps_the_slot():
    """Against the deck the card is in the list for, capping IS the board play."""
    ctx = _ctx_of_the_record(op_is_alakazam_deck=True,
                             op_state=SimpleNamespace(
                                 active=[SimpleNamespace(
                                     id=m.Alakazam_ex, preEvolution=[])],
                                 bench=[]))
    score, why = resolve(_RULES_XEROSIC_PLAY, [], ctx, default=0)
    assert score > m.XEROSIC_SCORE_GENERIC, (
        "la rama Alakazam esta POR ENCIMA del cedido y no la toca: "
        f"decidio {why}")


# ---------------------------------------------------------------------------
# 3. The predicate: what makes the search worth the slot
# ---------------------------------------------------------------------------

def test_the_search_buys_the_evolution_the_body_can_wear_today():
    assert _the_search_buys_an_evolution_today(_ctx_of_the_record())


def test_the_evolution_already_in_hand_does_not_need_a_search():
    ctx = _ctx_of_the_record(
        hand_counts={DAWN: 1, XEROSIC: 1, HYDRAPPLE: 1})
    assert not _the_search_buys_an_evolution_today(ctx), (
        "con la evolucion YA en mano no hay nada que comprar: el Supporter "
        "del turno no se justifica por una busqueda que sobra")


def test_an_evolution_that_is_no_longer_in_the_deck_buys_nothing():
    ctx = _ctx_of_the_record(cards_in_deck={HYDRAPPLE: {ZONE_DECK: 0}})
    assert not _the_search_buys_an_evolution_today(ctx), (
        "el mazo es la unica zona que alcanza una busqueda")


def test_without_the_forest_a_body_that_came_down_today_cannot_wear_it():
    """`_evolvable_counts`: the Dipplin appeared this turn -- without the
    stadium it is not evolvable, so the search buys a card for TOMORROW and no
    longer outbids the cap TODAY."""
    ctx = _ctx_of_the_record(forest_in_play=False,
                             field_at_turn_start={OGERPON: 1})
    assert not _the_search_buys_an_evolution_today(ctx)
    ctx_ayer = _ctx_of_the_record(forest_in_play=False,
                                  field_at_turn_start={OGERPON: 1, DIPPLIN: 1})
    assert _the_search_buys_an_evolution_today(ctx_ayer), (
        "el mismo Dipplin, en juego desde el inicio del turno, SI lo lleva")


def test_an_ex_evolution_is_not_bought_against_a_board_immune_to_ex():
    """The same clamp `_ub_evolve_now_search` spells out for Ultra Ball: against
    Crustle/Cornerstone an ex evolution is a dead card, not an attacker."""
    assert not _the_search_buys_an_evolution_today(
        _ctx_of_the_record(op_is_crustle_deck=True))
    assert not _the_search_buys_an_evolution_today(
        _ctx_of_the_record(op_has_ex_immune_active=True))


def test_the_yield_does_not_fire_for_a_search_the_turn_will_not_play():
    """The guard is the exact negation of Dawn's own vetoes: if the search is
    not going to be played, stepping aside loses the slot for BOTH."""
    assert not _xr_the_slot_belongs_to_the_search(
        _ctx_of_the_record(supp_values={DAWN: 0})), (
        "valor 0 es el veto que usa _score_dawn_play")
    assert not _xr_the_slot_belongs_to_the_search(
        _ctx_of_the_record(state=SimpleNamespace(
            supporterPlayed=True, turn=3, energyAttached=False)))


# ---------------------------------------------------------------------------
# 4. Deck-agnostic: it names no card
# ---------------------------------------------------------------------------

def test_the_predicate_reads_the_declared_lines_and_not_a_card_name():
    """Every pre->evo pair of `EVO_LINES` reaches the rule the same way: swap
    the deck and the sentence keeps answering, without editing the predicate."""
    for line in EVO_LINES:
        for pre, evo in zip(line, line[1:]):
            ctx = _make_boss_ctx(
                hand_counts={DAWN: 1, XEROSIC: 1},
                field_counts={pre: 1},
                field_at_turn_start={pre: 1},
                supp_values={DAWN: 700},
                cards_in_deck={evo: {ZONE_DECK: 1}},
                op_hand_count=8,
            )
            assert _the_search_buys_an_evolution_today(ctx), (
                f"la linea {line} no llega a la regla en el eslabon {pre}->{evo}")


def test_the_search_supporters_are_a_named_group_not_a_hard_coded_card():
    assert DAWN in POKEMON_SEARCH_SUPPORTER_IDS
    assert XEROSIC not in POKEMON_SEARCH_SUPPORTER_IDS, (
        "el cap no busca Pokemon: no puede ser su propio motivo para ceder")


@pytest.mark.parametrize("rule_name", ["yields_to_the_search_that_evolves_today"])
def test_the_rule_sits_above_the_generic_cap(rule_name):
    names = [r.name for r in _RULES_XEROSIC_PLAY]
    assert names.index(rule_name) < names.index("generic_very_big_hand"), (
        "por encima del cap generico...")
    assert names.index(rule_name) > names.index("alakazam_cap_the_hand"), (
        "...y por debajo de toda rama Alakazam")
