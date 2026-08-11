"""The forced discard does not pay THEIR Xerosic with OUR Xerosic.

Scenario (user, `records/registro_013_pasos_113_hasta_124.json`, episode
91513072, turn 13 vs Alakazam, LOST). On their turn they play Xerosic's
Machinations and our hand of seven has to come down to three:

    US                                      RIVAL
    active  Hydrapple ex 330/330 (2 {G})    active  Alakazam 140/140
    bench   Ogerpon ex (3 {G}), Ogerpon ex  bench   three more Alakazam,
            (1 {G}), Chikorita                      Dudunsparce
    hand    **Xerosic's Machinations**,     hand    18 cards
            Boss's Orders, Meowth ex,
            Tapu Bulu, Dipplin, Lillie's,
            Meganium

Of the four cards the agent handed over, one was its OWN Xerosic's Machinations
-- the card the whole matchup is built around, the cap on a Powerful Hand that
was reading EIGHTEEN cards at that moment (20 damage per card in their hand).

WHY IT WENT, and it is structural rather than situational. The discard ladder
had already answered the question the right way -- `op_is_alakazam_deck` -> 5,
"protect it the way the Meganium line is protected" -- and the block below it
overwrote that with `DISCARD_SUPPORTER_DEAD_DROP` (36), the band reserved for a
Supporter the board cannot use. That block orders the Supporters in hand by
`_supp_values`, the value layer that decides which Supporter gets played, so
that the card we KEEP and the card we would PLAY cannot disagree. But the value
layer prices FOUR ids -- Boss's Orders, Lillie's Determination, Dawn, Lana's Aid
-- and Xerosic's Machinations is not one of them: its play value lives on the
other scale, the disruption engine (`_score_xerosic_play`). The lookup was
written `_supp_values.get(card.id, 0)`, so a MISSING KEY read as a live value of
zero and the block declared dead the one Supporter it had never asked about. On
that scale the cap can never be anything else, in any deck, on any board.

THE FIX: silence is not a zero. The block now asks for MEMBERSHIP before it
speaks -- about a Supporter the value layer never priced it says nothing,
neither KEEP nor DROP, and the last word goes back to the ladder branch above,
which is where the matchup knowledge already lives. It names no card and no
deck: any Supporter added to `_SUPP_PLAY_IDS` without a branch in the value layer
is covered by the same sentence.

The guard is on the SUBJECT of the sentence only. The rivals list still counts
every Supporter in hand, priced or not, because it answers a different question
-- "is there another Supporter that could be sacrificed instead?" -- and
filtering the unpriced ones out of there as well was measured against the frozen
corpus: it emptied the rivals list on a hand whose only two Supporters were a
priced one and the cap, and cancelled a KEEP that had nothing to do with this
bug (registro_028, turn 7).

WHAT DID NOT CHANGE, and the tests below pin it: a Supporter the layer prices at
zero is still dead and still goes first. On this very board that is Boss's
Orders -- `_supp_values[1182] = 0`, no gust worth taking -- and it is the fourth
card discarded once the cap is safe.

Accepted flip in the frozen corpus (`tests/corpus/frozen_decisions.json`):
registro_001_alakazam_10 turn 9, another discard forced by their Xerosic, where
the agent kept an ORPHANED Hydrapple ex (no Applin or Dipplin in play, bench at
5/5) and paid with the cap instead. It now pays with the orphan.
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
from ptcg.cards.scoring import _SUPP_PLAY_IDS
import ptcg.turn.scoring as _scoring
from ptcg.turn.options import card as _card

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_t13_their_discard_does_not_eat_our_cap_step114.json")

XEROSIC = m.Xerosic_Machinations
BOSS = m.Boss_Orders
LILLIE = m.Lillie_Determination
MEOWTH = m.Meowth_ex
TAPU = m.Tapu_Bulu
DIPPLIN = m.Dipplin
MEGANIUM = m.Meganium


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _hand(obs):
    return [c["id"] for c in obs["current"]["players"][0]["hand"]]


def _discarded(obs, choice):
    hand = obs["current"]["players"][0]["hand"]
    return [hand[obs["select"]["option"][i]["index"]]["id"] for i in choice]


def _kept(obs, choice):
    dropped = list(_discarded(obs, choice))
    kept = []
    for cid in _hand(obs):
        if cid in dropped:
            dropped.remove(cid)
        else:
            kept.append(cid)
    return kept


def _run(obs=None):
    """Returns (obs, choice, per-card discard scores)."""
    obs = _obs() if obs is None else obs
    scores = {}
    original = _scoring._TABLE[_scoring.OptionType.CARD]

    def _spy(tc, o, score):
        value = original(tc, o, score)
        if tc.context == m.SelectContext.DISCARD:
            scores[tc.card.id] = value
        return value

    _scoring._TABLE[_scoring.OptionType.CARD] = _spy
    try:
        return obs, m.agent(obs), scores
    finally:
        _scoring._TABLE[_scoring.OptionType.CARD] = original


def _supp_values_of(obs):
    """The value layer as the discard scorer sees it on this very board."""
    seen = {}
    original = _scoring._TABLE[_scoring.OptionType.CARD]

    def _spy(tc, o, score):
        if tc.context == m.SelectContext.DISCARD and not seen:
            seen.update(tc._supp_values)
        return original(tc, o, score)

    _scoring._TABLE[_scoring.OptionType.CARD] = _spy
    try:
        m.agent(obs)
    finally:
        _scoring._TABLE[_scoring.OptionType.CARD] = original
    return seen


# ---------------------------------------------------------------------------
# 1. The record: the board that produced the mistake
# ---------------------------------------------------------------------------

def test_the_menu_of_step_114_is_the_one_from_the_record():
    obs = _obs()
    cur = obs["current"]
    mine = cur["players"][0]
    op = cur["players"][1]

    assert cur["yourIndex"] == 0
    # THEIR card is what makes us discard: the effect belongs to seat 1.
    assert obs["select"]["context"] == int(m.SelectContext.DISCARD)
    assert obs["select"]["effect"]["id"] == XEROSIC
    assert obs["select"]["effect"]["playerIndex"] == 1
    assert obs["select"]["minCount"] == obs["select"]["maxCount"] == 4

    assert sorted(_hand(obs)) == sorted(
        [XEROSIC, BOSS, MEOWTH, TAPU, DIPPLIN, LILLIE, MEGANIUM])
    # the hand of seven comes down to three
    assert len(obs["select"]["option"]) == 7

    # the matchup, and the hand the cap is aimed at
    bodies = ([p["id"] for p in op["active"]] + [p["id"] for p in op["bench"]])
    assert m.Alakazam_ex in bodies
    assert op["handCount"] == 18

    # our board is not the problem: an active that attacks and two charged
    # Ogerpon ex on the bench. What the turn needs from the hand is the cap.
    assert [p["id"] for p in mine["active"]] == [m.Hydrapple_ex]
    assert mine["bench"][0]["id"] == m.Teal_Mask_Ogerpon_ex


def test_the_value_layer_does_not_price_the_cap():
    """The root cause, asserted rather than described.

    If a later change teaches `evaluate_supporters` to price Xerosic's
    Machinations, this test is the reminder that the membership guard stops
    being a no-op for it -- and that the two scales then have to agree.
    """
    values = _supp_values_of(_obs())
    assert XEROSIC in _SUPP_PLAY_IDS
    assert XEROSIC not in values, (
        f"la capa de valor no puntua el Xerosic; valores: {values}")
    # the four it does price, and the one that is dead on THIS board
    for sid in (BOSS, LILLIE, m.Dawn, m.Lanas_Aid):
        assert sid in values
    assert values[BOSS] == 0 and values[LILLIE] > 0


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_the_cap_is_not_discarded():
    obs, choice, _ = _run()
    assert XEROSIC not in _discarded(obs, choice), (
        f"vs Alakazam, con 18 cartas en su mano, el Xerosic NO se paga a su "
        f"propio Xerosic; descarto {_discarded(obs, choice)}")


def test_the_dead_supporter_is_the_one_that_goes():
    """The block still does its job: Boss's Orders is priced at 0 by the value
    layer on this board and is the Supporter that pays."""
    obs, choice, scores = _run()
    assert BOSS in _discarded(obs, choice)
    assert scores[BOSS] == m.DISCARD_SUPPORTER_DEAD_DROP
    assert scores[LILLIE] == m.DISCARD_SUPPORTER_LIVE_KEEP


def test_the_hand_that_survives_is_the_one_the_next_turn_can_use():
    """Three cards, three jobs: the cap for their Powerful Hand, the refill, and
    the body whose Last-Ditch Catch goes and gets the next Supporter. What goes
    is what the board cannot use -- the manual attacker with no ex-immune wall
    to break, and two evolution pieces with no line to climb."""
    obs, choice, _ = _run()
    assert sorted(_kept(obs, choice)) == sorted([XEROSIC, LILLIE, MEOWTH])
    assert sorted(_discarded(obs, choice)) == sorted(
        [TAPU, DIPPLIN, MEGANIUM, BOSS])


def test_the_cap_keeps_the_matchup_score_of_its_own_branch():
    """It is the ladder branch that decides again, not the Supporter block."""
    _obs_, _choice, scores = _run()
    assert scores[XEROSIC] == 5, (
        f"vs Alakazam la rama del Xerosic vale 5; obtuvo {scores[XEROSIC]}")
    assert scores[XEROSIC] < m.DISCARD_SUPPORTER_DEAD_DROP


# ---------------------------------------------------------------------------
# 3. Controls: the exemption is not a blanket protection
# ---------------------------------------------------------------------------

def _swap_alakazam_for_dudunsparce(obs):
    """The same board with the Alakazam line replaced by the Dunsparce one.

    Same hand, same 18 cards on their side, no Powerful Hand: the matchup, not
    the block, is what has to decide whether the cap is worth a keep-slot.
    """
    op = obs["current"]["players"][1]
    # 66 Dudunsparce / 65 Dunsparce: the 1-prize line their own deck already
    # carries, so the board stays legal and nothing else about it moves.
    _line = {m.Alakazam_ex: 66, m.Kadabra: 65, m.Abra: 65}
    for pkmn in op["active"] + op["bench"]:
        pkmn["id"] = _line.get(pkmn["id"], pkmn["id"])
        for pre in pkmn.get("preEvolution") or []:
            pre["id"] = _line.get(pre["id"], pre["id"])
    for card in op["discard"]:
        card["id"] = _line.get(card["id"], card["id"])
    return obs


def test_without_the_matchup_the_cap_is_discardable_again():
    obs, choice, scores = _run(_swap_alakazam_for_dudunsparce(_obs()))
    assert scores[XEROSIC] == 60, (
        f"fuera del matchup manda la otra rama de la escalera; "
        f"obtuvo {scores[XEROSIC]}")
    assert XEROSIC in _discarded(obs, choice)


def test_the_guard_does_not_touch_our_own_costs():
    """The block serves two callers and the change is about neither of them: it
    is about WHICH card the block is allowed to speak about. On our own Ultra
    Ball cost the cap is protected by the same ladder branch, which is what
    `test_discard_protects_xerosic_vs_alakazam` already pins."""
    obs = _obs()
    obs["select"]["effect"] = {"id": m.Ultra_Ball, "playerIndex": 0,
                               "serial": 999}
    obs["select"]["minCount"] = obs["select"]["maxCount"] = 2
    _obs_, choice, scores = _run(obs)
    assert scores[XEROSIC] == 5
    assert XEROSIC not in _discarded(_obs_, choice)
