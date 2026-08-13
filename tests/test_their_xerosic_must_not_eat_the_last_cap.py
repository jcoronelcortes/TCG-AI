"""Their Xerosic cut our hand to three and the cap was the fourth card out.

Scenario (user, `records/registro_009_pasos_118_hasta_127.json`, episode
92413910, step 124, turn 9 vs Alakazam). On their turn they play Xerosic's
Machinations and our hand of seven has to come down to three. Their Powerful
Hand had just knocked our Tapu Bulu out for 220 -- "place 2 damage counters on
your opponent's Active Pokemon for each card in your hand", and they were
holding eleven:

    US (4 prizes)                          RIVAL (5 prizes, ELEVEN cards)
    bench   Ogerpon ex (4 {G}), Fezandipiti  active  Alakazam ex 140/140
            ex, Meganium, Ogerpon ex         bench   Fezandipiti ex, Kadabra x2,
            (4 {G}), Hydrapple ex                    Lopunny, Buneary
    hand    Applin, Dipplin, **Boss's
            Orders**, **Unfair Stamp**,
            Lillie's Determination,
            **Xerosic's Machinations**,
            Ultra Ball

The agent handed over Applin (83), Dipplin (55), Ultra Ball (38) and its own
Xerosic's Machinations (5) -- the last one anywhere: the other copy was already
in the discard pile and none was left in the deck. It was the fourth highest
because the two Supporters that survived were both sitting on the keep floor of
2, and the cap's own matchup branch has been 5 since long before that floor
existed.

TWO SCORERS OF ONE CARD, DISAGREEING IN THE MATCHUP THE CARD EXISTS FOR. On that
same board the PLAY scorer priced the cap at `XEROSIC_SCORE_SOBRE_BOSS` + 300 =
7300 -- explicitly ABOVE the Boss's Orders it was being sacrificed to (6800 at
most) -- and it could not say so in the discard: the card-agnostic Supporter
block reads `_supp_values`, the value layer never prices Xerosic, and about a
card it never measured that block correctly says nothing.

THE FIX IS TWO RUNGS, both gated on `_xr_cap_lost_if_discarded` -- Alakazam, and
no copy of the cap left in the deck:

  * the cap drops to `DISCARD_XEROSIC_CAP_IS_THE_ANSWER` (1), below every other
    Supporter and latched so a second copy cannot claim the same reason;
  * Lillie's Determination stops holding the "last refill" floor. It SHUFFLES
    OUR HAND INTO THE DECK, so keeping both means the refill's own play buries
    the answer we just kept. With the tie gone, the Boss's Orders the value
    layer prices at 970 stays and the refill it prices at 450 goes.

WHY THE PILE AND THE DECK ARE NOT THE SAME LOSS, and why this predicate is not
the one the Lillie's veto uses. `do_not_shuffle_the_last_xerosic` asks about the
Meowth ex route as well, because a shuffle puts the cap back IN THE DECK, which
is exactly where Last-Ditch Catch ("search your deck for a supporter card") can
go and get it. The discard pile has no such door: Lana's Aid recovers Pokemon
without a Rule Box and basic Energy, Night Stretcher a Pokemon or an Energy, and
nothing in the deck recovers a Supporter. So the discard half asks the deck-copy
question and stops there.

MEASURED. One decision changes in the whole local corpus -- this one -- and
ZERO in the frozen corpus (`tests/corpus/frozen_decisions.json`): in
`registro_001_alakazam` the cap menus move from 5 to 1 without any menu changing
its ranking, which is the shape a rule that only breaks a tie should have.
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
from ptcg.cards import ids
from ptcg.decision.disruption import (_xr_cap_lost_if_discarded,
                                      _xr_last_copy_locked_in_hand)

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_t9_their_xerosic_must_not_eat_our_cap_step124.json")

XEROSIC = m.Xerosic_Machinations
BOSS = m.Boss_Orders
LILLIE = m.Lillie_Determination
STAMP = m.Unfair_Stamp
APPLIN = m.Applin
DIPPLIN = m.Dipplin
ULTRA = m.Ultra_Ball


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


def _run(obs=None, todos=False):
    """The menu as the agent answers it, with the ladder's own scores.

    `todos=True` returns the score of EVERY copy instead of the first one,
    which is the only way to see a latch working.
    """
    obs = obs if obs is not None else _obs()
    scores = {}
    original = m.score_option

    def espia(tc, o, score):
        resultado = original(tc, o, score)
        card = m.get_card(tc.obs, o.area, o.index,
                          getattr(o, "playerIndex", tc.my_index))
        if card is not None and resultado is not tc._SALTAR:
            scores.setdefault(card.id, []).append(resultado)
        return resultado

    espacios = [esp for esp in
                (getattr(mod, "__dict__", {}) for mod in list(sys.modules.values())
                 if mod is not None)
                if esp.get("score_option") is original]
    for esp in espacios:
        esp["score_option"] = espia
    try:
        choice = m.agent(obs)
    finally:
        for esp in espacios:
            esp["score_option"] = original
    if todos:
        return obs, choice, scores
    return obs, choice, {cid: v[0] for cid, v in scores.items()}


# ---------------------------------------------------------------------------
# 1. The decision
# ---------------------------------------------------------------------------

def test_the_last_cap_is_not_discarded():
    obs, choice, _ = _run()
    assert XEROSIC not in _discarded(obs, choice), (
        f"vs Alakazam, con once cartas en su mano, el ultimo cap NO se paga a "
        f"su propio Xerosic; descarto {_discarded(obs, choice)}")


def test_the_hand_that_survives_is_the_one_the_next_turn_can_use():
    """Three cards, three jobs: the cap that takes their Powerful Hand from 220
    to 60, the Stamp that answers the knockout they just took, and the gust the
    value layer prices highest on this board (970). What goes is the refill that
    would shuffle the cap away, plus two evolution pieces and the search that
    has nothing left to buy."""
    obs, choice, _ = _run()
    assert sorted(_kept(obs, choice)) == sorted([BOSS, STAMP, XEROSIC])
    assert sorted(_discarded(obs, choice)) == sorted(
        [APPLIN, DIPPLIN, ULTRA, LILLIE])


# ---------------------------------------------------------------------------
# 2. The two rungs, and that they are a PERMUTATION among Supporters
# ---------------------------------------------------------------------------

def test_the_cap_outranks_every_other_supporter():
    _obs_, _choice, scores = _run()
    assert scores[XEROSIC] == ids.DISCARD_XEROSIC_CAP_IS_THE_ANSWER
    assert scores[XEROSIC] < ids.DISCARD_SUPPORTER_LIVE_KEEP
    # and never below the one card that is kept before it
    assert scores[STAMP] < scores[XEROSIC]


def test_the_refill_loses_the_floor_it_was_tying_with():
    """The Boss's Orders keeps the live floor; the refill is priced as the
    single copy it is. Before the rule both sat at 2 and the tie was broken by
    the order of the menu, which sent the gust away."""
    _obs_, _choice, scores = _run()
    assert scores[BOSS] == ids.DISCARD_SUPPORTER_LIVE_KEEP
    assert scores[LILLIE] > scores[BOSS]
    # It is still a Supporter, not fodder: it stays under every item in hand.
    assert scores[LILLIE] < scores[ULTRA]


def test_only_supporters_move():
    """The evolution pieces and the search are priced exactly as before: the
    change is a permutation inside the Supporter band, so how many
    non-Supporters are discarded cannot move."""
    _obs_, _choice, scores = _run()
    assert scores[APPLIN] == 83
    assert scores[DIPPLIN] == 55
    assert scores[ULTRA] == 38


# ---------------------------------------------------------------------------
# 3. Controls: the two halves of the harness
# ---------------------------------------------------------------------------

def _with_a_copy_back_in_the_deck(obs):
    """The same board with the OTHER Xerosic still in the deck.

    The tracker derives the deck from deck.csv minus what it can see, so taking
    the spent copy out of our discard pile is what puts it back in the deck --
    and that is the whole condition of the rule.
    """
    mine = obs["current"]["players"][0]
    mine["discard"] = [c for c in mine["discard"] if c["id"] != XEROSIC]
    return obs


def test_with_a_copy_still_in_the_deck_the_ordinary_price_answers():
    """The specificity half. The cap is no longer the last access, so the
    branch gives it the 5 it always gave, the refill keeps its floor, and the
    baseline decision comes back."""
    obs, choice, scores = _run(_with_a_copy_back_in_the_deck(_obs()))
    assert scores[XEROSIC] == 5
    assert scores[LILLIE] == ids.DISCARD_SUPPORTER_LIVE_KEEP
    assert XEROSIC in _discarded(obs, choice)


def test_only_the_first_copy_can_be_the_reason():
    """The latch. "No copy left in the deck" is a claim about the DECK, so every
    copy in hand answers it identically -- and a floor below the best live
    Supporter said of two cards sacrifices two Supporters to keep one answer.
    The second copy falls back to the branch's ordinary 5, which is what makes
    it the fourth card out here.

    Same failure the counter-stadium and the Meowth ex had before their own
    latches (`utils/duplicate_protection_audit.py`): the surplus is what makes a
    card cheap, never expensive.
    """
    obs = _with_a_copy_back_in_the_deck(_obs())
    obs["current"]["players"][0]["hand"][0] = {
        "id": XEROSIC, "playerIndex": 0, "serial": 61}
    obs, choice, scores = _run(obs, todos=True)
    assert sorted(scores[XEROSIC]) == [
        ids.DISCARD_XEROSIC_CAP_IS_THE_ANSWER, 5]
    assert _discarded(obs, choice).count(XEROSIC) == 1
    assert XEROSIC in _kept(obs, choice)


def _swap_alakazam_for_dudunsparce(obs):
    """The same board with the Alakazam line replaced by the Dunsparce one: no
    Powerful Hand across the table, so nothing here may fire."""
    op = obs["current"]["players"][1]
    _line = {m.Alakazam_ex: 66, m.Kadabra: 65, m.Abra: 65}
    for pkmn in op["active"] + op["bench"]:
        pkmn["id"] = _line.get(pkmn["id"], pkmn["id"])
        for pre in pkmn.get("preEvolution") or []:
            pre["id"] = _line.get(pre["id"], pre["id"])
    for card in op["discard"]:
        card["id"] = _line.get(card["id"], card["id"])
    return obs


def test_outside_the_matchup_neither_rung_fires():
    """Both rungs are gated on the same predicate, so both have to go silent
    together: the cap falls back to the generic reading of their hand and the
    refill gets its floor back."""
    _obs_, _choice, scores = _run(_swap_alakazam_for_dudunsparce(_obs()))
    assert scores[XEROSIC] == ids.DISCARD_XEROSIC_CAPS_A_FAT_HAND
    assert scores[LILLIE] == ids.DISCARD_SUPPORTER_LIVE_KEEP


def test_with_the_rule_switched_off_the_old_answer_comes_back():
    """The sensitivity half, and the reason the two rungs share one predicate:
    switching it off has to give back the recorded decision EXACTLY -- the cap
    in the pile, the refill on the floor of 2 and the tie with the gust broken
    by the order of the menu."""
    from ptcg.turn.options import card as _card_mod
    original = _card_mod._xr_cap_lost_if_discarded
    _card_mod._xr_cap_lost_if_discarded = lambda c: False
    try:
        obs, choice, scores = _run()
    finally:
        _card_mod._xr_cap_lost_if_discarded = original
    assert scores[XEROSIC] == 5
    assert scores[LILLIE] == scores[BOSS] == ids.DISCARD_SUPPORTER_LIVE_KEEP
    assert sorted(_discarded(obs, choice)) == sorted(
        [APPLIN, DIPPLIN, ULTRA, XEROSIC])


# ---------------------------------------------------------------------------
# 4. The predicate: the discard half is not the shuffle half
# ---------------------------------------------------------------------------

class _Ctx:
    """The five fields the two predicates read."""

    def __init__(self, **kw):
        self.op_is_alakazam_deck = kw.get("op_is_alakazam_deck", True)
        self.hand_counts = kw.get("hand_counts", {XEROSIC: 1})
        self.op_hand_count = kw.get("op_hand_count", 11)
        self.cards_in_deck = kw.get("cards_in_deck", {})
        self.field_counts = kw.get("field_counts", {})


def test_the_meowth_route_answers_the_shuffle_and_not_the_pile():
    """A Meowth ex in the deck is a way to get the cap back OUT OF THE DECK, so
    it cancels the shuffle veto and cannot cancel the discard reading: from the
    pile Last-Ditch Catch recovers nothing."""
    con_meowth = _Ctx(cards_in_deck={m.Meowth_ex: {"DECK": 2}})
    assert _xr_cap_lost_if_discarded(con_meowth)
    assert not _xr_last_copy_locked_in_hand(con_meowth)


def test_the_discard_half_is_the_deck_copy_question():
    """And nothing else: a copy left in the deck, a hand without the cap,
    another deck across the table or an opposing hand too small to cap each
    cancels it on its own."""
    assert _xr_cap_lost_if_discarded(_Ctx())
    assert not _xr_cap_lost_if_discarded(
        _Ctx(cards_in_deck={XEROSIC: {"DECK": 1}}))
    assert not _xr_cap_lost_if_discarded(_Ctx(hand_counts={}))
    assert not _xr_cap_lost_if_discarded(_Ctx(op_is_alakazam_deck=False))
    assert not _xr_cap_lost_if_discarded(_Ctx(op_hand_count=3))


def test_the_shuffle_half_is_the_discard_half_plus_the_route():
    """One predicate contains the other, which is what stops the two readings
    drifting apart the way the two SCORERS of this card already did."""
    sin_meowth = _Ctx(cards_in_deck={m.Meowth_ex: {"DECK": 0}})
    assert _xr_last_copy_locked_in_hand(sin_meowth)
    assert _xr_cap_lost_if_discarded(sin_meowth)
